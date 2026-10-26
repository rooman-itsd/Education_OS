import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { OrganisationApprovalQueue } from "../../src/admin/components/organisations/OrganisationApprovalQueue";

const ORGS = [
  { id: "o1", name: "Riverside Sports College", slug: "riverside", academy_type: "sports-college", requested_academy_type: null, country: "IN", status: "pending_approval", status_reason: null, created_at: "2026-10-20T09:00:00+00:00", plan: "trial", trial_ends_at: "2026-11-19T09:00:00+00:00" },
  { id: "o2", name: "Hilltop Music Academy", slug: "hilltop", academy_type: "music-academy", requested_academy_type: null, country: null, status: "pending_approval", status_reason: null, created_at: "2026-10-21T09:00:00+00:00", plan: "trial", trial_ends_at: null },
];
const DETAIL = { ...ORGS[0], entitlement: { modules: [], status: "pending_approval", subscription_status: "trialing", trial_ends_at: "2026-11-19T09:00:00+00:00" } };

type Reply = { status: number; body?: unknown } | "network-error" | Promise<never>;
const respond = (status: number, body: unknown) =>
  Promise.resolve({ ok: status < 400, status, statusText: "", json: async () => body } as Response);

/** fetch stub routed by path; `list` may be a sequence, one reply per call (the last repeats). */
function mockApi({ list = [{ status: 200, body: ORGS }] as Reply[], detail = { status: 200, body: DETAIL } as Reply, approve = { status: 200, body: { ...ORGS[0], status: "active" } } as Reply } = {}) {
  let listCalls = 0;
  const pick = (r: Reply) => (r === "network-error" ? Promise.reject(new TypeError("Failed to fetch")) : r instanceof Promise ? r : respond(r.status, r.body));
  const f = vi.fn((url: string, _init?: RequestInit) => {
    if (url.endsWith("/tenancy/admin/organisations?status=pending_approval")) return pick(list[Math.min(listCalls++, list.length - 1)]!);
    if (/\/approve$/.test(url)) return pick(approve);
    if (/\/tenancy\/admin\/organisations\/[^/?]+$/.test(url)) return pick(detail);
    return Promise.reject(new Error(`unexpected ${url}`));
  });
  vi.stubGlobal("fetch", f);
  return f;
}
const calls = (f: ReturnType<typeof mockApi>, re: RegExp) => f.mock.calls.filter(([u]) => re.test(String(u)));
const LIST = /\?status=pending_approval$/;
const APPROVE = /\/approve$/;

beforeEach(() => localStorage.setItem("eos.token", "super-admin-token"));
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

function renderQueue(props: Partial<React.ComponentProps<typeof OrganisationApprovalQueue>> = {}) {
  const onNotify = vi.fn();
  const onCountChange = vi.fn();
  render(<OrganisationApprovalQueue onNotify={onNotify} onCountChange={onCountChange} {...props} />);
  return { onNotify, onCountChange };
}

async function openReview(name = "Riverside Sports College") {
  fireEvent.click(await screen.findByRole("button", { name: `Review ${name}` }));
  return screen.findByRole("dialog", { name: `Review ${name}` });
}

describe("OrganisationApprovalQueue: the list", () => {
  it("loads pending organisations from GET ?status=pending_approval with the session token, and reports the count", async () => {
    const f = mockApi();
    const { onCountChange } = renderQueue();
    expect(screen.getByText("Loading organisations…")).toBeTruthy();
    expect(await screen.findByText("Riverside Sports College")).toBeTruthy();
    expect(screen.getByText("hilltop")).toBeTruthy();
    expect(screen.getAllByText("Sports College").length).toBeGreaterThan(0);
    expect(onCountChange).toHaveBeenLastCalledWith(2);
    const init = calls(f, LIST)[0]![1] as RequestInit;
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer super-admin-token");
  });

  it("shows an empty state", async () => {
    mockApi({ list: [{ status: 200, body: [] }] });
    const { onCountChange } = renderQueue();
    expect(await screen.findByText("No organisations are waiting for approval.")).toBeTruthy();
    expect(onCountChange).toHaveBeenLastCalledWith(0);
  });

  it("shows an error with a retry that recovers", async () => {
    mockApi({ list: ["network-error", { status: 200, body: ORGS }] });
    renderQueue();
    expect(await screen.findByText("Couldn't load the approval queue")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("Riverside Sports College")).toBeTruthy();
  });

  it("filters by name or short name", async () => {
    mockApi();
    renderQueue();
    fireEvent.change(await screen.findByLabelText("Search organisations awaiting approval"), { target: { value: "hill" } });
    expect(screen.queryByText("Riverside Sports College")).toBeNull();
    expect(screen.getByText("Hilltop Music Academy")).toBeTruthy();
  });

  it("reloads when the dashboard's refresh key changes", async () => {
    const f = mockApi();
    const onNotify = vi.fn();
    const { rerender } = render(<OrganisationApprovalQueue onNotify={onNotify} refreshKey={0} />);
    await screen.findByText("Riverside Sports College");
    rerender(<OrganisationApprovalQueue onNotify={onNotify} refreshKey={1} />);
    await waitFor(() => expect(calls(f, LIST)).toHaveLength(2));
  });
});

