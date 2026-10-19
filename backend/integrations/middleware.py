"""Authenticate new routes before legacy dispatch; no broad RLS exemption."""

import json

from django.core.exceptions import RequestDataTooBig
from django.db import transaction
from django.http import JsonResponse
from rest_framework.exceptions import APIException
from rest_framework_simplejwt.tokens import AccessToken

from common.models import Org, Profile
from integrations.authentication import (
    ServicePrincipal,
    decode,
    enabled,
    resolve_service,
    tenant_transaction,
)
from integrations.monitoring import record_failure

ROOT = "/api/integrations/v1/"
PROBE = ROOT + "service/probe/"


def response(detail, status):
    result = JsonResponse({"detail": detail}, status=status)
    result["Cache-Control"] = "private, no-store"
    if status >= 400:
        result["X-Integration-Request-ID"] = record_failure(status)
    return result


TENANT_SELECTORS = {
    "org",
    "org_id",
    "organization",
    "organization_id",
    "tenant",
    "tenant_id",
}


def reject_unsigned_selectors(request):
    # These routes never accept a caller-selected practice. Even a matching
    # selector is rejected rather than silently ignored; only verified claims
    # select the RLS context. Inspect bounded JSON before any tenant lookup.
    if any(key.lower() in TENANT_SELECTORS for key in request.GET):
        return response("Organization selectors are not allowed.", 403)
    try:
        if int(request.META.get("CONTENT_LENGTH") or 0) > 16384:
            return response("Command exceeds 16 KiB.", 400)
        body = request.body
        if len(body) > 16384:
            return response("Command exceeds 16 KiB.", 400)
        if body:
            if request.content_type != "application/json":
                return response("JSON body required.", 400)
            data = json.loads(body)
            if isinstance(data, dict) and any(
                key.lower() in TENANT_SELECTORS for key in data
            ):
                return response("Organization selectors are not allowed.", 403)
    except (ValueError, UnicodeError, RequestDataTooBig):
        return response("Invalid command body.", 400)
    return None


class IntegrationContext:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        header = request.headers.get("Authorization", "")
        token_header = request.headers.get("Token", "")
        parts = header.split()
        raw = parts[1] if len(parts) == 2 and parts[0].lower() == "bearer" else ""
        service = raw.startswith("mpis1") or token_header.startswith("mpis1")
        if not request.path.startswith(ROOT):
            if service:
                return response("This credential is not valid for this endpoint.", 403)
            return self.get_response(request)
        if header and token_header:
            return response("Mixed credentials are not allowed.", 403)
        if service and (request.path != PROBE or request.method != "GET"):
            return response("This credential is not valid for this endpoint.", 403)
        if token_header:
            return response("Human session required.", 403)
        if not raw:
            return response("Bearer authentication required.", 401)
        try:
            if service:
                claims = decode(raw)
                org_id = claims["org"]
            else:
                if raw.startswith("bcrm_pat_") or token_header:
                    return response("Human session required.", 403)
                token = AccessToken(raw)
                if token.get("token_type") != "access" or not token.get("user_id"):
                    return response("Human session required.", 403)
                org_id = token["org_id"]
        except Exception:
            return response("Invalid credential.", 401)
        if not enabled(org_id):
            return response("Not found.", 404)
        if any(
            h in request.headers and request.headers[h] != str(org_id)
            for h in ("Org", "X-Org-Id", "X-Organization-Id")
        ):
            return response("Conflicting organization.", 403)
        rejected = reject_unsigned_selectors(request)
        if rejected is not None:
            return rejected
        try:
            with tenant_transaction(org_id):
                org = (
                    Org.objects.select_for_update()
                    .filter(pk=org_id, is_active=True)
                    .first()
                )
                if org is None:
                    return response("Invalid credential.", 401)
                request.org = org
                request.profile = None
                request.integration_principal = None
                if service:
                    conn, credential = resolve_service(raw, claims)
                    request.integration_principal = ServicePrincipal(
                        str(conn.id), str(credential.id)
                    )
                    request.integration_connection = conn
                else:
                    profile = (
                        Profile.objects.select_for_update()
                        .select_related("user")
                        .filter(
                            org=org,
                            user_id=token["user_id"],
                            is_active=True,
                            user__is_active=True,
                            role="ADMIN",
                        )
                        .first()
                    )
                    if profile is None or request.path == PROBE:
                        return response("Human practice administrator required.", 403)
                    request.profile = profile
                request._integration_verified = True
                result = self.get_response(request)
                if result.status_code >= 500:
                    # Django may convert a view exception into a response before
                    # it reaches this boundary. Do not commit partial work.
                    transaction.set_rollback(True)
                    return response("Integration service temporarily unavailable.", 503)
                result["Cache-Control"] = "private, no-store"
                if result.status_code >= 400:
                    result["X-Integration-Request-ID"] = record_failure(
                        result.status_code
                    )
                return result
        except APIException as exc:
            return response("Invalid integration credential.", exc.status_code)
        except Exception:
            # No raw token, database error or patient data in logs/responses.
            return response("Integration service temporarily unavailable.", 503)
        finally:
            request._integration_verified = False
