"""Fictional-only acceptance. Run with migrated restricted PostgreSQL."""

import json
from datetime import timedelta
from unittest.mock import patch
from uuid import uuid4

import pytest
from django.db import IntegrityError, connection, transaction
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient, APIRequestFactory

from common.testing import rls_org
from integrations.authentication import decode, tenant_transaction
from integrations.manifests import MANIFESTS, permits_observation
from integrations.models import IntegrationAuditEvent as Audit
from integrations.models import IntegrationConnection as Connection
from integrations.models import IntegrationCredential as Credential
from integrations.models import ProviderNamespace as Namespace
from integrations.views import ProbeView

ROOT = "/api/integrations/v1/"


@pytest.fixture(autouse=True)
def fictional(settings, org_a, org_b):
    settings.INTEGRATION_FOUNDATION_ENABLED = True
    settings.INTEGRATION_TEST_ORGS = [str(org_a.id), str(org_b.id)]
    settings.INTEGRATION_AUDIENCE = "isolated-foundation-test"


def post(client, path, **data):
    data.setdefault("request_id", str(uuid4()))
    return client.post(ROOT + path, data, format="json")


@pytest.fixture
def registry(admin_client):
    namespace = post(
        admin_client,
        "namespaces/",
        provider_key="fixture_a",
        account_key="test_account",
    )
    assert namespace.status_code == 201, namespace.content
    conn = post(
        admin_client,
        "connections/",
        namespace_id=namespace.json()["id"],
        label="TEST fixture",
        manifest_id="fixture_a:acquisition",
    )
    assert conn.status_code == 201, conn.content
    return conn.json()["id"]


def issue(admin_client, registry, **overrides):
    data = {
        "expected_revision": Connection.objects.get(id=registry).revision,
        "expires_at": (timezone.now() + timedelta(days=2)).isoformat(),
        "scopes": ["integration.probe"],
        **overrides,
    }
    result = post(admin_client, f"connections/{registry}/credentials/", **data)
    assert result.status_code == 201, result.content
    return result.json()


def service(raw):
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION="Bearer " + raw)
    return client


def test_registry_probe_lifecycle(admin_client, registry):
    key = issue(admin_client, registry)
    client = service(key["credential"])
    assert client.get(ROOT + "service/probe/").status_code == 200
    assert Credential.objects.get(id=key["id"]).token_digest not in str(key)
    paused = post(
        admin_client,
        f"connections/{registry}/state/",
        expected_revision=2,
        target="paused",
        reason_code="maintenance",
    )
    assert paused.status_code == 200, paused.content
    assert client.get(ROOT + "service/probe/").status_code == 401
    assert (
        post(
            admin_client,
            f"connections/{registry}/state/",
            expected_revision=3,
            target="active",
            reason_code="resume",
        ).status_code
        == 200
    )
    assert client.get(ROOT + "service/probe/").status_code == 200
    assert (
        post(
            admin_client,
            f"connections/{registry}/state/",
            expected_revision=4,
            target="revoked",
            reason_code="compromise",
        ).status_code
        == 200
    )
    assert client.get(ROOT + "service/probe/").status_code == 401
    assert Credential.objects.get(id=key["id"]).revoked_at


@pytest.mark.django_db(transaction=True)
def test_committed_credentials_survive_database_reconnect(
    admin_client, registry, org_a
):
    key = issue(admin_client, registry)
    assert not connection.in_atomic_block
    connection.close()
    client = service(key["credential"])
    assert client.get(ROOT + "service/probe/").status_code == 200
    with rls_org(org_a):
        assert Credential.objects.get(id=key["id"]).token_digest
        assert Audit.objects.filter(credential_id=key["id"]).count() == 1


