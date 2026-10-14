"""Practice capabilities supplement (never replace) contact ownership/sharing."""

from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import SAFE_METHODS, BasePermission

from common.permissions import is_org_admin


def can_access_patients(profile):
    return bool(
        profile
        and profile.is_active
        and getattr(profile, "_patient_credential_allowed", True)
        and (is_org_admin(profile) or profile.has_patient_access)
    )


def can_record_outcomes(profile):
    return can_access_patients(profile) and (
        is_org_admin(profile) or profile.can_record_patient_outcomes
    )


def can_read_finance(profile):
    return can_access_patients(profile) and (
        is_org_admin(profile) or profile.has_patient_finance_access
    )


def require_outcomes(profile):
    if not can_record_outcomes(profile):
        raise PermissionDenied("Patient outcome recording permission is required.")


class PatientPermission(BasePermission):
    """Fail closed on every patient route, including inboxes and history."""

    def has_permission(self, request, view):
        profile = getattr(request, "profile", None)
        if not profile or not profile.is_active:
            return False
        if getattr(view, "aggregate_only", False):
            return is_org_admin(profile) or (
                request.method in SAFE_METHODS and profile.has_marketing_access
            )
        return can_access_patients(profile)
