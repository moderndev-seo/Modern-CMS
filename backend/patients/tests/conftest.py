"""Existing staff workflow scenarios explicitly grant patient capabilities.

Fresh profiles still default to no access; authorization regressions construct
unprivileged profiles separately. Finance remains an independent grant.
"""

import pytest

from common.models import Profile


@pytest.fixture
def user_profile(regular_user, org_a):
    return Profile.objects.create(
        user=regular_user,
        org=org_a,
        role="USER",
        is_active=True,
        has_patient_access=True,
        can_record_patient_outcomes=True,
        has_marketing_access=True,
    )
