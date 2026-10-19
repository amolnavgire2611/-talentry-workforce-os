import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api, clearAccessToken, getAccessToken, saveAccessToken, getCsrfToken, saveCsrfToken } from "./api";

describe("central API client", () => {
  const values = new Map<string, string>();

  beforeEach(() => {
    values.clear();
    vi.stubGlobal("sessionStorage", {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value),
      removeItem: (key: string) => values.delete(key),
    });
    vi.stubGlobal("localStorage", {
      getItem: (key: string) => values.get(key) ?? null,
      setItem: (key: string, value: string) => values.set(key, value),
      removeItem: (key: string) => values.delete(key),
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("attaches bearer credentials and parses JSON", async () => {
    saveAccessToken("signed-access-token");
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: 7 }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(api<{ id: number }>("/api/auth/me")).resolves.toEqual({ id: 7 });
    expect(new Headers(fetchMock.mock.calls[0][1].headers).get("Authorization")).toBe("Bearer signed-access-token");
    expect(fetchMock.mock.calls[0][1].credentials).toBe("include");
  });

  it("handles 204 without trying to parse a response body", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 })));
    await expect(api<void>("/api/employees/4", { method: "DELETE" })).resolves.toBeUndefined();
  });

  it("clears expired credentials and exposes safe API error details", async () => {
    saveAccessToken("expired-token");
    saveCsrfToken("old-csrf-token");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "Invalid or expired access token" }), { status: 401 })));

    await expect(api("/api/auth/me")).rejects.toMatchObject({ status: 401, message: "Invalid or expired access token" });
    expect(getAccessToken()).toBeNull();
    expect(getCsrfToken()).toBeNull();
    clearAccessToken();
  });

  it("rotates the browser session and retries one protected request after a 401", async () => {
    saveAccessToken("expired-access-token");
    saveCsrfToken("current-csrf-token");
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify({ detail: "Invalid or expired access token" }), { status: 401 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ access_token: "renewed-access-token", csrf_token: "rotated-csrf-token" }), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: 12 }), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(api<{ id: number }>("/api/auth/me")).resolves.toEqual({ id: 12 });
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(fetchMock.mock.calls[1][1].credentials).toBe("include");
    expect(new Headers(fetchMock.mock.calls[1][1].headers).get("X-CSRF-Token")).toBe("current-csrf-token");
    expect(new Headers(fetchMock.mock.calls[2][1].headers).get("Authorization")).toBe("Bearer renewed-access-token");
    expect(getAccessToken()).toBe("renewed-access-token");
    expect(getCsrfToken()).toBe("rotated-csrf-token");
  });

  it("sends the current CSRF token with a protected mutation", async () => {
    saveAccessToken("signed-access-token");
    saveCsrfToken("csrf-value");
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await api<void>("/api/auth/logout", { method: "POST" });
    expect(new Headers(fetchMock.mock.calls[0][1].headers).get("X-CSRF-Token")).toBe("csrf-value");
    expect(fetchMock.mock.calls[0][1].credentials).toBe("include");
  });

  it("formats Pydantic validation locations as useful messages", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: [{ loc: ["body", "email"], msg: "Invalid email" }] }), { status: 422 })));
    await expect(api("/api/auth/login", { method: "POST", body: JSON.stringify({}) })).rejects.toMatchObject({
      status: 422,
      message: "email: Invalid email",
    });
  });
});