@pytest.mark.parametrize("offset,expected", [(-1, 200), (0, 401), (1, 401)])
def test_rotation_retirement_boundary(admin_client, registry, offset, expected):
    first = issue(admin_client, registry)
    second = issue(admin_client, registry, replaces_id=first["id"], overlap_seconds=60)
    old = Credential.objects.get(id=first["id"])
    assert old.revoked_at is None and old.retire_at < old.expires_at
    with patch(
        "integrations.authentication.timezone.now",
        return_value=old.retire_at + timedelta(seconds=offset),
    ):
        assert (
            service(first["credential"]).get(ROOT + "service/probe/").status_code
            == expected
        )
        assert (
            service(second["credential"]).get(ROOT + "service/probe/").status_code
            == 200
        )


def test_zero_overlap(admin_client, registry):
    first = issue(admin_client, registry)
    second = issue(admin_client, registry, replaces_id=first["id"], overlap_seconds=0)
    assert service(first["credential"]).get(ROOT + "service/probe/").status_code == 401
    assert service(second["credential"]).get(ROOT + "service/probe/").status_code == 200


def test_issue_retry_and_conflict(admin_client, registry):
    request_id = str(uuid4())
    expiry = (timezone.now() + timedelta(days=2)).isoformat()
    first = issue(admin_client, registry, request_id=request_id, expires_at=expiry)
    result = post(
        admin_client,
        f"connections/{registry}/credentials/",
        request_id=request_id,
        expires_at=expiry,
        scopes=["integration.probe"],
        expected_revision=1,
    )
    assert result.status_code == 200, result.content
    assert not result.json()["secret_available"] and "credential" not in result.json()
    assert result.json()["id"] == first["id"] and Credential.objects.count() == 1
    assert (
        post(
            admin_client,
            f"connections/{registry}/credentials/",
            request_id=request_id,
            expires_at=expiry,
            scopes=[],
            expected_revision=1,
        ).status_code
        == 400
    )
    assert (
        post(
            admin_client,
            f"connections/{registry}/credentials/",
            request_id=request_id,
            expires_at=expiry,
            scopes=["integration.probe"],
            expected_revision=99,
        ).status_code
        == 409
    )


@pytest.mark.parametrize(
    "path",
    [
        "/api/patients/",
        "/api/contacts/",
        "/api/org/",
        "/api/auth/me/",
        ROOT + "namespaces/",
        ROOT + "connections/",
    ],
)
def test_service_cannot_read_legacy_or_manage(admin_client, registry, path):
    key = issue(admin_client, registry)
    assert service(key["credential"]).get(path).status_code == 403


@pytest.mark.parametrize(
    "field,value",
    [
        ("scopes", []),
        ("scopes", ["*"]),
        ("scopes", ["patients:read"]),
        ("scopes", ["integration.receive"]),
        ("overlap_seconds", 86401),
        ("unknown", True),
    ],
)
def test_reject_credential_escalation(admin_client, registry, field, value):
    data = {
        "expected_revision": 1,
        "expires_at": (timezone.now() + timedelta(days=1)).isoformat(),
        "scopes": ["integration.probe"],
        field: value,
    }
    assert (
        post(admin_client, f"connections/{registry}/credentials/", **data).status_code
        == 400
    )
    assert Credential.objects.count() == 0


def test_disabled_and_direct_view_fail_closed(admin_client, registry):
    with override_settings(INTEGRATION_FOUNDATION_ENABLED=False):
        assert admin_client.get(ROOT + "connections/").status_code == 404
    with override_settings(INTEGRATION_TEST_ORGS=[]):
        assert admin_client.get(ROOT + "connections/").status_code == 404
    result = ProbeView.as_view()(APIRequestFactory().get(ROOT + "service/probe/"))
    assert result.status_code == 401


def test_regular_and_foreign_practice(
    user_client, org_b_client, admin_client, registry
):
    assert user_client.get(ROOT + "connections/").status_code == 403
    assert org_b_client.get(ROOT + f"connections/{registry}/").status_code in (403, 404)
    assert admin_client.get(ROOT + "service/probe/").status_code == 403


