/*
 * Unit tests for the admin store's OIDC settings actions:
 * loadOidcSettings (TTL-gated), updateOidcSettings, testOidcConnection.
 * HTTP layer mocked; admin gate driven through the auth store.
 */
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock(import("@/api/v4/admin"), async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    getOidcSettings: vi.fn(),
    updateOidcSettings: vi.fn(),
    testOidcConnection: vi.fn(),
  };
});

import * as API from "@/api/v4/admin";
import { useAdminStore } from "@/stores/admin";
import { useAuthStore } from "@/stores/auth";

const SETTINGS = Object.freeze({
  enabled: true,
  providerName: "Authentik",
  serverUrl: "https://idp.example.com",
  clientId: "codex",
  clientSecretSet: true,
});

function adminStore() {
  const authStore = useAuthStore();
  authStore.user = { id: 1, username: "admin", isStaff: true };
  return useAdminStore();
}

beforeEach(() => {
  setActivePinia(createPinia());
  for (const fn of Object.values(API)) {
    if (typeof fn?.mockReset === "function") {
      fn.mockReset();
    }
  }
});

describe("useAdminStore — OIDC settings", () => {
  it("loads settings into state", async () => {
    API.getOidcSettings.mockResolvedValue({ data: SETTINGS });
    const store = adminStore();
    await store.loadOidcSettings();
    expect(store.oidcSettings).toEqual(SETTINGS);
  });

  it("respects the TTL and refetches with force", async () => {
    API.getOidcSettings.mockResolvedValue({ data: SETTINGS });
    const store = adminStore();
    await store.loadOidcSettings();
    await store.loadOidcSettings();
    expect(API.getOidcSettings).toHaveBeenCalledTimes(1);
    await store.loadOidcSettings({ force: true });
    expect(API.getOidcSettings).toHaveBeenCalledTimes(2);
  });

  it("denies non-admins", async () => {
    useAuthStore().user = { id: 2, username: "reader" };
    const store = useAdminStore();
    await store.loadOidcSettings();
    expect(API.getOidcSettings).not.toHaveBeenCalled();
  });

  it("update round-trips server state", async () => {
    API.updateOidcSettings.mockResolvedValue({
      data: { ...SETTINGS, providerName: "Renamed" },
    });
    const store = adminStore();
    await store.updateOidcSettings({ providerName: "Renamed" });
    expect(API.updateOidcSettings).toHaveBeenCalledWith({
      providerName: "Renamed",
    });
    expect(store.oidcSettings.providerName).toBe("Renamed");
  });

  it("test connection returns the endpoint report", async () => {
    const report = { ok: true, issuer: "https://idp.example.com" };
    API.testOidcConnection.mockResolvedValue({ data: report });
    const store = adminStore();
    const result = await store.testOidcConnection({
      serverUrl: "https://idp.example.com",
    });
    expect(result).toEqual(report);
  });

  it("test connection surfaces errors as undefined", async () => {
    API.testOidcConnection.mockRejectedValue(new Error("boom"));
    const store = adminStore();
    const result = await store.testOidcConnection({});
    expect(result).toBeUndefined();
  });
});
