"""Test OIDC config plumbing: TOML keys, env overrides, and derived settings."""

from pathlib import Path

from django.conf import settings

from codex.settings.config import get_bool, get_str, load_codex_config

_DEFAULT_TOML = Path("codex/settings/codex.toml.default")


def _load(tmp_path: Path, body: str):
    config_toml = tmp_path / "codex.toml"
    config_toml.write_text(body)
    return load_codex_config(config_toml, _DEFAULT_TOML)


class TestOIDCConfigPlumbing:
    """TOML and env override plumbing for [auth.oidc]."""

    def test_default_toml_has_no_live_oidc_keys(self, tmp_path):
        """The shipped default config documents but does not enable OIDC."""
        config = _load(tmp_path, _DEFAULT_TOML.read_text())
        assert get_bool(config, "auth.oidc.enabled") is False
        assert get_str(config, "auth.oidc.server_url") == ""

    def test_toml_keys_load(self, tmp_path):
        """[auth.oidc] TOML keys land at the expected keypaths."""
        config = _load(
            tmp_path,
            "[auth.oidc]\n"
            "enabled = true\n"
            'provider_name = "Authentik"\n'
            'server_url = "https://auth.example.com/application/o/codex/"\n'
            'client_id = "codex"\n'
            'scope = "openid profile email groups"\n'
            "pkce = false\n"
            "link_by_email = true\n",
        )
        assert get_bool(config, "auth.oidc.enabled") is True
        assert get_str(config, "auth.oidc.provider_name") == "Authentik"
        assert get_str(config, "auth.oidc.client_id") == "codex"
        assert get_str(config, "auth.oidc.scope") == "openid profile email groups"
        assert get_bool(config, "auth.oidc.pkce") is False
        assert get_bool(config, "auth.oidc.link_by_email") is True

    def test_env_overrides_toml(self, tmp_path, monkeypatch):
        """CODEX_AUTH_OIDC_* env vars override TOML values."""
        monkeypatch.setenv("CODEX_AUTH_OIDC_ENABLED", "true")
        monkeypatch.setenv("CODEX_AUTH_OIDC_SERVER_URL", "https://env.example.com")
        monkeypatch.setenv("CODEX_AUTH_OIDC_CLIENT_ID", "env-client")
        monkeypatch.setenv("CODEX_AUTH_OIDC_PKCE", "false")
        config = _load(
            tmp_path,
            '[auth.oidc]\nenabled = false\nserver_url = "https://toml.example.com"\n',
        )
        assert get_bool(config, "auth.oidc.enabled") is True
        assert get_str(config, "auth.oidc.server_url") == "https://env.example.com"
        assert get_str(config, "auth.oidc.client_id") == "env-client"
        # Env values arrive as strings; get_bool must coerce "false".
        assert get_bool(config, "auth.oidc.pkce") is False

    def test_defaults_when_section_missing(self, tmp_path):
        """Missing [auth.oidc] section yields the documented defaults."""
        config = _load(tmp_path, "[server]\nport = 9810\n")
        assert get_bool(config, "auth.oidc.enabled") is False
        assert get_bool(config, "auth.oidc.pkce", default=True) is True
        assert (
            get_str(config, "auth.oidc.username_claim", default="preferred_username")
            == "preferred_username"
        )


class TestOIDCDjangoSettings:
    """Derived Django settings in the (disabled-by-default) test environment."""

    def test_disabled_by_default(self):
        assert settings.AUTH_OIDC_ENABLED is False

    def test_provider_apps_empty_when_disabled(self):
        providers = settings.SOCIALACCOUNT_PROVIDERS
        assert providers["openid_connect"]["APPS"] == []

    def test_adapter_and_backends_wired(self):
        assert settings.SOCIALACCOUNT_ADAPTER == "codex.oidc.CodexSocialAccountAdapter"
        assert (
            "allauth.account.auth_backends.AuthenticationBackend"
            in settings.AUTHENTICATION_BACKENDS
        )

    def test_allauth_apps_installed(self):
        assert "allauth.socialaccount.providers.openid_connect" in (
            settings.INSTALLED_APPS
        )
        assert "allauth.account.middleware.AccountMiddleware" in settings.MIDDLEWARE