def test_metadata_does_not_reveal_secret(admin_client, registry):
    key = issue(admin_client, registry)
    for path in (
        "namespaces/",
        "connections/",
        f"connections/{registry}/credentials/",
        f"connections/{registry}/audit/",
    ):
        result = admin_client.get(ROOT + path)
        assert result.status_code == 200, result.content
        assert key["credential"].encode() not in result.content
        assert (
            Credential.objects.get(id=key["id"]).token_digest.encode()
            not in result.content
        )
        assert result["Cache-Control"] == "private, no-store"
    assert "test_account" not in admin_client.get(ROOT + "namespaces/").content.decode()


def test_db_forced_rls_and_foreign_link(admin_client, registry, org_b, profile_b):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE relname LIKE 'mp_integration_%' AND relkind='r'"
        )
        assert cursor.fetchall() == [(True, True)] * 4
    with rls_org(org_b):
        assert not Connection.objects.filter(id=registry).exists()
        with pytest.raises(IntegrityError), transaction.atomic():
            Namespace.objects.create(
                org=org_b,
                created_by_profile_id=Connection.objects.model.objects.none().first()
                or uuid4(),
                provider_key="fixture_a",
                account_key="test_foreign",
            )


def test_append_only_audit_and_namespace(admin_client, registry):
    for row in (Audit.objects.first(), Namespace.objects.first()):
        with pytest.raises(IntegrityError), transaction.atomic():
            type(row).objects.filter(pk=row.pk).delete()
    with pytest.raises(IntegrityError), transaction.atomic():
        Namespace.objects.update(account_key="test_relabel")


def test_pinned_manifest_and_authority():
    assert len(MANIFESTS) == 8
    for key in MANIFESTS:
        assert not permits_observation(key, "patient.identity_linked")
        assert not permits_observation(key, "payment.reconciled")
        assert not permits_observation(key, "conversion.corrected")
    assert not permits_observation("fixture_a:acquisition", "treatment.completed")
    assert permits_observation("fixture_b:clinical", "treatment.completed")


def test_context_restores_after_exception(org_a):
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('app.current_org',true)")
        before = cursor.fetchone()[0]
    with pytest.raises(RuntimeError), tenant_transaction(org_a.id):
        raise RuntimeError("synthetic")
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('app.current_org',true)")
        assert cursor.fetchone()[0] == before


def test_unaudited_write_rejected_before_tenant_context_restored(org_a, admin_profile):
    before = Namespace.objects.count()
    with pytest.raises(IntegrityError, match="Namespace requires audit"):
        with tenant_transaction(org_a.id):
            Namespace.objects.create(
                org=org_a,
                provider_key="fixture_a",
                account_key="test_missing_audit",
                created_by_profile=admin_profile,
            )
    assert Namespace.objects.count() == before


def test_audit_guards_checked_before_returning_to_other_practice(
    admin_client, org_a, org_b
):
    with rls_org(org_b):
        result = post(
            admin_client,
            "namespaces/",
            provider_key="fixture_a",
            account_key="test_context_switch",
        )
        assert result.status_code == 201, result.content
        assert not Namespace.objects.filter(pk=result.json()["id"]).exists()
        # No deferred query for the first practice may leak into the caller's
        # context or fail when its enclosing transaction commits.
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")
            cursor.execute("SET CONSTRAINTS ALL DEFERRED")
    with rls_org(org_a):
        assert Namespace.objects.filter(pk=result.json()["id"]).exists()


@pytest.mark.parametrize(
    "mode",
    ["signature", "secret", "audience", "mixed", "expired", "org_header", "oversized"],
)
def test_service_credential_failures(admin_client, registry, mode):
    key = issue(admin_client, registry)
    raw = key["credential"]
    client = service(raw)
    expected = 401
    if mode == "signature":
        parts = raw.split(".")
        parts[2] = parts[2][:-1] + ("a" if parts[2][-1] != "a" else "b")
        client = service(".".join(parts))
    elif mode == "secret":
        client = service(raw[:-1] + ("a" if raw[-1] != "a" else "b"))
    elif mode == "audience":
        with override_settings(INTEGRATION_AUDIENCE="another-isolated-deployment"):
            assert client.get(ROOT + "service/probe/").status_code == 401
        return
    elif mode == "mixed":
        client.credentials(
            HTTP_AUTHORIZATION="Bearer " + raw, HTTP_TOKEN="unused-fictional"
        )
        expected = 403
    elif mode == "expired":
        expiry = Credential.objects.get(id=key["id"]).expires_at
        with patch("integrations.authentication.timezone.now", return_value=expiry):
            assert client.get(ROOT + "service/probe/").status_code == 401
        return
    elif mode == "org_header":
        client.credentials(
            HTTP_AUTHORIZATION="Bearer " + raw, HTTP_X_ORG_ID=str(uuid4())
        )
        expected = 403
    elif mode == "oversized":
        client = service("mpis1." + "a" * 2100)
    assert client.get(ROOT + "service/probe/").status_code == expected


