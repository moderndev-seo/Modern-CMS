"""Shared pytest fixtures for Django CRM backend tests.

The definitions live in :mod:`common.testing` so that they ship inside the
wheel; see that module's docstring for why. This file re-exports them so pytest
discovers the fixtures at the repository root and so the twenty test modules
that already say ``from conftest import rls_org`` keep working.

Every name is listed explicitly rather than star-imported. A star import skips
names beginning with an underscore, which would silently drop
``_use_db`` and ``_restore_rls_context_after_each_request``: both are
``autouse``, so losing them does not fail loudly, it just stops granting
database access and stops restoring the RLS context after each request. That is
not a hypothetical. The enterprise suite re-exported this file with
``from community_conftest import *`` and has been missing both fixtures the
whole time.
"""

import pytest

from common.testing import (  # noqa: F401
    _make_authenticated_client,
    _restore_rls_context_after_each_request,
    _use_db,
    admin_client,
    admin_profile,
    admin_user,
    clear_rls_context,
    org_a,
    org_b,
    org_b_client,
    profile_b,
    regular_user,
    restore_rls_context,
    rls_org,
    set_rls_context,
    unauthenticated_client,
    user_b,
    user_client,
    user_profile,
)


def pytest_collection_modifyitems(items):
    """Patient workflows depend on PostgreSQL triggers, not SQLite emulation.

    Route the entire app (including future test modules) to the policy-bound
    security job. Other PostgreSQL tests keep their explicit module/test marks.
    No test is skipped here: CI selects the complementary two partitions.
    """
    from pathlib import Path

    import pytest

    patient_tests = Path(__file__).parent / "patients" / "tests"
    for item in items:
        if item.path.is_relative_to(patient_tests):
            item.add_marker(pytest.mark.postgres_only)


@pytest.fixture(autouse=True)
def _verify_security_database_role(request, db):
    if not request.node.get_closest_marker("postgres_only"):
        return
    from django.db import connection

    assert connection.vendor == "postgresql", (
        "Select -m 'not postgres_only' for SQLite; security tests require PostgreSQL."
    )
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user"
        )
        assert cursor.fetchone() == (False, False), (
            "Security tests require a non-superuser NOBYPASSRLS role."
        )
