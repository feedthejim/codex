"""Test the OIDCSettings singleton: pk enforcement, gating, encryption."""

from django.db import connection
from django.test import TestCase

from codex.models.admin import OIDCSettings
from codex.settings.db import get_oidc_settings, oidc_enabled


def _seed(**overrides) -> OIDCSettings:
    row, _ = OIDCSettings.objects.update_or_create(pk=1, defaults=overrides)
    return row


class OIDCSettingsSingletonTests(TestCase):
    """The model is a pk=1 singleton like EmailSettings."""

    def test_migration_seeded_singleton(self):
        """Migration 0047 seeds pk=1 so views can .get(pk=1) safely."""
        assert OIDCSettings.objects.filter(pk=1).exists()

    def test_save_forces_pk_one(self):
        # Fresh instances only insert cleanly when no row exists
        # (auto_now_add fields skip the UPDATE path) — same contract as
        # EmailSettings. Runtime writes always go through the fetched row.
        OIDCSettings.objects.all().delete()
        row = OIDCSettings(enabled=True)
        row.save()
        assert row.pk == 1
        row.provider_name = "Other"
        row.save()
        assert OIDCSettings.objects.filter(pk=1).count() == 1
        assert OIDCSettings.objects.count() == 1

    def test_get_oidc_settings_returns_row(self):
        _seed(provider_name="Authentik")
        row = get_oidc_settings()
        assert row is not None
        assert row.provider_name == "Authentik"

    def test_get_oidc_settings_none_when_unseeded(self):
        OIDCSettings.objects.all().delete()
        assert get_oidc_settings() is None


class OIDCEnabledDerivationTests(TestCase):
    """enabled AND server_url AND client_id must all be set."""

    def test_disabled_by_default(self):
        assert oidc_enabled() is False

    def test_enabled_switch_alone_is_not_enough(self):
        _seed(enabled=True)
        assert oidc_enabled() is False

    def test_requires_client_id(self):
        _seed(enabled=True, server_url="https://idp.example.com")
        assert oidc_enabled() is False

    def test_fully_configured_is_enabled(self):
        row = _seed(
            enabled=True, server_url="https://idp.example.com", client_id="codex"
        )
        assert oidc_enabled() is True
        assert oidc_enabled(row) is True

    def test_enabled_off_wins_over_config(self):
        _seed(enabled=False, server_url="https://idp.example.com", client_id="codex")
        assert oidc_enabled() is False


class OIDCSecretEncryptionTests(TestCase):
    """client_secret is encrypted at rest and decrypted on read."""

    def test_secret_round_trips_but_is_not_plaintext_in_db(self):
        secret = "hush-hush-test-secret"  # noqa: S105
        _seed(client_secret=secret)
        row = OIDCSettings.objects.get(pk=1)
        assert row.client_secret == secret
        with connection.cursor() as cursor:
            cursor.execute("SELECT client_secret FROM codex_oidcsettings")
            raw = cursor.fetchone()[0]
        assert raw != secret
        assert secret not in raw
