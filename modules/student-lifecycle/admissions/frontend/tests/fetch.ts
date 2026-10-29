import { vi } from "vitest";

/** A fetch stand-in: answers with `body` and `status`, and records every URL and header set it was called with. */
export function api(body: unknown, status = 200) {
  return vi.fn().mockImplementation(async () => ({
    ok: status < 400,
    status,
    statusText: "",
    json: async () => body,
  }));
}

export const calledUrl = (fetchMock: ReturnType<typeof api>, call = 0): string => String(fetchMock.mock.calls[call]?.[0]);
export const calledHeaders = (fetchMock: ReturnType<typeof api>, call = 0): Record<string, string> =>
  (fetchMock.mock.calls[call]?.[1] as { headers: Record<string, string> }).headers;
