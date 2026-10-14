"""Who may open a contact, and so who may link one to a record.

Extracted from ``ContactDetailView.assert_contact_access`` so the attachment
download view asks the same question rather than carrying a second copy of the
answer. The detail view still calls it.
"""

from django.db.models import Q
from rest_framework.exceptions import PermissionDenied

from common.permissions import is_org_admin
from contacts.models import Contact

_DENIED = "You do not have Permission to perform this action"


def contact_account_ids(contact):
    """Every account this contact is joined to, by either route."""
    accounts = set(contact.account_contacts.values_list("id", flat=True))
    if contact.account_id:
        accounts.add(contact.account_id)
    return accounts


def has_contact_access(profile, contact):
    """Who may work on this person's record.

    One predicate for every verb, because the divergence was the bug. The list
    filter and ``delete`` compared ``created_by`` (a User) against
    ``request.profile.user``, correctly. ``get``, ``put``, ``patch`` and the
    comment endpoint compared it against ``request.profile`` -- a Profile is
    never equal to a User, so those four branches could only ever be False.
    The result a non-admin actually saw: their own contacts listed on the
    index, 403 on opening any of them, and a successful delete on the same
    record they had just been refused a look at.

    Assignment to the account the person belongs to counts as access. Whoever
    owns the company owns the conversation with the people at it, and there is
    no reading under which that is true for viewing but false for editing.

    A Django superuser sees every contact in their own org, as they do every
    account, deal and invoice. The flag is read from ``profile.user``, the
    identity the request authenticated as, so a caller without a request (the
    case CSV import, through `visible_contacts_qs`) gets the same answer. Like
    the admin branch, it does not check the org itself: every caller fetches
    ``contact`` with ``org=profile.org`` first.
    """
    from patients.access import can_access_patients

    if not can_access_patients(profile) and hasattr(contact, "patient"):
        return False
    if is_org_admin(profile) or profile.user.is_superuser:
        return True
    if profile.user_id == contact.created_by_id:
        return True
    if profile.id in {assignee.id for assignee in contact.assigned_to.all()}:
        return True
    my_accounts = set(profile.account_assigned_users.values_list("id", flat=True))
    return bool(my_accounts & contact_account_ids(contact))


def visible_contacts_qs(profile):
    """Contacts ``profile`` may open, the queryset form of `has_contact_access`."""
    from patients.access import can_access_patients

    qs = Contact.objects.filter(org=profile.org)
    if not can_access_patients(profile):
        qs = qs.filter(patient__isnull=True)
    if is_org_admin(profile) or profile.user.is_superuser:
        return qs
    my_accounts = profile.account_assigned_users.values_list("id", flat=True)
    return qs.filter(
        Q(created_by=profile.user)
        | Q(assigned_to=profile)
        | Q(account_contacts__id__in=my_accounts)
        | Q(account_id__in=my_accounts)
    ).distinct()


def replace_visible_contacts(related, contact_ids, profile):
    """Set the contacts in ``related`` to ``contact_ids``, as far as
    ``profile`` can see them.

    ``related`` is a record's contacts manager (``account.contacts``,
    ``deal.contacts``, ``case.contacts``, ``lead.contacts``). Every write path
    that links contacts by id comes through here, on create and on replace.

    An id the caller may not open is dropped, not linked, and the write still
    succeeds, as it does for an id from another org. Linking it would hand
    the caller a copy: through account assignment it becomes theirs to open,
    and the other records nest their contacts in full.

    Contacts already linked that the caller may not open stay linked. The
    caller's form only ever held the ones they can see, so its list says
    nothing about the rest. For an admin every contact in the org is visible,
    so this is a plain replace; on a new record nothing is linked yet, so it
    links the visible ids.
    """
    visible = visible_contacts_qs(profile)
    kept = related.exclude(id__in=visible.values("id"))
    wanted = visible.filter(id__in=contact_ids) if contact_ids else []
    related.set([*kept, *wanted])


def assert_contact_access(profile, contact):
    """Raise 403 unless ``profile`` may open ``contact``."""
    if not has_contact_access(profile, contact):
        raise PermissionDenied(_DENIED)


def may_serialize_contact(contact, context):
    """Fail closed for patient identity in nested/picker/contact serializers."""
    if not hasattr(contact, "patient"):
        return True
    request = context.get("request")
    profile = context.get("profile") or getattr(request, "profile", None)
    return bool(
        profile
        and contact.org_id == profile.org_id
        and has_contact_access(profile, contact)
    )


def restricted_patient_contacts(profile, *, financial=False):
    """Patient links that must hide a shared CRM record's body as well as its name."""
    from patients.access import can_read_finance

    patients = Contact.objects.filter(org=profile.org, patient__isnull=False)
    if financial and not can_read_finance(profile):
        return patients
    return patients.exclude(pk__in=visible_contacts_qs(profile).values("pk"))


def patient_link_queryset(queryset, profile, *, financial=False):
    return queryset.exclude(
        contacts__in=restricted_patient_contacts(profile, financial=financial)
    )


def has_patient_link_access(profile, record, *, financial=False):
    return not record.contacts.filter(
        pk__in=restricted_patient_contacts(profile, financial=financial)
    ).exists()


def assert_generic_patient_access(profile, interaction):
    """Keep patient restrictions on generic comment/attachment mutation routes.

    Legacy routes accept generic IDs across CRM modules. Inspect the actual
    parent, not the endpoint name; unrelated records retain their own rules.
    """
    if interaction is None:
        return
    parent = interaction.content_object
    if parent is None:
        return
    model = interaction.content_type.model
    if model == "contact" and hasattr(parent, "patient"):
        assert_contact_access(profile, parent)
    elif model in {"case", "task", "lead", "opportunity"}:
        if not has_patient_link_access(
            profile, parent, financial=model in {"lead", "opportunity"}
        ):
            raise PermissionDenied(_DENIED)
    elif model == "invoice" and parent.contact_id:
        from patients.access import can_read_finance

        if hasattr(parent.contact, "patient") and (
            not can_read_finance(profile)
            or not has_contact_access(profile, parent.contact)
        ):
            raise PermissionDenied(_DENIED)
