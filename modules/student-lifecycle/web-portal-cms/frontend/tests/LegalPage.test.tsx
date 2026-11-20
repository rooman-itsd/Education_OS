import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PrivacyPage, TermsPage } from "../src/public/pages/LegalPage";
import { SiteFooter } from "../src/public/components/SiteFooter";
import { LEGAL_VERSION, PRIVACY_NOTICE, TERMS_OF_SERVICE } from "../src/public/legal";

afterEach(cleanup);

describe("legal pages (#148, draft pending legal review)", () => {
  it("the version is the one platform/tenancy records at registration (DEFAULT_TERMS_VERSION, #665)", () => {
    expect(LEGAL_VERSION).toBe("2026-11-20");
  });

  it("the privacy notice shows its title, version, every section and the operator's placeholders", () => {
    render(<PrivacyPage onNavigate={() => {}} />);
    expect(screen.getByRole("heading", { level: 1, name: "Privacy Notice" })).toBeTruthy();
    expect(screen.getByText(new RegExp(`Version ${LEGAL_VERSION}`))).toBeTruthy();
    for (const s of PRIVACY_NOTICE.sections) {
      expect(screen.getByRole("heading", { level: 2, name: s.heading })).toBeTruthy();
    }
    const text = document.body.textContent ?? "";
    for (const placeholder of ["[Company legal name]", "[Registered address]", "[Grievance Officer name, email]"]) {
      expect(text).toContain(placeholder);
    }
    expect(text).toContain("Data Protection Board of India");
  });

  it("the terms show every section and link to the privacy notice", () => {
    const onNavigate = vi.fn();
    render(<TermsPage onNavigate={onNavigate} />);
    expect(screen.getByRole("heading", { level: 1, name: "Terms of Service" })).toBeTruthy();
    for (const s of TERMS_OF_SERVICE.sections) {
      expect(screen.getByRole("heading", { level: 2, name: s.heading })).toBeTruthy();
    }
    fireEvent.click(screen.getByRole("link", { name: "Privacy Notice" }));
    expect(onNavigate).toHaveBeenCalledWith("privacy");
  });

  it("a contents link scrolls to its section and leaves the route alone", () => {
    const scrolled = vi.fn();
    Element.prototype.scrollIntoView = scrolled;
    const onNavigate = vi.fn();
    render(<PrivacyPage onNavigate={onNavigate} />);
    const contents = screen.getByRole("navigation", { name: "Contents" });
    const first = contents.querySelector("a")!;
    expect(first.getAttribute("href")).toBe("#/privacy");
    fireEvent.click(first);
    expect(scrolled).toHaveBeenCalledTimes(1);
    expect(onNavigate).not.toHaveBeenCalled();
  });

  it("the footer's legal links open the two pages", () => {
    const onNavigate = vi.fn();
    render(<SiteFooter onNavigate={onNavigate} />);
    const legal = screen.getByRole("navigation", { name: "Legal" });
    const privacy = Array.from(legal.querySelectorAll("a")).find((a) => a.textContent === "Privacy notice")!;
    const terms = Array.from(legal.querySelectorAll("a")).find((a) => a.textContent === "Terms of service")!;
    expect(privacy.getAttribute("href")).toBe("#/privacy");
    expect(terms.getAttribute("href")).toBe("#/terms");
    fireEvent.click(privacy);
    fireEvent.click(terms);
    expect(onNavigate.mock.calls).toEqual([["privacy"], ["terms"]]);
  });
});
