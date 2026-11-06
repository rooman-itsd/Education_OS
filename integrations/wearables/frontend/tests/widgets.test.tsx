import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import type { ComponentType } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { WidgetProps } from "@eos/ui-kit";
import { getAlerts, type Alert, type AlertPage } from "../src/api/client";
import { widgets } from "../src/widgets";
import { Alerts } from "../src/widgets/Alerts";
import { athleteHandle, dayOf } from "../src/widgets/format";

const URL_ALERTS = "/api/v1/wearables/alerts";

function answer(status: number, body: unknown) {
  return { ok: status < 400, status, statusText: "", json: async () => body };
}

/** Stubs fetch with one response per call, in order. */
function stubFetch(...responses: ReturnType<typeof answer>[]) {
  const fetchMock = vi.fn();
  for (const r of responses) fetchMock.mockResolvedValueOnce(r);
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

function lastCall(fetchMock: ReturnType<typeof vi.fn>) {
  const [url, init] = fetchMock.mock.calls[fetchMock.mock.calls.length - 1] as [string, RequestInit];
  return { url, headers: init.headers as Record<string, string> };
}

beforeEach(() => {
  localStorage.setItem("eos.token", "test-token");
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

const alert = (over: Partial<Alert> = {}): Alert => ({
  person_id: "11111111-2222-4333-8444-555555aaaaaa",
  provider: "polar",
  kind: "link_expired",
  since: "2026-11-03T06:00:00+00:00",
  last_synced_at: null,
  ...over,
});
const page = (items: Alert[], next_cursor: string | null = null): AlertPage => ({ items, next_cursor });

describe("widget declaration", () => {
  it("exports the widget the Coach layout names, behind wearables:alert:read", () => {
    expect(widgets.map((w) => w.id)).toEqual(["wearables.alerts"]);
    const w = widgets[0]!;
    expect(w.permission).toBe("wearables:alert:read");
    expect(w.size).toBe("1x1");
    expect(w.kind).toBe("list");
    expect(w.title).toBe("Device alerts");
    expect(w.component).toBe(Alerts as ComponentType<WidgetProps>);
  });
});

describe("format", () => {
  it("gives an athlete the widget has no name for a short stable handle", () => {
    expect(athleteHandle("11111111-2222-4333-8444-555555aaaaaa")).toBe("Athlete …aaaaaa");
  });

  it("reads a date-time in the viewer's time zone and says nothing for a bad one", () => {
    expect(dayOf("2026-11-03T06:00:00+00:00")).toBe("3 Nov 2026");
    expect(dayOf(null)).toBeNull();
    expect(dayOf("not a date")).toBeNull();
  });
});

describe("wearables.alerts", () => {
  it("lists each problem with what it is, which device and since when, from GET /alerts", async () => {
    const fetchMock = stubFetch(
      answer(
        200,
        page([
          alert(),
          alert({ person_id: "aaaaaaaa-2222-4333-8444-5555550000bb", provider: "garmin", kind: "link_revoked", since: "2026-11-01T06:00:00+00:00" }),
          alert({ person_id: "aaaaaaaa-2222-4333-8444-5555550000cc", provider: null, kind: "not_linked" }),
        ]),
      ),
    );
    render(<Alerts role="coach" />);
    expect(screen.getByLabelText("Loading").getAttribute("aria-busy")).toBe("true");
    const list = await screen.findByRole("list", { name: "Device alerts" });
    const rows = within(list).getAllByRole("listitem");
    expect(rows).toHaveLength(3);
    expect(rows[0]!.textContent).toBe("Athlete …aaaaaaLink expiredPolar, since 3 Nov 2026");
    expect(rows[1]!.textContent).toBe("Athlete …0000bbLink removedGarmin, since 1 Nov 2026");
    expect(rows[2]!.textContent).toContain("Not connected");
    expect(screen.getByRole("heading", { name: "3 athletes need attention" })).toBeTruthy();
    const { url, headers } = lastCall(fetchMock);
    expect(url).toBe(`${URL_ALERTS}?limit=50`);
    expect(headers.Authorization).toBe("Bearer test-token");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("says the kind in words and in a tone, never by colour alone", async () => {
    stubFetch(answer(200, page([alert({ kind: "sync_failing" }), alert({ person_id: "x-aaaaaa1", kind: "no_recent_data" }), alert({ person_id: "x-aaaaaa2", kind: "link_expired" })])));
    render(<Alerts role="coach" />);
    expect((await screen.findByText("Not syncing")).className).toContain("eos-badge--danger");
    expect(screen.getByText("No recent data").className).toContain("eos-badge--warning");
    expect(screen.getByText("Link expired").className).toContain("eos-badge--warning");
  });

  it("names Fitbit for the Google Health provider and shows no reading", async () => {
    stubFetch(answer(200, page([alert({ provider: "google-health" }), alert({ person_id: "p-bbbbbb", provider: "strava" })])));
    render(<Alerts role="coach" />);
    expect(await screen.findByText(/Fitbit, since/)).toBeTruthy();
    expect(screen.getByText(/Strava, since/)).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/bpm|steps|kcal|km/);
  });

  it("says one athlete in the singular", async () => {
    stubFetch(answer(200, page([alert()])));
    render(<Alerts role="coach" />);
    expect(await screen.findByRole("heading", { name: "1 athlete needs attention" })).toBeTruthy();
  });

  it("shows eight and says how many more, with a plus when the server has another page", async () => {
    const many = Array.from({ length: 11 }, (_, i) => alert({ person_id: `00000000-0000-4000-8000-${String(i).padStart(12, "0")}` }));
    stubFetch(answer(200, page(many, "next")));
    render(<Alerts role="coach" />);
    const list = await screen.findByRole("list", { name: "Device alerts" });
    expect(within(list).getAllByRole("listitem")).toHaveLength(8);
    expect(screen.getByText("and 3+ more")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "11+ athletes need attention" })).toBeTruthy();
  });

  it("shows an empty state when nobody has a device problem", async () => {
    stubFetch(answer(200, page([])));
    render(<Alerts role="coach" />);
    expect(await screen.findByText("No device problems")).toBeTruthy();
    expect(screen.queryByRole("list")).toBeNull();
  });

  it("shows a generic error, never the server's message, and retries", async () => {
    const fetchMock = stubFetch(answer(500, { code: "internal", detail: "Database unavailable" }), answer(200, page([alert()])));
    render(<Alerts role="coach" />);
    const alertBox = await screen.findByRole("alert");
    expect(alertBox.textContent).toContain("Could not load device alerts.");
    expect(alertBox.textContent).not.toContain("Database unavailable");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Link expired")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("shows an error when the service cannot be reached, and retries", async () => {
    const fetchMock = vi.fn().mockRejectedValueOnce(new TypeError("Failed to fetch")).mockResolvedValueOnce(answer(200, page([alert()])));
    vi.stubGlobal("fetch", fetchMock);
    render(<Alerts role="coach" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Device alerts are not available yet.");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Link expired")).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it.each([404, 502, 503])("says the alerts are not available yet on %i, with a retry", async (status) => {
    stubFetch(answer(status, {}));
    render(<Alerts role="coach" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Device alerts are not available yet.");
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });

  it("asks the user to sign in again, without a retry, on 401", async () => {
    stubFetch(answer(401, { code: "unauthenticated", detail: "invalid token" }));
    render(<Alerts role="coach" />);
    expect((await screen.findByRole("alert")).textContent).toContain("Sign in again to see this.");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });

  it("offers no retry when the viewer lacks wearables:alert:read", async () => {
    stubFetch(answer(403, { code: "forbidden", detail: "requires wearables:alert:read" }));
    render(<Alerts role="coach" />);
    expect((await screen.findByRole("alert")).textContent).toContain("You do not have access to this.");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
  });

  it("sends no Authorization header when there is no session token", async () => {
    localStorage.clear();
    const fetchMock = stubFetch(answer(200, page([])));
    render(<Alerts role="coach" />);
    await screen.findByText("No device problems");
    expect(lastCall(fetchMock).headers.Authorization).toBeUndefined();
  });
});

describe("the API client", () => {
  it("asks for a squad with a comma-separated person_id, at most 200", async () => {
    const fetchMock = stubFetch(answer(200, page([])));
    const ids = Array.from({ length: 250 }, (_, i) => `00000000-0000-4000-8000-${String(i).padStart(12, "0")}`);
    await getAlerts({ personIds: ids, limit: 20 });
    const url = new URL(lastCall(fetchMock).url, "http://x");
    expect(url.pathname).toBe(URL_ALERTS);
    expect(url.searchParams.get("limit")).toBe("20");
    expect(url.searchParams.get("person_id")!.split(",")).toHaveLength(200);
  });

  it("sends no filter when there is no squad", async () => {
    const fetchMock = stubFetch(answer(200, page([])));
    await getAlerts();
    expect(lastCall(fetchMock).url).toBe(URL_ALERTS);
  });
});
