import { afterEach, describe, expect, it, vi } from "vitest";
import { apiRequest, apiUrl, setCsrfToken } from "./http";

describe("same-origin API client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    setCsrfToken(null);
  });

  it("uses the versioned relative prefix, cookies, and CSRF for writes", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: "trip-1" }), {
      status: 201,
      headers: { "content-type": "application/json" },
    }));
    vi.stubGlobal("fetch", fetchMock);
    setCsrfToken("csrf-value");

    await apiRequest("/trips", { method: "POST", body: JSON.stringify({ title: "差旅" }) });

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/trips");
    expect(init.credentials).toBe("include");
    expect(new Headers(init.headers).get("x-csrf-token")).toBe("csrf-value");
    expect(new Headers(init.headers).get("content-type")).toBe("application/json");
  });

  it("keeps the session CSRF token when a read response does not rotate it", async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce(new Response(JSON.stringify([]), { status: 200, headers: { "content-type": "application/json" } }))
      .mockResolvedValueOnce(new Response(JSON.stringify({ id: "trip-1" }), { status: 201, headers: { "content-type": "application/json" } }));
    vi.stubGlobal("fetch", fetchMock);
    setCsrfToken("session-token");

    await apiRequest("/trips");
    await apiRequest("/trips", { method: "POST", body: JSON.stringify({ title: "差旅" }) });

    const [, writeInit] = fetchMock.mock.calls[1] as [string, RequestInit];
    expect(new Headers(writeInit.headers).get("x-csrf-token")).toBe("session-token");
  });

  it("keeps resource URLs under the same versioned API prefix", () => {
    expect(apiUrl("documents/document-1/preview")).toBe("/api/v1/documents/document-1/preview");
  });

  it("turns an unauthorized response into a typed error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ code: "SESSION_EXPIRED" }), {
      status: 401,
      headers: { "content-type": "application/json" },
    })));

    await expect(apiRequest("/trips")).rejects.toMatchObject({
      name: "ApiError",
      status: 401,
      code: "SESSION_EXPIRED",
    });
  });

  it("surfaces FastAPI detail messages for browser-visible failures", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ detail: "Document not found" }), {
      status: 404,
      headers: { "content-type": "application/json" },
    })));

    await expect(apiRequest("/documents/missing")).rejects.toMatchObject({
      name: "ApiError",
      status: 404,
      message: "Document not found",
    });
  });
});