describe("OrganisationApprovalQueue: reviewing", () => {
  it("opens a dialog with the organisation's details from GET /{id}", async () => {
    const f = mockApi();
    renderQueue();
    const drawer = await openReview();
    expect(await within(drawer).findByText("riverside")).toBeTruthy();
    expect(within(drawer).getByText("Awaiting approval")).toBeTruthy();
    expect(within(drawer).getByText("Yes")).toBeTruthy();
    expect(within(drawer).getByText("trial")).toBeTruthy();
    expect(within(drawer).getByText("Not available from the API yet")).toBeTruthy();
    expect(calls(f, /\/organisations\/o1$/)).toHaveLength(1);
  });

  it("shows the administrator's email when the API returns it (contract field admin_email)", async () => {
    mockApi({ detail: { status: 200, body: { ...DETAIL, admin_email: "asha@riverside.example.com" } } });
    renderQueue();
    const drawer = await openReview();
    expect(await within(drawer).findByText("asha@riverside.example.com")).toBeTruthy();
  });

  it("Escape closes the drawer and returns focus to its Review button", async () => {
    mockApi();
    renderQueue();
    const review = await screen.findByRole("button", { name: "Review Riverside Sports College" });
    fireEvent.click(review);
    await screen.findByRole("dialog", { name: "Review Riverside Sports College" });
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(review);
  });
});

describe("OrganisationApprovalQueue: approving through POST /{id}/approve", () => {
  async function confirmDialog() {
    const drawer = await openReview();
    await within(drawer).findByText("riverside");
    fireEvent.click(within(drawer).getByRole("button", { name: "Approve" }));
    return screen.findByRole("dialog", { name: "Approve Riverside Sports College?" });
  }

  it("asks for confirmation, approves, notifies, and refreshes the list and count", async () => {
    const f = mockApi({ list: [{ status: 200, body: ORGS }, { status: 200, body: [ORGS[1]] }] });
    const { onNotify, onCountChange } = renderQueue();
    const dialog = await confirmDialog();
    expect(calls(f, APPROVE)).toHaveLength(0);
    fireEvent.click(within(dialog).getByRole("button", { name: "Approve" }));
    await waitFor(() => expect(onNotify).toHaveBeenCalledWith("Riverside Sports College approved. Its administrator can now sign in."));
    expect(JSON.parse(String((calls(f, APPROVE)[0]![1] as RequestInit).body))).toEqual({});
    await waitFor(() => expect(onCountChange).toHaveBeenLastCalledWith(1));
    expect(screen.queryByText("Riverside Sports College")).toBeNull();
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("sends the optional reason when one is given", async () => {
    const f = mockApi();
    renderQueue();
    const dialog = await confirmDialog();
    fireEvent.change(within(dialog).getByLabelText("Reason (optional)"), { target: { value: "  verified institution " } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Approve" }));
    await waitFor(() => expect(calls(f, APPROVE)).toHaveLength(1));
    expect(JSON.parse(String((calls(f, APPROVE)[0]![1] as RequestInit).body))).toEqual({ reason: "verified institution" });
  });

  it("sends exactly one request however often Approve is clicked while it is in progress", async () => {
    const f = mockApi({ approve: new Promise<never>(() => {}) });
    renderQueue();
    const dialog = await confirmDialog();
    const button = within(dialog).getByRole("button", { name: "Approve" });
    fireEvent.click(button);
    const busy = await within(dialog).findByRole("button", { name: "Approving…" });
    expect((busy as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(busy);
    fireEvent.click(busy);
    expect(calls(f, APPROVE)).toHaveLength(1);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.getByRole("dialog", { name: "Approve Riverside Sports College?" })).toBeTruthy();
  });

  it("409: says it is no longer awaiting approval and refreshes the queue", async () => {
    const f = mockApi({ approve: { status: 409, body: { detail: "organisation is active, nothing to approve" } } });
    const { onNotify } = renderQueue();
    const dialog = await confirmDialog();
    fireEvent.click(within(dialog).getByRole("button", { name: "Approve" }));
    await waitFor(() => expect(onNotify).toHaveBeenCalledWith("Riverside Sports College is no longer awaiting approval."));
    await waitFor(() => expect(calls(f, LIST)).toHaveLength(2));
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("403: explains the missing permission and keeps the dialog open", async () => {
    mockApi({ approve: { status: 403, body: { detail: "requires platform:organisations:manage" } } });
    renderQueue();
    const dialog = await confirmDialog();
    fireEvent.click(within(dialog).getByRole("button", { name: "Approve" }));
    expect(await within(dialog).findByRole("alert")).toBeTruthy();
    expect(within(dialog).getByText("You don't have permission to approve organisations.")).toBeTruthy();
  });

  it("network failure: shows a retryable error and leaves the list untouched", async () => {
    const f = mockApi({ approve: "network-error" });
    renderQueue();
    const dialog = await confirmDialog();
    fireEvent.click(within(dialog).getByRole("button", { name: "Approve" }));
    expect(await within(dialog).findByText("Couldn't reach the service. Please try again.")).toBeTruthy();
    expect(calls(f, LIST)).toHaveLength(1);
    expect((within(dialog).getByRole("button", { name: "Approve" }) as HTMLButtonElement).disabled).toBe(false);
  });
});
