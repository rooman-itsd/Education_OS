import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { Application } from "../src/api/client";
import { TrackApplicationPage } from "../src";
import { api, calledHeaders, calledUrl } from "./fetch";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

const tracked: Application = {
  id: "a-1",
  reference_number: "ADM-2026-A1B2C3",
  applicant: { first_name: "Ana", last_name: "Silva", email: "ana@example.com" },
  programme_id: "p-1",
  academic_year: "2026-27",
  status: "offered",
  documents: [
    {
      id: "d-1",
      application_id: "a-1",
      type: "academic_record",
      document_id: "doc-1",
      label: "Grade 12 transcript",
      verification_status: "verified",
      uploaded_at: "2026-10-21T09:00:00+00:00",
    },
  ],
  offer: { id: "o-1", status: "open", note: "Welcome!", offered_at: "2026-10-25T09:00:00+00:00", expires_at: "2026-11-08T00:00:00+00:00" },
  submitted_at: "2026-10-20T09:00:00+00:00",
};

function fill(reference: string, email: string) {
  fireEvent.change(screen.getByLabelText("Reference number"), { target: { value: reference } });
  fireEvent.change(screen.getByLabelText("Email"), { target: { value: email } });
  fireEvent.click(screen.getByRole("button", { name: "Track application" }));
}

describe("Track application page", () => {
  it("looks the application up for the organisation, without a token, and shows status, offer and documents", async () => {
    localStorage.setItem("eos.token", "staff-token");
    const fetchMock = api(tracked);
    vi.stubGlobal("fetch", fetchMock);
    render(<TrackApplicationPage orgSlug="green valley" />);
    fill(" ADM-2026-A1B2C3 ", "ana+test@example.com");

    expect(await screen.findByText("Offer made")).toBeTruthy();
    expect(calledUrl(fetchMock)).toBe(
      "/api/v1/admissions/public/green%20valley/applications/track?reference_number=ADM-2026-A1B2C3&email=ana%2Btest%40example.com",
    );
    expect(calledHeaders(fetchMock).Authorization).toBeUndefined();
    expect(screen.getByText("You have an offer. Accept or decline it before it expires.")).toBeTruthy();
    expect(screen.getByText("Welcome!")).toBeTruthy();
    expect(screen.getByText(/Respond by 8 Nov 2026/)).toBeTruthy();
    expect(screen.getByText("Grade 12 transcript")).toBeTruthy();
    expect(screen.getByText("Verified")).toBeTruthy();
  });

  it("gives one answer for a wrong reference or a wrong email", async () => {
    vi.stubGlobal("fetch", api({}, 404));
    render(<TrackApplicationPage orgSlug="demo" />);
    fill("ADM-2026-000000", "ana@example.com");
    expect(await screen.findByText("No application found")).toBeTruthy();
  });

  it("does not send anything until both fields are filled", () => {
    const fetchMock = api(tracked);
    vi.stubGlobal("fetch", fetchMock);
    render(<TrackApplicationPage orgSlug="demo" />);
    fill("ADM-2026-A1B2C3", "   ");
    expect(screen.getByRole("alert").textContent).toBe("Enter your reference number and email.");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("offers a retry when the service is down", async () => {
    const fetchMock = api({}, 503);
    vi.stubGlobal("fetch", fetchMock);
    render(<TrackApplicationPage orgSlug="demo" />);
    fill("ADM-2026-A1B2C3", "ana@example.com");
    expect(await screen.findByText("Admissions data is not available yet.")).toBeTruthy();
    fetchMock.mockImplementation(async () => ({ ok: true, status: 200, statusText: "", json: async () => tracked }));
    fireEvent.click(screen.getByRole("button", { name: /try again|retry/i }));
    expect(await screen.findByText("Offer made")).toBeTruthy();
  });

  it("shows an empty documents list and no offer panel when there are none", async () => {
    vi.stubGlobal("fetch", api({ ...tracked, status: "submitted", offer: null, documents: [] }));
    render(<TrackApplicationPage orgSlug="demo" />);
    fill("ADM-2026-A1B2C3", "ana@example.com");
    expect(await screen.findByText("No documents yet")).toBeTruthy();
    expect(screen.queryByText("Your offer")).toBeNull();
  });
});