def test_slot_limit_namespace_replacement_and_stale_revision(admin_client, registry):
    first = issue(admin_client, registry)
    issue(admin_client, registry)
    response = post(
        admin_client,
        f"connections/{registry}/credentials/",
        expected_revision=3,
        expires_at=(timezone.now() + timedelta(days=1)).isoformat(),
        scopes=["integration.probe"],
    )
    assert response.status_code == 409
    assert (
        post(
            admin_client,
            f"connections/{registry}/state/",
            expected_revision=1,
            target="paused",
            reason_code="maintenance",
        ).status_code
        == 409
    )
    old_namespace = Connection.objects.get(id=registry).namespace_id
    assert (
        post(
            admin_client,
            f"connections/{registry}/state/",
            expected_revision=3,
            target="revoked",
            reason_code="compromise",
        ).status_code
        == 200
    )
    result = post(
        admin_client,
        "connections/",
        namespace_id=str(old_namespace),
        label="TEST replacement",
        manifest_id="fixture_a:acquisition",
    )
    assert result.status_code == 201, result.content
    assert result.json()["namespace_id"] == str(old_namespace)
    assert service(first["credential"]).get(ROOT + "service/probe/").status_code == 401


def test_no_domain_effects_and_no_receiver(admin_client, registry):
    from contacts.models import Contact
    from patients.models import Appointment, JourneyEvent, Patient, Receipt

    models = (Contact, Patient, Receipt, JourneyEvent, Appointment)
    before = [model.objects.count() for model in models]
    issue(admin_client, registry)
    assert admin_client.post(ROOT + "events/", {}, format="json").status_code in (
        404,
        405,
    )
    assert [model.objects.count() for model in models] == before


def test_rollback_after_audit_failure(admin_client, registry):
    from integrations.models import IntegrationAuditEvent

    before = (
        Credential.objects.count(),
        Connection.objects.get(id=registry).revision,
        Audit.objects.count(),
    )
    admin_client.raise_request_exception = False
    with patch.object(
        IntegrationAuditEvent.objects,
        "create",
        side_effect=RuntimeError("synthetic audit failure"),
    ):
        response = post(
            admin_client,
            f"connections/{registry}/credentials/",
            expected_revision=1,
            expires_at=(timezone.now() + timedelta(days=1)).isoformat(),
            scopes=["integration.probe"],
        )
        assert response.status_code == 503
        assert response.json() == {
            "detail": "Integration service temporarily unavailable."
        }
    assert (
        Credential.objects.count(),
        Connection.objects.get(id=registry).revision,
        Audit.objects.count(),
    ) == before


def test_database_manifest_scopes_lifecycle_guards(admin_client, registry):
    key = issue(admin_client, registry)
    for model, pk, values in [
        (Connection, registry, {"mode": "live"}),
        (Connection, registry, {"capabilities": {"id": "forged"}}),
        (Credential, key["id"], {"scopes": []}),
        (Credential, key["id"], {"expires_at": timezone.now() + timedelta(days=60)}),
        (Connection, registry, {"revision": 0}),
        (Audit, Audit.objects.first().id, {"details": {"patient": "forbidden"}}),
    ]:
        with pytest.raises(IntegrityError), transaction.atomic():
            model.objects.filter(pk=pk).update(**values)


