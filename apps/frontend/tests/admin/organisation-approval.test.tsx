import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { OrganisationApprovalQueue } from "../../src/admin/components/organisations/OrganisationApprovalQueue";

const ORGS = [
  { id: "o1", name: "Riverside Sports College", slug: "riverside", academy_type: "sports-college", requested_academy_type: null, country: "IN", status: "pending_approval", status_reason: null, created_at: "2026-10-20T09:00:00+00:00", plan: "trial", trial_ends_at: "2026-11-19T09:00:00+00:00" },
  { id: "o2", name: "Hilltop Music Academy", slug: "hilltop", academy_type: "music-academy", requested_academy_type: null, country: null, status: "pending_approval", status_reason: null, created_at: "2026-10-21T09:00:00+00:00", plan: "trial", trial_ends_at: null },
];
const UNVERIFIED = { id: "o3", name: "Lakeside Dance School", slug: "lakeside", academy_type: "sports-college", requested_academy_type: null, country: "IN", status: "pending_verification", status_reason: null, created_at: "2026-10-22T09:00:00+00:00", plan: "trial", trial_ends_at: null };
const DETAIL = { ...ORGS[0], entitlement: { modules: [], status: "pending_approval", subscription_status: "trialing", trial_ends_at: "2026-11-19T09:00:00+00:00" } };

type Reply = { status: number; body?: unknown } | "network-error" | Promise<never>;
const respond = (status: number, body: unknown) =>
  Promise.resolve({ ok: status < 400, status, statusText: "", json: async () => body } as Response);

/** fetch stub routed by path; `list` may be a sequence, one reply per call (the last repeats). */
function mockApi({
  list = [{ status: 200, body: ORGS }] as Reply[],
  unverified = { status: 200, body: [] } as Reply,
  detail = { status: 200, body: DETAIL } as Reply,
  approve = { status: 200, body: { ...ORGS[0], status: "active" } } as Reply,
  reject = { status: 200, body: { ...ORGS[0], status: "archived" } } as Reply,
} = {}) {
  let listCalls = 0;
  const pick = (r: Reply) => (r === "network-error" ? Promise.reject(new TypeError("Failed to fetch")) : r instanceof Promise ? r : respond(r.status, r.body));
  const f = vi.fn((url: string, _init?: RequestInit) => {
    if (url.endsWith("/tenancy/admin/organisations?status=pending_approval")) return pick(list[Math.min(listCalls++, list.length - 1)]!);
    if (url.endsWith("/tenancy/admin/organisations?status=pending_verification")) return pick(unverified);
    if (/\/approve$/.test(url)) return pick(approve);
    if (/\/status$/.test(url)) return pick(reject);
    if (/\/tenancy\/admin\/organisations\/[^/?]+$/.test(url)) return pick(detail);
    return Promise.reject(new Error(`unexpected ${url}`));
  });
  vi.stubGlobal("fetch", f);
  return f;
}
const calls = (f: ReturnType<typeof mockApi>, re: RegExp) => f.mock.calls.filter(([u]) => re.test(String(u)));
const LIST = /\?status=pending_approval$/;
const UNVERIFIED_LIST = /\?status=pending_verification$/;
const APPROVE = /\/approve$/;
const REJECT = /\/status$/;
const body = (call: unknown[]) => JSON.parse(String((call[1] as RequestInit).body));
const button = (scope: HTMLElement, name: string) => within(scope).getByRole("button", { name }) as HTMLButtonElement;

beforeEach(() => localStorage.setItem("eos.token", "super-admin-token"));
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

