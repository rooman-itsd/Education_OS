import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { Application, ApplicationDocument, FunnelReport } from "../src/api/client";
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
    ["admissions.application-status", "admissions:self:read", "list", "1x1", ApplicationStatusWidget],
    ["admissions.pending-documents", "admissions:self:read", "list", "1x1", PendingDocumentsWidget],
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

// ---------------------------------------------------------------- application status

const doc = (over: Partial<ApplicationDocument>): ApplicationDocument => ({
  id: "d-1",
  application_id: "a-1",
  type: "academic_record",
  document_id: "doc-1",
  label: "Grade 12 transcript",
  verification_status: "pending",
  uploaded_at: new Date(Date.now() - 3 * 24 * 3600 * 1000).toISOString(),
  ...over,
});

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
  it("lists the applicant's linked application with its status and offer", async () => {
    const fetchMock = api({
      items: [
        application({
          id: "a-1",
          status: "under_review",
          offer: {
            id: "o-1",
            status: "open",
            offered_at: "2026-10-25T10:00:00Z",
          },
        }),
      ],
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<ApplicationStatusWidget role="applicant" />);
    expect(await screen.findByText("ADM-2026-A1B2C3 · Ana Silva")).toBeTruthy();
    const rows = screen.getAllByRole("listitem");
    expect(rows).toHaveLength(1);
    expect(rows[0]?.textContent).toContain("Under review");
    expect(rows[0]?.textContent).toContain("2026-27 · Submitted 20 Oct 2026 · Offer: Open");
    expect(calledUrl(fetchMock)).toBe("/api/v1/admissions/me/applications");
  });

  it("renders a link form when no application is linked, and links on submit", async () => {
    let callCount = 0;
    const fetchMock = vi.fn().mockImplementation(async (url: string, opts?: RequestInit) => {
      callCount++;
      if (opts?.method === "POST") {
        expect(url).toBe("/api/v1/admissions/me/applications");
        expect(JSON.parse(opts.body as string)).toEqual({
          reference_number: "ADM-2026-A1B2C3",
          email: "ana@example.com",
        });
        return {
          ok: true,
          status: 200,
          statusText: "OK",
          json: async () => application({ id: "a-1" }),
        };
      }
      return {
        ok: true,
        status: 200,
        statusText: "OK",
        json: async () => ({ items: callCount > 1 ? [application({ id: "a-1" })] : [] }),
      };
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<ApplicationStatusWidget role="applicant" />);
    expect(await screen.findByRole("form", { name: "Link application" })).toBeTruthy();
    expect(screen.getByText("Link your submitted application to track your status here.")).toBeTruthy();

    fireEvent.change(screen.getByLabelText("Reference number"), { target: { value: "ADM-2026-A1B2C3" } });
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "ana@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Link application" }));

    expect(await screen.findByText("ADM-2026-A1B2C3 · Ana Silva")).toBeTruthy();
  });

  it("shows an error when linking fails with 404", async () => {
    const fetchMock = vi.fn().mockImplementation(async (_url: string, opts?: RequestInit) => {
      if (opts?.method === "POST") {
        return {
          ok: false,
          status: 404,
          statusText: "Not Found",
          json: async () => ({ code: "not_found", message: "application not found" }),
        };
      }
      return { ok: true, status: 200, statusText: "OK", json: async () => ({ items: [] }) };
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<ApplicationStatusWidget role="applicant" />);
    await screen.findByRole("form", { name: "Link application" });

    fireEvent.change(screen.getByLabelText("Reference number"), { target: { value: "ADM-WRONG" } });
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "ana@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: "Link application" }));

    expect(await screen.findByText("No application matches that reference number and email.")).toBeTruthy();
  });

  it("asks to sign in again on 401", async () => {
    vi.stubGlobal("fetch", api({}, 401));
    render(<ApplicationStatusWidget role="applicant" />);
    expect(await screen.findByText("Sign in again to see this.")).toBeTruthy();
  });
});

// ---------------------------------------------------------------- pending documents

describe("admissions.pending-documents", () => {
  it("lists documents from own applications that are pending or rejected", async () => {
    const fetchMock = api({
      items: [
        application({
          documents: [
            doc({ id: "d-1", type: "academic_record", label: "Grade 12 transcript", verification_status: "pending" }),
            doc({ id: "d-2", type: "identity_proof", label: null, verification_status: "pending" }),
            doc({
              id: "d-3",
              type: "other",
              label: "Certificate",
              verification_status: "rejected",
              verification_note: "Blurry scan",
            }),
            doc({ id: "d-4", type: "academic_record", label: "Marksheet", verification_status: "verified" }),
          ],
        }),
      ],
    });
    vi.stubGlobal("fetch", fetchMock);
    render(<PendingDocumentsWidget role="applicant" />);
    expect((await screen.findByLabelText("Documents waiting")).textContent).toBe("3 documents waiting for verification");
    const rows = screen.getAllByRole("listitem");
    expect(rows).toHaveLength(3);
    expect(rows[0]?.textContent).toContain("Academic record · Grade 12 transcript");
    expect(rows[0]?.textContent).toContain("Waiting 3 days");
    expect(rows[1]?.textContent).toContain("Identity proof");
    expect(rows[2]?.textContent).toContain("Rejected: Blurry scan");
    expect(rows[2]?.textContent).toContain("Not accepted");
    expect(calledUrl(fetchMock)).toBe("/api/v1/admissions/me/applications");
  });

  it("has an empty state when no documents are pending or rejected", async () => {
    vi.stubGlobal("fetch", api({ items: [application({ documents: [] })] }));
    render(<PendingDocumentsWidget role="applicant" />);
    expect(await screen.findByText("Nothing waiting for verification")).toBeTruthy();
  });

  it("explains a 500 and lets the user retry", async () => {
    vi.stubGlobal("fetch", api({}, 500));
    render(<PendingDocumentsWidget role="applicant" />);
    expect(await screen.findByText("Could not load documents waiting for verification")).toBeTruthy();
    expect(screen.getByRole("button")).toBeTruthy();
  });
});
