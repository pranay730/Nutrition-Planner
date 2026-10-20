import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, api } from "./api";

afterEach(() => vi.unstubAllGlobals());

describe("api", () => {
  it("adds JSON and bearer headers and parses successful responses", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await expect(api<{ ok: boolean }>("/daily-plan", {}, "token-123")).resolves.toEqual({
      ok: true,
    });
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(/\/daily-plan$/),
      expect.objectContaining({
        headers: expect.objectContaining({
          Authorization: "Bearer token-123",
          "Content-Type": "application/json",
        }),
      }),
    );
  });

  it("surfaces API detail with its HTTP status", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ detail: "Profile required" }), {
          status: 409,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );

    const request = api("/daily-plan");

    await expect(request).rejects.toEqual(new ApiError(409, "Profile required"));
  });

  it("uses a safe fallback when an error response is not JSON", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("bad gateway", { status: 502 })));

    await expect(api("/health")).rejects.toMatchObject({
      status: 502,
      message: "Something went wrong",
    });
  });
});