def test_real_foreign_links_and_credential_reads(
    admin_client, registry, org_a, org_b, profile_b, org_b_client
):
    key = issue(admin_client, registry)
    with rls_org(org_b):
        assert not Credential.objects.filter(pk=key["id"]).exists()
    result = post(
        org_b_client, "namespaces/", provider_key="fixture_a", account_key="test_other"
    )
    # The repository's org_b fixture is an administrator.
    assert result.status_code == 201, result.content
    foreign = result.json()["id"]
    result = post(
        admin_client,
        "connections/",
        namespace_id=foreign,
        label="TEST foreign",
        manifest_id="fixture_a:acquisition",
    )
    assert result.status_code == 404
    with pytest.raises(IntegrityError), transaction.atomic():
        Connection.objects.filter(pk=registry).update(namespace_id=foreign)


@pytest.mark.parametrize("credential_kind", ["pat", "org_key", "portal"])
def test_nonhuman_credentials_cannot_manage(
    admin_profile, admin_client, registry, credential_kind
):
    client = APIClient()
    if credential_kind == "pat":
        from common.models import PersonalAccessToken

        raw, token = PersonalAccessToken.generate(
            profile=admin_profile, name="TEST integration denial", scopes=[]
        )
        client.credentials(HTTP_AUTHORIZATION="Bearer " + raw)
    elif credential_kind == "org_key":
        client.credentials(HTTP_TOKEN=str(admin_profile.org.api_key))
    else:
        from rest_framework_simplejwt.tokens import AccessToken

        token = AccessToken()
        token["token_type"] = "portal"
        token["org_id"] = str(admin_profile.org_id)
        client.credentials(HTTP_AUTHORIZATION="Bearer " + str(token))
    assert client.get(ROOT + "namespaces/").status_code in (401, 403)
    assert post(
        client, "namespaces/", provider_key="fixture_a", account_key="test_forbidden"
    ).status_code in (401, 403)
    assert Namespace.objects.count() == 1


def test_scope_body_bounds_and_safe_failures(admin_client, registry):
    response = post(
        admin_client,
        "namespaces/",
        provider_key="fixture_a",
        account_key="test_a",
        payload="x" * 17000,
    )
    assert response.status_code == 400
    assert (
        post(
            admin_client,
            "namespaces/",
            provider_key="fixture_a",
            account_key="test_a",
            org_id=str(uuid4()),
        ).status_code
        == 403
    )
    assert admin_client.delete(ROOT + f"connections/{registry}/").status_code == 405
    assert (
        admin_client.patch(
            ROOT + f"connections/{registry}/", {}, format="json"
        ).status_code
        == 405
    )
    with patch(
        "integrations.middleware.tenant_transaction",
        side_effect=RuntimeError("synthetic secret must not escape"),
    ):
        result = admin_client.get(ROOT + "connections/")
    assert result.status_code == 503
    assert b"synthetic secret" not in result.content


def test_credential_retirement_independent_predicate(admin_client, registry):
    # Use a real persisted, signed credential; isolate the retirement predicate
    # without weakening the database's command/audit requirements.
    key = issue(admin_client, registry)
    raw = key["credential"]
    now = timezone.now()
    from integrations.authentication import resolve_service

    stored = Credential.objects.get(id=key["id"])
    stored.retire_at = now
    stored.revoked_at = None
    assert stored.expires_at > now
    with (
        patch(
            "integrations.authentication.IntegrationCredential.objects.filter"
        ) as query,
        patch("integrations.authentication.timezone.now", return_value=now),
    ):
        query.return_value.first.return_value = stored
        from rest_framework.exceptions import AuthenticationFailed

        with pytest.raises(AuthenticationFailed):
            resolve_service(raw, decode(raw))


