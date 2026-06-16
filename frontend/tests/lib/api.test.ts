import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { apiClient, ApiError } from "@/lib/api";
import { isDemoMode, setDemoMode } from "@/lib/demoMode";
import { mockRuns } from "@/lib/mockData";

describe("api client demo-mode fallback", () => {
  beforeEach(() => {
    setDemoMode(false);
    vi.restoreAllMocks();
  });

  afterEach(() => {
    setDemoMode(false);
  });

  it("falls back to bundled mock runs and flips demo mode on network failure", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.reject(new TypeError("Failed to fetch")))
    );
    const data = await apiClient.listRuns();
    expect(data.runs).toEqual(mockRuns);
    expect(isDemoMode()).toBe(true);
  });

  it("returns live data and clears demo mode on a successful response", async () => {
    const payload = { runs: [{ run_id: "x", workflow_name: "w", status: "completed", created_at: "2026-01-01T00:00:00Z" }] };
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(JSON.stringify(payload), {
            status: 200,
            headers: { "Content-Type": "application/json" },
          })
        )
      )
    );
    const data = await apiClient.listRuns();
    expect(data.runs[0].run_id).toBe("x");
    expect(isDemoMode()).toBe(false);
  });

  it("re-throws real HTTP errors instead of falling back", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(JSON.stringify({ detail: "boom" }), { status: 500 })
        )
      )
    );
    await expect(apiClient.listRuns()).rejects.toBeInstanceOf(ApiError);
  });
});
