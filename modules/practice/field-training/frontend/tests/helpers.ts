import { cleanup } from "@testing-library/react";
import { afterEach, beforeEach, vi } from "vitest";
import type { Opening, Placement } from "../src/api/client";

/** fetch answering once with this status and body. */
export function answer(status: number, body: unknown) {
  return vi.fn().mockResolvedValue({ ok: status < 400, status, statusText: "", json: async () => body });
}

/** fetch failing once with 503, then answering with `body`: the error state and its retry. */
export function failThenAnswer(body: unknown) {
  return vi
    .fn()
    .mockResolvedValueOnce({ ok: false, status: 503, statusText: "", json: async () => ({}) })
    .mockResolvedValueOnce({ ok: true, status: 200, statusText: "", json: async () => body });
}

/** The URL and Authorization header of the first fetch call. */
export function firstCall(fetchMock: ReturnType<typeof vi.fn>): { url: string; auth: string | undefined } {
  const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
  return { url, auth: (init.headers as Record<string, string>).Authorization };
}

export function useSession() {
  beforeEach(() => {
    localStorage.setItem("eos.token", "test-token");
  });
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    localStorage.clear();
  });
}

export const placement = (over: Partial<Placement> = {}): Placement => ({
  id: "p1",
  organisation_id: "o1",
  opening_id: "op1",
  opening_title: "General rotation",
  site_id: "s1",
  site_name: "North Ward",
  trainee_id: "t1",
  trainee_name: null,
  supervisor_id: "sup1",
  starts_on: "2026-11-02",
  ends_on: "2026-12-31",
  status: "active",
  required_hours: 40,
  verified_hours: 12.5,
  pending_hours: 4,
  final_outcome: null,
  ...over,
});

export const opening = (over: Partial<Opening> = {}): Opening => ({
  id: "op1",
  organisation_id: "o1",
  site_id: "s1",
  site_name: "North Ward",
  title: "General rotation",
  discipline: "General",
  starts_on: "2026-11-02",
  ends_on: "2026-12-31",
  seats: 3,
  seats_filled: 1,
  status: "open",
  ...over,
});
