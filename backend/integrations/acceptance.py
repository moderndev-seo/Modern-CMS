"""Transactional fictional delivery acceptance; no worker/domain effects."""

from uuid import uuid4

from django.db import connection, transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from integrations.ingress import seal_envelope, validate_envelope
from integrations.models import IntegrationDeliveryConflict as Conflict
from integrations.models import IntegrationEventInbox as Inbox
from integrations.models import IntegrationPendingWork as Pending


def receipt_data(row):
    return {
        "receipt_id": str(row.id),
        "delivery_id": str(row.delivery_id),
        "received_at": row.created_at.isoformat(),
        "status": "accepted",
    }


def accept_delivery(raw, conn, credential):
    # The middleware owns the outer transaction and Org/connection locks.
    # Its commit must finish before a response can reach the caller.
    now = timezone.now()
    if (
        not connection.in_atomic_block
        or credential.connection_id != conn.id
        or credential.org_id != conn.org_id
        or credential.scopes != ["integration.receive"]
        or conn.capabilities.get("ingress") != "fixture.ingress/1"
        or conn.status != "active"
        or conn.mode != "fictional"
        or credential.revoked_at is not None
        or now >= credential.expires_at
        or (credential.retire_at is not None and now >= credential.retire_at)
    ):
        raise PermissionDenied("Receive authority required.")
    envelope, semantic, transport = validate_envelope(
        raw, conn.capabilities["source_class"]
    )
    with transaction.atomic():
        prior = Inbox.objects.filter(
            org_id=conn.org_id,
            namespace_id=conn.namespace_id,
            delivery_id=envelope["delivery_id"],
        ).first()
        if prior:
            if prior.semantic_digest != semantic:
                Conflict.objects.get_or_create(
                    org_id=conn.org_id,
                    inbox=prior,
                    credential=credential,
                    attempted_digest=semantic,
                )
                return {"detail": "Delivery ID conflicts with accepted content."}, 409
            return receipt_data(prior), 200
        receipt_id = uuid4()
        version, ciphertext = seal_envelope(
            envelope,
            receipt_id=receipt_id,
            org_id=conn.org_id,
            semantic_digest=semantic,
        )
        row = Inbox.objects.create(
            id=receipt_id,
            org_id=conn.org_id,
            namespace_id=conn.namespace_id,
            connection=conn,
            credential=credential,
            delivery_id=envelope["delivery_id"],
            manifest_digest=conn.manifest_digest,
            authorization_generation=conn.authorization_generation,
            semantic_digest=semantic,
            transport_digest=transport,
            replay_key_version=version,
            replay_ciphertext=ciphertext,
        )
        Pending.objects.create(org_id=conn.org_id, inbox=row)
        return receipt_data(row), 202
