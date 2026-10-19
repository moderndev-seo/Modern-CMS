"""Prove CI's SQLite/PostgreSQL partitions cover every collected backend test.

Run from the repository root using the backend environment. Collection performs
no test writes. A subprocess per partition avoids pytest plugin state reuse.
"""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def collect(marker=None):
    command = [sys.executable, "-m", "pytest", "--collect-only", "--no-cov", "-qq"]
    if marker:
        command += ["-m", marker]
    result = subprocess.run(
        command,
        cwd=ROOT / "backend",
        env={**os.environ, "DJANGO_SETTINGS_MODULE": "crm.test_settings"},
        text=True,
        capture_output=True,
    )
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    return {
        line.strip()
        for line in result.stdout.splitlines()
        if "::" in line and not line.startswith(" ")
    }


if __name__ == "__main__":
    all_tests = collect()
    sqlite = collect("not postgres_only")
    security = collect("postgres_only")
    assert all_tests and sqlite and security, "A test partition is empty"
    assert not sqlite & security, "CI partitions overlap"
    assert sqlite | security == all_tests, "CI silently loses tests"
    patients = {test for test in all_tests if test.startswith("patients/tests/")}
    assert patients and patients <= security, (
        "Patient tests escaped the policy-bound PostgreSQL job"
    )
    integrations = {
        test for test in all_tests if test.startswith("integrations/tests/")
    }
    assert integrations and integrations <= security, (
        "Integration tests escaped restricted PostgreSQL"
    )
    legacy_security = {
        test
        for test in all_tests
        if test.startswith(
            (
                "common/tests/test_multitenancy.py::TestRLSIntegration::",
                "common/tests/test_pool_rls_isolation.py::",
            )
        )
    }
    assert len(legacy_security) >= 8 and legacy_security <= security, (
        "Legacy tenant/pool checks escaped the restricted PostgreSQL job"
    )
    print(
        f"{len(all_tests)} collected = {len(sqlite)} SQLite-compatible + {len(security)} PostgreSQL security; all {len(patients)} patient cases and {len(integrations)} integration cases routed to security."
    )
