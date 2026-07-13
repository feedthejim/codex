"""OIDCSettings admin serializers."""

from typing import override

from rest_framework.exceptions import ValidationError
from rest_framework.fields import SerializerMethodField
from rest_framework.serializers import BooleanField, CharField, Serializer, URLField

from codex.models import OIDCSettings
from codex.serializers.models.base import BaseModelSerializer

_ENABLE_REQUIRES_MSG = (
    "OIDC login cannot be enabled without a provider name,"
    " a server URL, and a client ID."
)


class OIDCSettingsSerializer(BaseModelSerializer):
    """Serializer for the OIDCSettings singleton."""

    # Secret is write-only — clients see whether one is set, not the value.
    client_secret = CharField(write_only=True, required=False, allow_blank=True)
    client_secret_set = SerializerMethodField()

    @staticmethod
    def get_client_secret_set(obj) -> bool:
        """Whether an OIDC client secret has been configured."""
        return bool(obj.client_secret)

    @override
    def validate(self, attrs):
        """
        Reject an enabled-but-unconfigured state.

        The UI disables the enable switch until a provider name, server
        URL, and client ID are present; this enforces the same invariant
        for API clients and for partial updates that blank a prerequisite
        while leaving ``enabled`` on. Merges the incoming fields over the
        saved row so partial PUTs validate against the effective result.
        """
        merged = {
            field: attrs.get(field, getattr(self.instance, field, ""))
            for field in ("enabled", "provider_name", "server_url", "client_id")
        }
        if merged["enabled"] and not (
            merged["provider_name"] and merged["server_url"] and merged["client_id"]
        ):
            raise ValidationError({"enabled": _ENABLE_REQUIRES_MSG})
        return attrs

    class Meta(BaseModelSerializer.Meta):
        """Specify model and fields."""

        model = OIDCSettings
        fields = (
            "enabled",
            "provider_name",
            "server_url",
            "client_id",
            "client_secret",
            "client_secret_set",
            "scope",
            "pkce",
            "token_auth_method",
            "fetch_userinfo",
            "username_claim",
            "create_users",
            "link_by_email",
            "sync_groups",
            "groups_claim",
            "admin_group",
            "rp_initiated_logout",
        )
        read_only_fields = ("client_secret_set",)


class OIDCTestRequestSerializer(Serializer):
    """
    Request body for the OIDC Test Connection endpoint.

    ``server_url`` is optional: when present it overrides the saved row
    for this one probe, so an admin can validate an issuer URL before
    saving it (the email Test Send pattern).
    """

    server_url = URLField(required=False, allow_blank=True)


class OIDCTestResponseSerializer(Serializer):
    """Test-connection outcome: which endpoints the provider advertises."""

    ok = BooleanField()
    error = CharField(allow_null=True, required=False, default=None)
    issuer = CharField(allow_null=True, required=False, default=None)
    authorization_endpoint = BooleanField(required=False, default=False)
    token_endpoint = BooleanField(required=False, default=False)
    userinfo_endpoint = BooleanField(required=False, default=False)
    end_session_endpoint = BooleanField(required=False, default=False)