def test_revocation_wins_during_wait_for_connection_lock(admin_client, registry):
    key = issue(admin_client, registry)
    first = Credential.objects.get(id=key["id"])
    second = issue(admin_client, registry, replaces_id=key["id"], overlap_seconds=60)
    old = Credential.objects.get(id=first.id)
    # First clock read (signed locator) is before cutoff; the locked resolver's
    # later clock read crosses it, proving an earlier sample cannot authorize.
    with patch(
        "integrations.authentication.timezone.now",
        side_effect=[old.retire_at - timedelta(seconds=1), old.retire_at],
    ):
        assert (
            service(key["credential"]).get(ROOT + "service/probe/").status_code == 401
        )
    assert service(second["credential"]).get(ROOT + "service/probe/").status_code == 200


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("rotation", [False, True])
def test_concurrent_issuance_serializes_revision(
    admin_client, registry, org_a, rotation
):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    old = issue(admin_client, registry) if rotation else None
    revision = 2 if rotation else 1
    barrier = Barrier(2)
    headers = dict(admin_client._credentials)

    def attempt():
        try:
            connection.ensure_connection()
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                pid = cursor.fetchone()[0]
            client = APIClient()
            client.credentials(**headers)
            barrier.wait(timeout=10)
            data = {
                "expected_revision": revision,
                "expires_at": (timezone.now() + timedelta(days=1)).isoformat(),
                "scopes": ["integration.probe"],
            }
            if old:
                data.update(replaces_id=old["id"], overlap_seconds=60)
            result = post(client, f"connections/{registry}/credentials/", **data)
            return pid, result.status_code
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(attempt) for _ in range(2)]
        results = [future.result(timeout=20) for future in futures]
    assert len({pid for pid, _ in results}) == 2
    assert sorted(status for _, status in results) == [201, 409]
    with rls_org(org_a):
        assert Credential.objects.filter(connection_id=registry).count() == (
            2 if old else 1
        )
        assert Connection.objects.get(id=registry).revision == revision + 1


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("request_kind", ["probe", "issue"])
def test_probe_waits_for_committed_revocation(
    admin_client, registry, org_a, admin_profile, request_kind
):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from common.models import Org
    from integrations.services import command

    key = issue(admin_client, registry)
    waiting = Event()

    def probe():
        def observe(execute, sql, params, many, context):
            if '"organization"' in sql and "FOR UPDATE" in sql:
                waiting.set()
            return execute(sql, params, many, context)

        try:
            with connection.execute_wrapper(observe):
                if request_kind == "issue":
                    client = APIClient()
                    client.credentials(**admin_client._credentials)
                    return post(
                        client,
                        f"connections/{registry}/credentials/",
                        expected_revision=2,
                        expires_at=(timezone.now() + timedelta(days=1)).isoformat(),
                        scopes=["integration.probe"],
                    ).status_code
                return (
                    service(key["credential"]).get(ROOT + "service/probe/").status_code
                )
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=1) as pool:
        with tenant_transaction(org_a.id):
            # Match the HTTP boundary's practice-before-connection lock order.
            Org.objects.select_for_update().get(id=org_a.id)
            Connection.objects.select_for_update().get(id=registry)
            future = pool.submit(probe)
            assert waiting.wait(timeout=10), (
                "Probe never reached the held practice lock"
            )
            assert not future.done()
            command(
                admin_profile,
                "state",
                {
                    "request_id": uuid4(),
                    "expected_revision": 2,
                    "target": "revoked",
                    "reason_code": "compromise",
                },
                connection_id=registry,
            )
        assert future.result(timeout=10) == (401 if request_kind == "probe" else 409)
    with rls_org(org_a):
        assert Credential.objects.get(id=key["id"]).revoked_at is not None


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("failure_at", [1, 2])
def test_context_failure_cannot_contaminate_next_connection(org_a, failure_at):
    from concurrent.futures import ThreadPoolExecutor

    def attempt():
        calls = 0

        def fail(execute, sql, params, many, context):
            nonlocal calls
            result = execute(sql, params, many, context)
            if "set_config('app.current_org'" in sql:
                calls += 1
                if calls == failure_at:
                    raise RuntimeError("synthetic context failure")
            return result

        try:
            with connection.execute_wrapper(fail):
                with pytest.raises(RuntimeError, match="synthetic context failure"):
                    with tenant_transaction(org_a.id):
                        pass
            discarded = connection.connection is None
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_setting('app.current_org',true)")
                remaining = cursor.fetchone()[0]
            return discarded, remaining
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=1) as pool:
        discarded, remaining = pool.submit(attempt).result(timeout=15)
    assert not remaining
    if failure_at == 2:
        assert discarded, "A failed context reset must discard the connection"


