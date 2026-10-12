import json
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import OperationalError

from patients.management.commands import check_practice_setup as setup


@pytest.fixture(autouse=True)
def _use_db():
    """Catalog and migration inputs are mocked; no database setup is needed."""


@pytest.fixture(autouse=True)
def _restore_rls_context_after_each_request():
    """No real connection or tenant context is used by these command tests."""


@pytest.fixture
def local_setup(settings, monkeypatch):
    settings.EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
    db = MagicMock(vendor="postgresql")
    cursor = db.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (False, False)
    cursor.fetchall.return_value = [
        ("mp_patient", True, True, [setup.ISOLATION_POLICY, setup.INSERT_POLICY])
    ]
    executor = MagicMock()
    executor.migration_plan.return_value = []
    monkeypatch.setattr(setup, "connection", db)
    monkeypatch.setattr(setup, "ORG_SCOPED_TABLES", ["mp_patient"])
    monkeypatch.setattr(setup, "MigrationExecutor", lambda _: executor)
    return cursor, executor


def test_local_setup_json_success_is_read_only(local_setup):
    output = StringIO()
    call_command("check_practice_setup", "--json", stdout=output)
    result = json.loads(output.getvalue())
    assert result["passed"]
    cursor, _ = local_setup
    assert all(
        call.args[0].lstrip().startswith("SELECT")
        for call in cursor.execute.call_args_list
    )
    assert "production readiness" in result["scope"]


@pytest.mark.parametrize("role", [(True, False), (False, True), None])
def test_unsafe_or_missing_role_fails(local_setup, role):
    local_setup[0].fetchone.return_value = role
    with pytest.raises(CommandError, match="checks failed"):
        call_command("check_practice_setup", stdout=StringIO())


@pytest.mark.parametrize(
    "tables",
    [
        [],
        [("mp_patient", False, True, [])],
        [("mp_patient", True, False, [])],
        [("mp_patient", True, True, [setup.ISOLATION_POLICY])],
    ],
)
def test_missing_table_or_rls_protection_fails(local_setup, tables):
    local_setup[0].fetchall.return_value = tables
    with pytest.raises(CommandError, match="checks failed"):
        call_command("check_practice_setup", stdout=StringIO())


def test_pending_migrations_and_nonlocal_email_fail(local_setup, settings):
    local_setup[1].migration_plan.return_value = [object()]
    settings.EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    output = StringIO()
    with pytest.raises(CommandError):
        call_command("check_practice_setup", "--json", stdout=output)
    failed = {
        x["check"] for x in json.loads(output.getvalue())["checks"] if not x["passed"]
    }
    assert failed == {"migrations", "local_email"}


def test_database_failure_does_not_echo_configuration(local_setup):
    local_setup[0].execute.side_effect = OperationalError("private-connection-value")
    with pytest.raises(CommandError) as error:
        call_command("check_practice_setup", stdout=StringIO())
    assert "private-connection-value" not in str(error.value)


def test_non_postgresql_fails_without_database_queries(local_setup):
    with patch.object(setup.connection, "vendor", "sqlite"):
        with pytest.raises(CommandError):
            call_command("check_practice_setup", stdout=StringIO())
    local_setup[0].execute.assert_not_called()