function renderQueue(props: Partial<React.ComponentProps<typeof OrganisationApprovalQueue>> = {}) {
  const onNotify = vi.fn();
  const onCountChange = vi.fn();
  const onSessionExpired = vi.fn();
  render(<OrganisationApprovalQueue onNotify={onNotify} onCountChange={onCountChange} onSessionExpired={onSessionExpired} {...props} />);
  return { onNotify, onCountChange, onSessionExpired };
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
    expect(calls(f, UNVERIFIED_LIST)).toHaveLength(1);
  });

  it("lists unverified registrations as waiting, newest first, without counting them", async () => {
    mockApi({ unverified: { status: 200, body: [UNVERIFIED] } });
    const { onCountChange } = renderQueue();
    expect(await screen.findByText("Lakeside Dance School")).toBeTruthy();
    expect(screen.getByText("Waiting for email verification")).toBeTruthy();
    expect(screen.getAllByText("Awaiting approval")).toHaveLength(2);
    const names = screen.getAllByRole("button", { name: /^Review / }).map((b) => b.getAttribute("aria-label"));
    expect(names).toEqual(["Review Lakeside Dance School", "Review Hilltop Music Academy", "Review Riverside Sports College"]);
    expect(onCountChange).toHaveBeenLastCalledWith(2);
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

  it("401 on the list: says the session has expired and reports it", async () => {
    mockApi({ list: [{ status: 401, body: { detail: "token expired" } }] });
    const { onSessionExpired } = renderQueue();
    expect(await screen.findByText("Your session has expired. Sign in again.")).toBeTruthy();
    expect(onSessionExpired).toHaveBeenCalledTimes(1);
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
    expect(button(drawer, "Approve").disabled).toBe(false);
    expect(button(drawer, "Reject").disabled).toBe(false);
  });

  it("shows the administrator's email when the API returns it (contract field admin_email)", async () => {
    mockApi({ detail: { status: 200, body: { ...DETAIL, admin_email: "asha@riverside.example.com" } } });
    renderQueue();
    const drawer = await openReview();
    expect(await within(drawer).findByText("asha@riverside.example.com")).toBeTruthy();
  });

  it("an unverified registration can be reviewed but not decided on", async () => {
    mockApi({ unverified: { status: 200, body: [UNVERIFIED] }, detail: { status: 200, body: { ...UNVERIFIED, entitlement: {} } } });
    renderQueue();
    const drawer = await openReview("Lakeside Dance School");
    await within(drawer).findByText("lakeside");
    expect(within(drawer).getByText("Waiting for email verification")).toBeTruthy();
    expect(within(drawer).getByText("No")).toBeTruthy();
    expect(within(drawer).getByText("Waiting for the administrator to verify their email.")).toBeTruthy();
    expect(button(drawer, "Approve").disabled).toBe(true);
    expect(button(drawer, "Reject").disabled).toBe(true);
  });

  it("follows the fetched status, not the list row: an organisation decided on elsewhere cannot be approved", async () => {
    mockApi({ detail: { status: 200, body: { ...DETAIL, status: "active" } } });
    renderQueue();
    const drawer = await openReview();
    await within(drawer).findByText("riverside");
    expect(within(drawer).getByText("No longer awaiting approval.")).toBeTruthy();
    expect(button(drawer, "Approve").disabled).toBe(true);
    expect(button(drawer, "Reject").disabled).toBe(true);
  });

  it("drops a late detail response: slow Riverside, then Hilltop, never shows Riverside in Hilltop's drawer", async () => {
    let resolveSlow!: (r: Response) => void;
    const f = mockApi();
    f.mockImplementation((url: string) => {
      if (url.endsWith("?status=pending_approval")) return respond(200, ORGS);
      if (url.endsWith("?status=pending_verification")) return respond(200, []);
      if (url.endsWith("/o1")) return new Promise<Response>((r) => { resolveSlow = r; });
      if (url.endsWith("/o2")) return respond(200, { ...ORGS[1], entitlement: {} });
      return Promise.reject(new Error(`unexpected ${url}`));
    });
    renderQueue();
    await openReview();
    fireEvent.keyDown(document, { key: "Escape" });
    const drawer = await openReview("Hilltop Music Academy");
    await within(drawer).findByText("hilltop");
    resolveSlow(await respond(200, DETAIL));
    await new Promise((r) => setTimeout(r, 20));
    expect(within(drawer).queryByText("riverside")).toBeNull();
    expect(within(drawer).getByText("hilltop")).toBeTruthy();
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
    fireEvent.click(button(drawer, "Approve"));
    return screen.findByRole("dialog", { name: "Approve Riverside Sports College?" });
  }

  it("asks for confirmation, approves, notifies, and refreshes the list and count", async () => {
    const f = mockApi({ list: [{ status: 200, body: ORGS }, { status: 200, body: [ORGS[1]] }] });
    const { onNotify, onCountChange } = renderQueue();
    const dialog = await confirmDialog();
    expect(calls(f, APPROVE)).toHaveLength(0);
    fireEvent.click(button(dialog, "Approve"));
    await waitFor(() => expect(onNotify).toHaveBeenCalledWith("Riverside Sports College approved. Its administrator can now sign in."));
    expect(body(calls(f, APPROVE)[0]!)).toEqual({});
    expect(calls(f, REJECT)).toHaveLength(0);
    await waitFor(() => expect(onCountChange).toHaveBeenLastCalledWith(1));
    expect(screen.queryByText("Riverside Sports College")).toBeNull();
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("sends the optional reason when one is given", async () => {
    const f = mockApi();
    renderQueue();
    const dialog = await confirmDialog();
    fireEvent.change(within(dialog).getByLabelText("Reason (optional)"), { target: { value: "  verified institution " } });
    fireEvent.click(button(dialog, "Approve"));
    await waitFor(() => expect(calls(f, APPROVE)).toHaveLength(1));
    expect(body(calls(f, APPROVE)[0]!)).toEqual({ reason: "verified institution" });
  });

  it("sends exactly one request however often Approve is clicked while it is in progress", async () => {
    const f = mockApi({ approve: new Promise<never>(() => {}) });
    renderQueue();
    const dialog = await confirmDialog();
    fireEvent.click(button(dialog, "Approve"));
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
    fireEvent.click(button(dialog, "Approve"));
    await waitFor(() => expect(onNotify).toHaveBeenCalledWith("Riverside Sports College is no longer awaiting approval."));
    await waitFor(() => expect(calls(f, LIST)).toHaveLength(2));
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("403: explains the missing permission and keeps the dialog open", async () => {
    mockApi({ approve: { status: 403, body: { detail: "requires platform:organisations:manage" } } });
    renderQueue();
    const dialog = await confirmDialog();
    fireEvent.click(button(dialog, "Approve"));
    expect(await within(dialog).findByRole("alert")).toBeTruthy();
    expect(within(dialog).getByText("You don't have permission to approve organisations.")).toBeTruthy();
    expect(button(dialog, "Approve").disabled).toBe(false);
  });

  it("401: says the session has expired and reports it", async () => {
    mockApi({ approve: { status: 401, body: { detail: "token expired" } } });
    const { onSessionExpired } = renderQueue();
    const dialog = await confirmDialog();
    fireEvent.click(button(dialog, "Approve"));
    expect(await within(dialog).findByText("Your session has expired. Sign in again.")).toBeTruthy();
    expect(onSessionExpired).toHaveBeenCalledTimes(1);
  });

  it("network failure: shows a retryable error and leaves the list untouched", async () => {
    const f = mockApi({ approve: "network-error" });
    renderQueue();
    const dialog = await confirmDialog();
    fireEvent.click(button(dialog, "Approve"));
    expect(await within(dialog).findByText("Couldn't reach the service. Please try again.")).toBeTruthy();
    expect(calls(f, LIST)).toHaveLength(1);
    expect(button(dialog, "Approve").disabled).toBe(false);
  });
});

describe("OrganisationApprovalQueue: rejecting through PUT /{id}/status", () => {
  async function rejectDialog() {
    const drawer = await openReview();
    await within(drawer).findByText("riverside");
    fireEvent.click(button(drawer, "Reject"));
    return screen.findByRole("dialog", { name: "Reject Riverside Sports College?" });
  }

  it("requires a reason: nothing is sent until one is typed", async () => {
    const f = mockApi();
    renderQueue();
    const dialog = await rejectDialog();
    expect(button(dialog, "Reject").disabled).toBe(true);
    fireEvent.click(button(dialog, "Reject"));
    fireEvent.change(within(dialog).getByLabelText("Reason (required)"), { target: { value: "   " } });
    expect(button(dialog, "Reject").disabled).toBe(true);
    expect(calls(f, REJECT)).toHaveLength(0);
    expect(calls(f, APPROVE)).toHaveLength(0);
  });

  it("archives with the trimmed reason, notifies, and refreshes the list and count", async () => {
    const f = mockApi({ list: [{ status: 200, body: ORGS }, { status: 200, body: [ORGS[1]] }] });
    const { onNotify, onCountChange } = renderQueue();
    const dialog = await rejectDialog();
    fireEvent.change(within(dialog).getByLabelText("Reason (required)"), { target: { value: "  not an institution " } });
    fireEvent.click(button(dialog, "Reject"));
    await waitFor(() => expect(onNotify).toHaveBeenCalledWith("Riverside Sports College rejected. Its registration is archived."));
    const call = calls(f, REJECT)[0]!;
    expect(String(call[0])).toMatch(/\/tenancy\/admin\/organisations\/o1\/status$/);
    expect((call[1] as RequestInit).method).toBe("PUT");
    expect(body(call)).toEqual({ status: "archived", reason: "not an institution" });
    expect(calls(f, APPROVE)).toHaveLength(0);
    await waitFor(() => expect(onCountChange).toHaveBeenLastCalledWith(1));
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("403: explains the missing permission and keeps the dialog open", async () => {
    mockApi({ reject: { status: 403, body: { detail: "requires platform:organisations:manage" } } });
    renderQueue();
    const dialog = await rejectDialog();
    fireEvent.change(within(dialog).getByLabelText("Reason (required)"), { target: { value: "spam" } });
    fireEvent.click(button(dialog, "Reject"));
    expect(await within(dialog).findByText("You don't have permission to reject organisations.")).toBeTruthy();
    expect(button(dialog, "Reject").disabled).toBe(false);
  });

  it("network failure: shows a retryable error and leaves the list untouched", async () => {
    const f = mockApi({ reject: "network-error" });
    renderQueue();
    const dialog = await rejectDialog();
    fireEvent.change(within(dialog).getByLabelText("Reason (required)"), { target: { value: "spam" } });
    fireEvent.click(button(dialog, "Reject"));
    expect(await within(dialog).findByText("Couldn't reach the service. Please try again.")).toBeTruthy();
    expect(calls(f, LIST)).toHaveLength(1);
    expect(button(dialog, "Reject").disabled).toBe(false);
  });
});
