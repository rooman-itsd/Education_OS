import { cleanup, render, screen } from "@testing-library/react";
import type { ReactElement } from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";

/** A fetch that answers every call with `status` and `body`. */
export function answer(status: number, body: unknown) {
  return vi.fn().mockResolvedValue({ ok: status < 400, status, statusText: "", json: async () => body });
}

/** A fetch that fails once with 503, then answers with `body`: the error state and its retry. */
export function failThenAnswer(body: unknown) {
  return vi
    .fn()
    .mockResolvedValueOnce({ ok: false, status: 503, statusText: "", json: async () => ({}) })
    .mockResolvedValueOnce({ ok: true, status: 200, statusText: "", json: async () => body });
}

/** A fetch that never answers: the loading state. */
export function pending() {
  return vi.fn().mockReturnValue(new Promise(() => undefined));
}

/** The URL and Authorization header of the first call. */
export function firstCall(fetchMock: ReturnType<typeof vi.fn>): { url: string; auth: string | undefined } {
  const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
  return { url, auth: (init.headers as Record<string, string>).Authorization };
}

export function useSession(): void {
  beforeEach(() => {
    localStorage.setItem("eos.token", "test-token");
  });
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    localStorage.clear();
  });
}

/**
 * The error state says why a load failed (describeFailure): 401 and 403 offer no retry, another server error names
 * what could not be loaded and offers one. The 503 case, with its retry, is in each widget's own test.
 */
export function itDescribesFailures(widget: () => ReactElement, what: string): void {
  it.each([
    [401, "Sign in again to see this."],
    [403, "You do not have access to this."],
  ])("on %i says why and offers no retry", async (status, text) => {
    vi.stubGlobal("fetch", answer(status, {}));
    render(widget());
    expect((await screen.findByRole("alert")).textContent).toContain(text);
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });

  it("on another server error says what could not be loaded and offers a retry", async () => {
    vi.stubGlobal("fetch", answer(500, {}));
    render(widget());
    expect((await screen.findByRole("alert")).textContent).toContain(`Could not load ${what}`);
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });

  it("on a network failure says the data is not available yet and offers a retry", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    render(widget());
    expect((await screen.findByRole("alert")).textContent).toContain("Projects data is not available yet.");
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });
}
