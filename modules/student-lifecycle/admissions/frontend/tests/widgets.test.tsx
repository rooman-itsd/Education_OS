import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Application, DocumentQueueItem, FunnelReport } from "../src/api/client";
import { widgets } from "../src/widgets";
import { ApplicationStatusWidget } from "../src/widgets/ApplicationStatusWidget";
import { FunnelWidget } from "../src/widgets/FunnelWidget";
import { PendingDocumentsWidget } from "../src/widgets/PendingDocumentsWidget";
import { api, calledHeaders, calledUrl } from "./fetch";

beforeEach(() => localStorage.setItem("eos.token", "test-token"));
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

describe("widget registrations", () => {
  it.each([
    ["admissions.funnel", "admissions:report:read", "chart", "2x1", FunnelWidget],
    ["admissions.application-status", "admissions:application:read", "list", "1x1", ApplicationStatusWidget],
    ["admissions.pending-documents", "admissions:document:verify", "list", "1x1", PendingDocumentsWidget],
  ])("%s is exported with the permission, kind and size the layouts expect", (id, permission, kind, size, component) => {
    const w = widgets.find((x) => x.id === id);
    expect(w).toMatchObject({ permission, kind, size, component });
  });

  it("exports exactly the three widgets this module owns", () => {
    expect(widgets.map((w) => w.id).sort()).toEqual([
      "admissions.application-status",
      "admissions.funnel",
      "admissions.pending-documents",
    ]);
  });
});

// ---------------------------------------------------------------- funnel

const funnel = (over: Partial<FunnelReport> = {}): FunnelReport => ({
  total: 40,
  stages: { applied: 40, eligible: 20, offered: 10, accepted: 5 },
  by_status: {},
  ...over,
});

