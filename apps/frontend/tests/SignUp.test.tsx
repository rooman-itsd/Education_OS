import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SignUp } from "../src/auth/SignUp";

const TYPES = [{ id: "music-academy", title: "Music Academy", description: "Lessons and recitals." }];

function mockApi() {
  const f = vi.fn((url: string, _init?: RequestInit) => {
    const body = String(url).endsWith("/tenancy/academy-types") ? TYPES : { id: "o1", slug: "riverside" };
    return Promise.resolve({ ok: true, status: String(url).endsWith("/register") ? 201 : 200, statusText: "", json: async () => body } as Response);
  });
  vi.stubGlobal("fetch", f);
  return f;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("SignUp at /app#signup (DPDP consent, #148)", () => {
  it("asks for the terms to be accepted, links both documents, and sends what was ticked", async () => {
    const f = mockApi();
    render(<SignUp onDone={() => {}} onLogin={() => {}} />);
    await screen.findByRole("option", { name: "Music Academy" });

    const box = screen.getByRole("checkbox") as HTMLInputElement;
    expect(box.required).toBe(true);
    expect(box.checked).toBe(false);
    expect(screen.getByRole("link", { name: "Terms of Service" }).getAttribute("href")).toBe("/#/terms");
    expect(screen.getByRole("link", { name: "Privacy Notice" }).getAttribute("href")).toBe("/#/privacy");

    fireEvent.change(screen.getByLabelText("Organisation name"), { target: { value: "Riverside" } });
    fireEvent.change(screen.getByLabelText("Your name"), { target: { value: "Asha Rao" } });
    fireEvent.change(screen.getByLabelText("Work email"), { target: { value: "asha@riverside.example" } });
    fireEvent.change(screen.getByLabelText(/Password/), { target: { value: "Passw0rd!x" } });
    fireEvent.click(box);
    fireEvent.submit(box.closest("form")!);

    await waitFor(() => expect(f.mock.calls.some(([url]) => String(url).endsWith("/tenancy/register"))).toBe(true));
    const call = f.mock.calls.find(([url]) => String(url).endsWith("/tenancy/register"))!;
    expect(JSON.parse(String(call[1]?.body)).accepted_terms).toBe(true);
  });
});