def test_unexpected_exception_never_logs_credential(admin_client, registry, caplog):
    key = issue(admin_client, registry)
    before = Audit.objects.count()
    admin_client.raise_request_exception = False
    with patch(
        "integrations.views.command", side_effect=RuntimeError(key["credential"])
    ):
        response = post(
            admin_client,
            f"connections/{registry}/state/",
            expected_revision=2,
            target="paused",
            reason_code="maintenance",
        )
    exposed = (
        key["credential"] in caplog.text
        or key["credential"] in response.content.decode()
    )
    assert not exposed, "A synthetic credential reached the error response or logs"
    assert response.status_code == 503
    assert Audit.objects.count() == before
    assert Connection.objects.get(id=registry).status == "active"


@pytest.mark.parametrize(
    "selector",
    ["org", "org_id", "organization", "organization_id", "tenant", "tenant_id"],
)
@pytest.mark.parametrize("location", ["body", "query"])
def test_unsigned_practice_selectors_rejected_before_context(
    admin_client, registry, org_b, selector, location
):
    key = issue(admin_client, registry)
    for client, path in (
        (admin_client, "namespaces/"),
        (service(key["credential"]), "service/probe/"),
    ):
        with patch("integrations.middleware.tenant_transaction") as context:
            if location == "body":
                result = client.generic(
                    "GET",
                    ROOT + path,
                    json.dumps({selector: str(org_b.pk)}),
                    content_type="application/json",
                )
            else:
                result = client.get(ROOT + path, {selector: str(org_b.pk)})
            assert result.status_code == 403
            context.assert_not_called()
    assert Namespace.objects.count() == 1


def test_monitoring_uses_only_bounded_reasons_and_server_ids(caplog):
    from uuid import UUID

    from integrations.monitoring import failure_counts

    before = failure_counts()
    client = service("mpis1.synthetic-credential-canary")
    with patch("integrations.middleware.tenant_transaction") as context:
        results = [
            client.get(
                ROOT + "service/probe/", HTTP_X_INTEGRATION_REQUEST_ID="caller-canary"
            )
            for _ in range(2)
        ]
        context.assert_not_called()
    ids = [result["X-Integration-Request-ID"] for result in results]
    assert len(set(ids)) == 2
    assert all(UUID(value).version == 4 for value in ids)
    assert all(result.status_code == 401 for result in results)
    assert "caller-canary" not in caplog.text
    assert "synthetic-credential-canary" not in caplog.text
    assert all(value in caplog.text for value in ids)
    after = failure_counts()
    assert after["invalid_authentication"] == before["invalid_authentication"] + 2
    assert set(after) == {
        "invalid_authentication",
        "authorization_denied",
        "unavailable_route",
        "service_unavailable",
        "request_rejected",
    }


def test_monitoring_counter_saturates_without_new_labels():
    from integrations import monitoring

    with patch.dict(monitoring._COUNTS, invalid_authentication=monitoring._MAX_COUNT):
        monitoring.record_failure(401)
        assert (
            monitoring.failure_counts()["invalid_authentication"]
            == monitoring._MAX_COUNT
        )


def test_same_practice_selector_is_not_silently_ignored(admin_client, org_a):
    response = post(
        admin_client,
        "namespaces/",
        provider_key="fixture_a",
        account_key="test_selector",
        org_id=str(org_a.pk),
    )
    assert response.status_code == 403
    assert Namespace.objects.count() == 0


