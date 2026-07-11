"""Tests for the admin OIDC settings endpoints."""

from typing import Final, override
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase

from codex.models.admin import OIDCSettings
from codex.oidc import DISCOVERY_CACHE_KEY

_URL: Final = "/api/v4/admin/oidc-settings"
_TEST_URL: Final = "/api/v4/admin/oidc-settings/test"
_HTTP_OK: Final = 200
_HTTP_BAD_REQUEST: Final = 400
_HTTP_FORBIDDEN: Final = 403
_SECRET: Final = "hush-test-secret"  # noqa: S105


def _data(response) -> dict:
    return response.json()["data"]


class AdminOIDCPermissionTests(TestCase):
    """Only admins may read or write OIDC settings."""

    def test_anonymous_denied(self) -> None:
        assert self.client.get(_URL).status_code == _HTTP_FORBIDDEN
        assert (
            self.client.put(_URL, {}, content_type="application/json").status_code
            == _HTTP_FORBIDDEN
        )
        assert self.client.post(_TEST_URL, {}).status_code == _HTTP_FORBIDDEN

    def test_non_staff_denied(self) -> None:
        user = User.objects.create_user("reader")
        self.client.force_login(user)
        assert self.client.get(_URL).status_code == _HTTP_FORBIDDEN


class AdminOIDCSettingsViewTests(TestCase):
    """GET/PUT round trip with a write-only secret."""

    @override
    def setUp(self) -> None:
        admin = User.objects.create_superuser("admin", "", "admin")
        self.client.force_login(admin)

    def test_get_returns_settings_without_secret(self) -> None:
        OIDCSettings.objects.filter(pk=1).update(client_secret="")
        data = _data(self.client.get(_URL))
        assert data["enabled"] is False
        assert data["providerName"] == "SSO"
        assert data["clientSecretSet"] is False
        assert "clientSecret" not in data

    def test_put_round_trip_and_secret_mirror(self) -> None:
        payload = {
            "enabled": True,
            "providerName": "Authentik",
            "serverUrl": "https://auth.example.com/application/o/codex/",
            "clientId": "codex",
            "clientSecret": _SECRET,
            "scope": "openid profile email groups",
            "syncGroups": True,
        }
        data = _data(self.client.put(_URL, payload, content_type="application/json"))
        assert data["enabled"] is True
        assert data["providerName"] == "Authentik"
        assert data["clientSecretSet"] is True
        assert "clientSecret" not in data
        row = OIDCSettings.objects.get(pk=1)
        assert row.client_secret == _SECRET
        assert row.sync_groups is True

    def test_put_without_secret_keeps_existing_secret(self) -> None:
        OIDCSettings.objects.filter(pk=1).update(client_secret=_SECRET)
        self.client.put(
            _URL, {"providerName": "Renamed"}, content_type="application/json"
        )
        row = OIDCSettings.objects.get(pk=1)
        assert row.client_secret == _SECRET
        assert row.provider_name == "Renamed"

    def test_put_blank_secret_clears_it(self) -> None:
        OIDCSettings.objects.filter(pk=1).update(client_secret=_SECRET)
        data = _data(
            self.client.put(_URL, {"clientSecret": ""}, content_type="application/json")
        )
        assert data["clientSecretSet"] is False
        assert OIDCSettings.objects.get(pk=1).client_secret == ""

    def test_put_enabled_without_prerequisites_is_rejected(self) -> None:
        """enabled=true requires a server URL and client ID (UI mirror)."""
        response = self.client.put(
            _URL, {"enabled": True}, content_type="application/json"
        )
        assert response.status_code == _HTTP_BAD_REQUEST
        assert OIDCSettings.objects.get(pk=1).enabled is False

    def test_put_blanking_prerequisite_while_enabled_is_rejected(self) -> None:
        OIDCSettings.objects.filter(pk=1).update(
            enabled=True, server_url="https://idp.example.com", client_id="codex"
        )
        response = self.client.put(
            _URL, {"serverUrl": ""}, content_type="application/json"
        )
        assert response.status_code == _HTTP_BAD_REQUEST
        assert OIDCSettings.objects.get(pk=1).server_url == "https://idp.example.com"

    def test_put_disable_and_blank_together_is_allowed(self) -> None:
        OIDCSettings.objects.filter(pk=1).update(
            enabled=True, server_url="https://idp.example.com", client_id="codex"
        )
        response = self.client.put(
            _URL,
            {"enabled": False, "serverUrl": "", "clientId": ""},
            content_type="application/json",
        )
        assert response.status_code == _HTTP_OK
        row = OIDCSettings.objects.get(pk=1)
        assert row.enabled is False
        assert row.server_url == ""

    def test_put_invalidates_discovery_cache(self) -> None:
        cache.set(DISCOVERY_CACHE_KEY, {"issuer": "https://stale.example.com"})
        self.client.put(
            _URL,
            {"serverUrl": "https://new.example.com"},
            content_type="application/json",
        )
        assert cache.get(DISCOVERY_CACHE_KEY) is None


class AdminOIDCTestViewTests(TestCase):
    """The Test Connection endpoint probes the discovery document."""

    @override
    def setUp(self) -> None:
        admin = User.objects.create_superuser("admin", "", "admin")
        self.client.force_login(admin)

    def _post(self, payload: dict) -> dict:
        return _data(
            self.client.post(_TEST_URL, payload, content_type="application/json")
        )

    def test_reports_discovered_endpoints(self) -> None:
        doc = {
            "issuer": "https://idp.example.com",
            "authorization_endpoint": "https://idp.example.com/authorize",
            "token_endpoint": "https://idp.example.com/token",
            "userinfo_endpoint": "https://idp.example.com/userinfo",
        }
        with patch("codex.views.admin.oidc.fetch_discovery_document", return_value=doc):
            data = self._post({"serverUrl": "https://idp.example.com"})
        assert data["ok"] is True
        assert data["issuer"] == "https://idp.example.com"
        assert data["authorizationEndpoint"] is True
        assert data["tokenEndpoint"] is True
        assert data["userinfoEndpoint"] is True
        # Authelia case: no end_session advertised.
        assert data["endSessionEndpoint"] is False

    def test_reports_fetch_error(self) -> None:
        import requests

        with patch(
            "codex.views.admin.oidc.fetch_discovery_document",
            side_effect=requests.ConnectionError("boom"),
        ):
            data = self._post({"serverUrl": "https://unreachable.example.com"})
        assert data["ok"] is False
        assert "boom" in data["error"]

    def test_falls_back_to_saved_server_url(self) -> None:
        OIDCSettings.objects.filter(pk=1).update(server_url="https://saved.example.com")
        with patch(
            "codex.views.admin.oidc.fetch_discovery_document", return_value={}
        ) as mock_fetch:
            data = self._post({})
        mock_fetch.assert_called_once_with("https://saved.example.com")
        assert data["ok"] is False

    def test_no_server_url_anywhere(self) -> None:
        OIDCSettings.objects.filter(pk=1).update(server_url="")
        data = self._post({})
        assert data["ok"] is False
        assert "No server URL" in data["error"]