describe("admissions.funnel", () => {
  it("shows each stage against everyone who applied, and the overall acceptance", async () => {
    const fetchMock = api(funnel());
    vi.stubGlobal("fetch", fetchMock);
    render(<FunnelWidget role="management" />);
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    expect((await screen.findByLabelText("Funnel summary")).textContent).toContain("12.5%");
    expect(screen.getByLabelText("Funnel summary").textContent).toContain("40 applications");
    for (const stage of ["Applied", "Eligible", "Offered", "Accepted"]) expect(screen.getByText(stage)).toBeTruthy();
    for (const share of ["100%", "50%", "25%", "12.5%"]) expect(screen.getAllByText(share).length).toBeGreaterThan(0);
    expect(calledUrl(fetchMock)).toBe("/api/v1/admissions/reports/funnel");
    expect(calledHeaders(fetchMock).Authorization).toBe("Bearer test-token");
  });

  it("says so when there are no applications", async () => {
    vi.stubGlobal("fetch", api(funnel({ total: 0, stages: { applied: 0, eligible: 0, offered: 0, accepted: 0 } })));
    render(<FunnelWidget role="management" />);
    expect(await screen.findByText("No applications yet")).toBeTruthy();
  });

  it("does not offer a retry that cannot help (403)", async () => {
    vi.stubGlobal("fetch", api({}, 403));
    render(<FunnelWidget role="management" />);
    expect(await screen.findByText("You do not have access to this.")).toBeTruthy();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("retries when the service is not available yet", async () => {
    const fetchMock = api({}, 503);
    vi.stubGlobal("fetch", fetchMock);
    render(<FunnelWidget role="management" />);
    expect(await screen.findByText("Admissions data is not available yet.")).toBeTruthy();
    fetchMock.mockImplementation(async () => ({ ok: true, status: 200, statusText: "", json: async () => funnel() }));
    fireEvent.click(screen.getByRole("button"));
    expect(await screen.findByLabelText("Funnel summary")).toBeTruthy();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });
});

// ---------------------------------------------------------------- latest applications

const application = (over: Partial<Application>): Application => ({
  id: "a-1",
  reference_number: "ADM-2026-A1B2C3",
  applicant: { first_name: "Ana", last_name: "Silva", email: "ana@example.com" },
  programme_id: "p-1",
  academic_year: "2026-27",
  status: "submitted",
  documents: [],
  offer: null,
  submitted_at: "2026-10-20T09:00:00+00:00",
  ...over,
});

describe("admissions.application-status", () => {
  it("lists the newest applications in the API's order with their status in words", async () => {
    const fetchMock = api({
      items: [
        application({ id: "a-1", status: "under_review" }),
        application({ id: "a-2", reference_number: "ADM-2026-D4E5F6", status: "accepted" }),
      ],
      total: 2,
      page: 1,
      page_size: 6,
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<ApplicationStatusWidget role="admissions-staff" />);
    expect(await screen.findByText("ADM-2026-A1B2C3 · Ana Silva")).toBeTruthy();
    const rows = screen.getAllByRole("listitem");
    expect(rows).toHaveLength(2);
    expect(rows[0]?.textContent).toContain("Under review");
    expect(rows[0]?.textContent).toContain("2026-27 · Submitted 20 Oct 2026");
    expect(rows[1]?.textContent).toContain("Accepted");
    expect(calledUrl(fetchMock)).toBe("/api/v1/admissions/applications?page_size=6");
  });

  it("counts the rest and shows an unknown status as its own word", async () => {
    const items = [application({ status: "on_hold" as Application["status"] })];
    vi.stubGlobal("fetch", api({ items, total: 9, page: 1, page_size: 6 }));
    render(<ApplicationStatusWidget role="admissions-staff" />);
    expect(await screen.findByText("on_hold")).toBeTruthy();
    expect(screen.getByText("8 more")).toBeTruthy();
  });

  it("has an empty state and asks to sign in again on 401", async () => {
    vi.stubGlobal("fetch", api({ items: [], total: 0, page: 1, page_size: 6 }));
    render(<ApplicationStatusWidget role="admissions-staff" />);
    expect(await screen.findByText("No applications yet")).toBeTruthy();
    cleanup();
    vi.stubGlobal("fetch", api({}, 401));
    render(<ApplicationStatusWidget role="admissions-staff" />);
    expect(await screen.findByText("Sign in again to see this.")).toBeTruthy();
  });
});

// ---------------------------------------------------------------- documents to verify

const doc = (over: Partial<DocumentQueueItem>): DocumentQueueItem => ({
  id: "d-1",
  application_id: "a-1",
  type: "academic_record",
  document_id: "doc-1",
  label: "Grade 12 transcript",
  verification_status: "pending",
  uploaded_at: new Date(Date.now() - 3 * 24 * 3600 * 1000).toISOString(),
  reference_number: "ADM-2026-A1B2C3",
  applicant_name: "Ana Silva",
  ...over,
});

describe("admissions.pending-documents", () => {
  it("lists the longest waiting first with type, label and how long it has waited", async () => {
    const fetchMock = api({ items: [doc({}), doc({ id: "d-2", type: "identity_proof", label: null })], total: 2, page: 1, page_size: 6 });
    vi.stubGlobal("fetch", fetchMock);
    render(<PendingDocumentsWidget role="admissions-reviewer" />);
    expect((await screen.findByLabelText("Documents waiting")).textContent).toBe("2 documents waiting for verification");
    const rows = screen.getAllByRole("listitem");
    expect(rows[0]?.textContent).toContain("Academic record · Grade 12 transcript");
    expect(rows[0]?.textContent).toContain("Waiting 3 days");
    expect(rows[1]?.textContent).toContain("Identity proof");
    expect(calledUrl(fetchMock)).toBe("/api/v1/admissions/documents?verification_status=pending&page_size=6");
  });

  it("has an empty state", async () => {
    vi.stubGlobal("fetch", api({ items: [], total: 0, page: 1, page_size: 6 }));
    render(<PendingDocumentsWidget role="admissions-reviewer" />);
    expect(await screen.findByText("Nothing waiting for verification")).toBeTruthy();
  });

  it("explains a 500 and lets the user retry", async () => {
    vi.stubGlobal("fetch", api({}, 500));
    render(<PendingDocumentsWidget role="admissions-reviewer" />);
    expect(await screen.findByText("Could not load documents waiting for verification")).toBeTruthy();
    expect(screen.getByRole("button")).toBeTruthy();
  });
});
