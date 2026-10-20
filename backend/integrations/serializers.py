from rest_framework import serializers

from integrations.manifests import ALL_MANIFESTS


class StrictCommand(serializers.Serializer):
    request_id = serializers.UUIDField()

    def to_internal_value(self, data):
        if not isinstance(data, dict) or set(data) - set(self.fields):
            raise serializers.ValidationError(
                {"non_field_errors": ["Unknown command fields."]}
            )
        return super().to_internal_value(data)


class NamespaceCommand(StrictCommand):
    provider_key = serializers.ChoiceField(choices=["fixture_a", "fixture_b"])
    account_key = serializers.RegexField(r"^test_[A-Za-z0-9_-]{1,123}$", max_length=128)


class ConnectionCommand(StrictCommand):
    namespace_id = serializers.UUIDField()
    label = serializers.RegexField(
        r"^[A-Za-z0-9 _.-]{1,100}$",
        max_length=100,
        help_text="Operator label only; never enter patient information.",
    )
    manifest_id = serializers.ChoiceField(choices=list(ALL_MANIFESTS))


class RevisionCommand(StrictCommand):
    expected_revision = serializers.IntegerField(min_value=1)


class StateCommand(RevisionCommand):
    target = serializers.ChoiceField(choices=["active", "paused", "revoked"])
    reason_code = serializers.ChoiceField(
        choices=["maintenance", "resume", "compromise", "retired", "operator_revoke"]
    )


class IssueCommand(RevisionCommand):
    expires_at = serializers.DateTimeField()
    scopes = serializers.ListField(
        child=serializers.ChoiceField(
            choices=["integration.probe", "integration.receive"]
        ),
        min_length=1,
        max_length=1,
    )
    replaces_id = serializers.UUIDField(required=False)
    overlap_seconds = serializers.IntegerField(
        min_value=0, max_value=86400, required=False, default=0
    )


class RevokeCommand(RevisionCommand):
    reason_code = serializers.ChoiceField(
        choices=["retired", "operator_revoke", "compromise"]
    )