def test_validation_errors_never_echo_credentials(admin_client, registry, caplog):
    key = issue(admin_client, registry)
    result = post(
        admin_client,
        f"connections/{registry}/credentials/",
        expected_revision=2,
        expires_at=(timezone.now() + timedelta(days=1)).isoformat(),
        scopes=[key["credential"]],
    )
    assert result.status_code == 400
    assert result.json() == {"detail": "Invalid command."}
    assert key["credential"] not in caplog.text
    assert result["Cache-Control"] == "private, no-store"
    assert result["X-Integration-Request-ID"]


def test_signing_key_replacement_and_fallback_never_bypass_revocation(
    admin_client, registry
):
    from django.conf import settings

    old = issue(admin_client, registry)
    first_secret = settings.SECRET_KEY
    with override_settings(
        INTEGRATION_SIGNING_KEYS={
            "1": first_secret,
            "2": "fictional-replacement-signing-key-at-least-32",
        },
        INTEGRATION_SIGNING_KEY_VERSION="2",
    ):
        new = issue(admin_client, registry, replaces_id=old["id"], overlap_seconds=60)
        assert (
            service(old["credential"]).get(ROOT + "service/probe/").status_code == 200
        )
        assert (
            service(new["credential"]).get(ROOT + "service/probe/").status_code == 200
        )
        with override_settings(
            INTEGRATION_SIGNING_KEYS={
                "2": "fictional-replacement-signing-key-at-least-32"
            }
        ):
            assert (
                service(old["credential"]).get(ROOT + "service/probe/").status_code
                == 401
            )
            assert (
                service(new["credential"]).get(ROOT + "service/probe/").status_code
                == 200
            )
        revoked = post(
            admin_client,
            f"connections/{registry}/state/",
            expected_revision=3,
            target="revoked",
            reason_code="compromise",
        )
        assert revoked.status_code == 200
        assert (
            service(old["credential"]).get(ROOT + "service/probe/").status_code == 401
        )
        assert (
            service(new["credential"]).get(ROOT + "service/probe/").status_code == 401
        )


def test_no_tenant_context_sees_no_integration_metadata(admin_client, registry):
    issue(admin_client, registry)
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('app.current_org',true)")
        previous = cursor.fetchone()[0] or ""
        cursor.execute("SELECT set_config('app.current_org','',true)")
        try:
            for model in (Namespace, Connection, Credential, Audit):
                assert not model.objects.exists()
        finally:
            cursor.execute("SELECT set_config('app.current_org',%s,true)", [previous])


def test_disabled_practice_denies_existing_credential(admin_client, registry, org_a):
    key = issue(admin_client, registry)
    client = service(key["credential"])
    assert client.get(ROOT + "service/probe/").status_code == 200
    org_a.is_active = False
    org_a.save(update_fields=["is_active"])
    assert client.get(ROOT + "service/probe/").status_code == 401


@pytest.mark.parametrize("offset,expected", [(-1, 200), (0, 401), (1, 401)])
def test_exact_expiry_boundary_without_retirement(
    admin_client, registry, offset, expected
):
    key = issue(admin_client, registry)
    credential = Credential.objects.get(id=key["id"])
    assert credential.retire_at is None and credential.revoked_at is None
    with patch(
        "integrations.authentication.timezone.now",
        return_value=credential.expires_at + timedelta(seconds=offset),
    ):
        assert (
            service(key["credential"]).get(ROOT + "service/probe/").status_code
            == expected
        )


def test_revocation_retry_preserves_existing_retirement_fact(admin_client, registry):
    old = issue(admin_client, registry)
    issue(admin_client, registry, replaces_id=old["id"], overlap_seconds=60)
    cutoff = Credential.objects.get(id=old["id"]).retire_at.isoformat()
    command_id = str(uuid4())
    path = f"connections/{registry}/credentials/{old['id']}/revoke/"
    results = [
        post(
            admin_client,
            path,
            request_id=command_id,
            expected_revision=3,
            reason_code="retired",
        )
        for _ in range(2)
    ]
    assert all(result.status_code == 200 for result in results)
    assert results[0].json() == results[1].json()
    assert results[0].json()["retire_at"] == cutoff
    assert results[0].json()["revoked_at"] is not None
