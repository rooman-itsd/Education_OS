import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { timeAgo, type WorkflowRequest } from "../src/api/client";
import { widgets } from "../src/widgets";
import { ApprovalsPending, SHOWN } from "../src/widgets/ApprovalsPending";

const req = (over: Partial<WorkflowRequest> = {}): WorkflowRequest => ({
  id: "req-1",
  organisation_id: "org-1",
  chain_id: "chain-1",
  entity_type: "leave",
  entity_id: "l-1",
  title: "Faculty Leave: Dr. Sharma",
  description: "Annual leave request",
  requester_id: "u-1",
  requester_name: "Dr. Sharma",
  current_step_order: 1,
  status: "pending",
  submitted_at: new Date(Date.now() - 10 * 60_000).toISOString(),
  current_step_deadline: new Date(Date.now() + 24 * 3600_000).toISOString(),
  is_overdue: false,
  context: {},
  ...over,
});

function answer(status: number, body: unknown) {
  return vi.fn().mockResolvedValue({ ok: status < 400, status, statusText: "", json: async () => body });
}

beforeEach(() => localStorage.setItem("eos.token", "test-token"));
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("workflow.approvals-pending", () => {
  it("is exported with the id and permission the Department Admin layout expects", () => {
    const w = widgets.find((x) => x.id === "workflow.approvals-pending");
    expect(w?.permission).toBe("workflow:request:read");
    expect(w?.kind).toBe("list");
    expect(w?.component).toBe(ApprovalsPending);
  });

  it("lists pending approvals with requester and timing", async () => {
    const fetchMock = answer(200, {
      items: [
        req(),
        req({
          id: "req-2",
          entity_type: "procurement",
          title: "Lab Equipment Purchase",
          requester_name: "Prof. Verma",
          is_overdue: true,
        }),
      ],
      total: 2,
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<ApprovalsPending role="department-admin" />);

    expect(await screen.findByText("Faculty Leave: Dr. Sharma")).toBeTruthy();
    expect(screen.getByText("Leave · Dr. Sharma · Submitted 10 min ago")).toBeTruthy();
    expect(screen.getByText("Lab Equipment Purchase")).toBeTruthy();
    expect(screen.getByText("Procurement · Prof. Verma · Overdue")).toBeTruthy();

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(`/api/v1/workflow/requests/pending?limit=${SHOWN}`);
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer test-token");
  });

  it("displays empty state when there are no pending requests", async () => {
    vi.stubGlobal("fetch", answer(200, { items: [], total: 0 }));
    render(<ApprovalsPending role="department-admin" />);
    expect(await screen.findByText("No pending approvals")).toBeTruthy();
    expect(screen.getByText("You have reviewed all pending workflow items.")).toBeTruthy();
  });

  it("displays error state with retry when service is not reachable", async () => {
    vi.stubGlobal("fetch", answer(404, { detail: "Not Found" }));
    render(<ApprovalsPending role="department-admin" />);
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Workflow data is not available yet.");
    expect(screen.getByRole("button", { name: "Try again" })).toBeTruthy();
  });

  it("timeAgo formats timestamps correctly", () => {
    const now = new Date("2026-10-30T12:00:00Z");
    expect(timeAgo("2026-10-30T11:59:45Z", now)).toBe("just now");
    expect(timeAgo("2026-10-30T11:45:00Z", now)).toBe("15 min ago");
    expect(timeAgo("2026-10-30T08:00:00Z", now)).toBe("4 h ago");
    expect(timeAgo("2026-10-28T12:00:00Z", now)).toBe("2 d ago");
  });
});

