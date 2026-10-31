import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { TrainingVideo, VideoAnnotation } from "../src/api/client";
import { widgets } from "../src/widgets";
import { duration } from "../src/widgets/format";
import { CHECKED, ReviewsPending, SHOWN } from "../src/widgets/ReviewsPending";

const BASE = "/api/v1/training-video-analysis";

type Reply = { status: number; body: unknown };
const ok = (body: unknown): Reply => ({ status: 200, body });

/**
 * Stubs fetch: `/videos` answers the list, `/videos/{id}/annotations` answers through `annotations(id)`.
 * Any other request fails the test.
 */
function stubApi(videos: Reply | (() => Reply), annotations: (id: string) => Reply = () => ok([])) {
  const fetchMock = vi.fn(async (input: string, _init?: RequestInit) => {
    const url = new URL(input, "http://localhost");
    const path = url.pathname.slice(BASE.length);
    const match = path.match(/^\/videos\/([^/]+)\/annotations$/);
    let r: Reply;
    if (path === "/videos") r = typeof videos === "function" ? videos() : videos;
    else if (match) r = annotations(decodeURIComponent(match[1]!));
    else throw new Error(`unexpected request ${input}`);
    return { ok: r.status < 400, status: r.status, statusText: "", json: async () => r.body };
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const urls = (fetchMock: { mock: { calls: unknown[][] } }) => fetchMock.mock.calls.map((c) => String(c[0]));

const video = (id: string, title: string, recorded_at = "2026-10-20T09:30:00Z", duration_seconds = 245.5): TrainingVideo => ({
  id,
  title,
  uploader_id: "u-1",
  video_url: `https://videos.example/${id}.mp4`,
  duration_seconds,
  recorded_at,
  created_at: recorded_at,
});
const note = (videoId: string): VideoAnnotation => ({
  id: `n-${videoId}`,
  video_id: videoId,
  author_id: "u-coach",
  start_timestamp: 12,
  content: "Drive the knee",
  category: "technical",
  created_at: "2026-10-21T10:00:00Z",
});
const page = <T,>(items: T[], total = items.length) => ({ items, total });

beforeEach(() => localStorage.setItem("eos.token", "test-token"));
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("widget declarations", () => {
  it("exports only reviews-pending, with a permission the coach role holds", () => {
    expect(widgets.map((w) => w.id)).toEqual(["training-video-analysis.reviews-pending"]);
    const w = widgets[0]!;
    expect(w.title).toBe("Videos to review");
    expect(w.permission).toBe("training-video-analysis:video:read");
    expect(w.kind).toBe("list");
    expect(w.size).toBe("2x1");
    expect(w.component).toBe(ReviewsPending);
  });

  it("does not export session-plan or training-schedule (the layouts name them under athlete-performance)", () => {
    expect(widgets.map((w) => w.id)).not.toContain("training-video-analysis.session-plan");
    expect(widgets.map((w) => w.id)).not.toContain("training-video-analysis.training-schedule");
  });
});

describe("format", () => {
  it("writes a video's length as m:ss or h:mm:ss", () => {
    expect(duration(245.5)).toBe("4:06");
    expect(duration(59)).toBe("0:59");
    expect(duration(3729)).toBe("1:02:09");
    expect(duration(Number.NaN)).toBe("—");
  });
});

describe("training-video-analysis.reviews-pending", () => {
  const vids = [
    video("v-1", "Sprint mechanics cam A", "2026-10-25T07:00:00Z", 245.5),
    video("v-2", "Match vs. Rovers, first half", "2026-10-22T16:00:00Z", 2730),
    video("v-3", "Block starts", "2026-10-20T07:00:00Z", 3729),
  ];

  it("lists the recent videos nobody has annotated, in the server's order, and counts them", async () => {
    const fetchMock = stubApi(ok(page(vids)), (id) => ok(id === "v-2" ? [note(id)] : []));
    render(<ReviewsPending role="coach" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    const list = await screen.findByRole("list", { name: "Videos waiting for review" });
    const items = within(list).getAllByRole("listitem");
    expect(items).toHaveLength(2);
    expect(items[0]?.textContent).toContain("Sprint mechanics cam A");
    expect(items[0]?.textContent).toContain("Recorded 25 Oct 2026");
    expect(items[0]?.textContent).toContain("4:06");
    expect(items[1]?.textContent).toContain("Block starts");
    expect(items[1]?.textContent).toContain("1:02:09");
    expect(screen.getByLabelText("Review summary").textContent).toBe("Waiting for review2Reviewed1");
    expect(urls(fetchMock).sort()).toEqual([
      `${BASE}/videos/v-1/annotations`,
      `${BASE}/videos/v-2/annotations`,
      `${BASE}/videos/v-3/annotations`,
      `${BASE}/videos?limit=${CHECKED}`,
    ]);
    expect((fetchMock.mock.calls[0]?.[1] as unknown as { headers: Record<string, string> }).headers.Authorization).toBe("Bearer test-token");
  });

  it(`checks at most ${CHECKED} videos, lists ${SHOWN} and says how many more and how many were not checked`, async () => {
    const many = Array.from({ length: CHECKED }, (_, i) => video(`v-${i}`, `Video ${i}`));
    const fetchMock = stubApi(ok(page(many, 45)));
    render(<ReviewsPending role="coach" />);
    const list = await screen.findByRole("list", { name: "Videos waiting for review" });
    expect(within(list).getAllByRole("listitem")).toHaveLength(SHOWN);
    expect(screen.getByText(`and ${CHECKED - SHOWN} videos more`)).toBeTruthy();
    expect(screen.getByText(`Checked the ${CHECKED} most recent of 45 videos.`)).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(1 + CHECKED);
  });

  it("has an empty state when there are no videos, without asking for annotations", async () => {
    const fetchMock = stubApi(ok(page([])));
    render(<ReviewsPending role="coach" />);
    expect(await screen.findByText("No training videos yet")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("says every video is reviewed when all have an annotation", async () => {
    stubApi(ok(page(vids)), (id) => ok([note(id)]));
    render(<ReviewsPending role="coach" />);
    expect(await screen.findByText("All videos reviewed")).toBeTruthy();
  });

  it("does not claim all are reviewed when older videos were not checked", async () => {
    stubApi(ok(page(vids, 40)), (id) => ok([note(id)]));
    render(<ReviewsPending role="coach" />);
    expect(await screen.findByText("None of the 3 videos checked is waiting for review.")).toBeTruthy();
    expect(screen.getByText("Checked the 3 most recent of 40 videos.")).toBeTruthy();
    expect(screen.queryByText("All videos reviewed")).toBeNull();
  });

  it("does not offer a retry that cannot help (403)", async () => {
    stubApi({ status: 403, body: { code: "forbidden", message: "no" } });
    render(<ReviewsPending role="coach" />);
    expect(await screen.findByText("You do not have access to this.")).toBeTruthy();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("asks to sign in again on 401, without a retry", async () => {
    stubApi({ status: 401, body: { detail: "expired" } });
    render(<ReviewsPending role="coach" />);
    expect(await screen.findByText("Sign in again to see this.")).toBeTruthy();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it.each([0, 502, 503])("says the data is not available yet when the service is down (%s)", async (status) => {
    if (status === 0) vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("Failed to fetch"))));
    else stubApi({ status, body: {} });
    render(<ReviewsPending role="coach" />);
    expect(await screen.findByText("Training video data is not available yet.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });

  it("says the data is not available yet while the backend is missing, and retries", async () => {
    let mounted = false;
    const fetchMock = stubApi(() => (mounted ? ok(page(vids)) : { status: 404, body: { detail: "Not Found" } }));
    render(<ReviewsPending role="coach" />);
    expect(await screen.findByText("Training video data is not available yet.")).toBeTruthy();
    mounted = true;
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("list", { name: "Videos waiting for review" })).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(1 + 1 + vids.length);
  });

  it("does not show server wording for other failures", async () => {
    stubApi(ok(page(vids)), () => ({ status: 500, body: { code: "boom", message: "Traceback ..." } }));
    render(<ReviewsPending role="coach" />);
    expect(await screen.findByText("Could not load training video data.")).toBeTruthy();
    expect(screen.queryByText(/Traceback/)).toBeNull();
  });
});
