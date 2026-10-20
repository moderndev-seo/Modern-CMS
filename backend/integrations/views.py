import logging

from django.db import connection, transaction
from rest_framework.exceptions import (
    APIException,
    NotFound,
    PermissionDenied,
    ValidationError,
)
from rest_framework.parsers import JSONParser
from rest_framework.response import Response
from rest_framework.views import APIView

from integrations.authentication import IntegrationAuthentication
from integrations.models import IntegrationAuditEvent as Audit
from integrations.models import IntegrationConnection as Connection
from integrations.models import IntegrationCredential as Credential
from integrations.models import ProviderNamespace as Namespace
from integrations.serializers import (
    ConnectionCommand,
    IssueCommand,
    NamespaceCommand,
    RevokeCommand,
    StateCommand,
)
from integrations.services import (
    command,
    connection_data,
    credential_data,
    namespace_data,
)


class BoundedIntegrationView(APIView):
    def handle_exception(self, exc):
        if isinstance(exc, ValidationError):
            # Choice-field errors can quote caller-supplied values. Never echo
            # possible credentials or patient data from a rejected command.
            return Response({"detail": "Invalid command."}, status=400)
        if isinstance(exc, APIException):
            return super().handle_exception(exc)
        # Do not let Django's uncaught-exception logger serialize exception
        # text or request data containing a one-time service credential.
        if connection.in_atomic_block:
            transaction.set_rollback(True)
        logging.getLogger(__name__).error("Integration request failed unexpectedly.")
        return Response(
            {"detail": "Integration service temporarily unavailable."}, status=503
        )


class MetadataView(BoundedIntegrationView):
    authentication_classes = [IntegrationAuthentication]
    parser_classes = [JSONParser]
    permission_classes = []
    http_method_names = ["get", "post", "options"]
    kind = None

    def initial(self, request, *args, **kwargs):
        super().initial(request, *args, **kwargs)
        if request.method == "POST" and len(request.body) > 16384:
            raise ValidationError("Command exceeds 16 KiB.")
        if getattr(request, "integration_principal", None) is not None:
            raise PermissionDenied("Human administrator required.")

    def post(self, request, connection_id=None, credential_id=None, **kwargs):
        serializer_type = {
            "namespace": NamespaceCommand,
            "connection": ConnectionCommand,
            "state": StateCommand,
            "issue": IssueCommand,
            "revoke": RevokeCommand,
        }.get(self.kind)
        if serializer_type is None or kwargs.get("object_id"):
            from rest_framework.exceptions import MethodNotAllowed

            raise MethodNotAllowed("POST")
        serializer = serializer_type(data=request.data)
        serializer.is_valid(raise_exception=True)
        result, status = command(
            request.profile,
            self.kind,
            serializer.validated_data,
            connection_id,
            credential_id,
        )
        return Response(result, status=status)

    def get(self, request, object_id=None, connection_id=None, **kwargs):
        if self.kind in ("state", "revoke"):
            from rest_framework.exceptions import MethodNotAllowed

            raise MethodNotAllowed("GET")
        if (
            connection_id
            and not Connection.objects.filter(
                org=request.org, id=connection_id
            ).exists()
        ):
            raise NotFound()
        if self.kind == "namespace":
            qs, render = Namespace.objects.filter(org=request.org), namespace_data
        elif self.kind == "connection":
            qs, render = Connection.objects.filter(org=request.org), connection_data
        elif self.kind == "issue":
            qs, render = (
                Credential.objects.filter(org=request.org, connection_id=connection_id),
                credential_data,
            )
        else:
            qs = Audit.objects.filter(org=request.org, connection_id=connection_id)

            def render(row):
                return {
                    "id": str(row.id),
                    "action": row.action,
                    "reason_code": row.reason_code,
                    "actor_profile_id": str(row.actor_profile_id),
                    "credential_id": str(row.credential_id)
                    if row.credential_id
                    else None,
                    "occurred_at": row.occurred_at.isoformat(),
                    "details": row.details,
                    "previous_generation": row.previous_generation,
                    "new_generation": row.new_generation,
                }

        if object_id:
            row = qs.filter(id=object_id).first()
            if not row:
                raise NotFound()
            return Response(
                namespace_data(row, detail=True)
                if self.kind == "namespace"
                else render(row)
            )
        try:
            limit = min(100, max(1, int(request.query_params.get("limit", 50))))
            offset = max(0, int(request.query_params.get("offset", 0)))
        except ValueError:
            raise ValidationError("Invalid pagination.") from None
        return Response(
            {
                "count": qs.count(),
                "results": [
                    render(row)
                    for row in qs.order_by("created_at", "id")[offset : offset + limit]
                ],
            }
        )


class ProbeView(BoundedIntegrationView):
    authentication_classes = [IntegrationAuthentication]
    permission_classes = []
    http_method_names = ["get"]

    def get(self, request):
        if not getattr(request, "integration_principal", None):
            raise PermissionDenied()
        conn = request.integration_connection
        return Response(
            {
                "connection_id": str(conn.id),
                "mode": "fictional",
                "manifest_id": conn.capabilities["id"],
                "manifest_version": conn.manifest_version,
                "permitted_action": "integration.probe",
            }
        )


class ReceiveView(BoundedIntegrationView):
    authentication_classes = [IntegrationAuthentication]
    permission_classes = []
    http_method_names = ["post"]

    def post(self, request):
        if not getattr(request, "integration_principal", None):
            raise PermissionDenied()
        from integrations.acceptance import accept_delivery

        result, status = accept_delivery(
            request.body, request.integration_connection, request.integration_credential
        )
        return Response(result, status=status)
