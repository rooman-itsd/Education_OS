import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { StrictMode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { tokenFromHash, VerifyPage } from "../src/public/pages/VerifyPage";

function mockVerify(status: number, body: unknown) {
  const f = vi.fn((_url: string, _init?: RequestInit) =>
    Promise.resolve({ ok: status < 400, status, statusText: "", json: async () => body } as Response),
  );
  vi.stubGlobal("fetch", f);
  return f;
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  window.history.replaceState(null, "", "/");
});

describe("tokenFromHash", () => {
  it("reads the token query of a #/verify link", () => {
    expect(tokenFromHash("#/verify?token=abc_DEF-123")).toBe("abc_DEF-123");
    expect(tokenFromHash("#/verify")).toBe("");
    expect(tokenFromHash("#/verify?other=1")).toBe("");
  });
});

describe("VerifyPage (#/verify, where the emailed link lands)", () => {
  it("confirms the token from the link at once, removes it from the address bar, and shows waiting for approval", async () => {
    window.history.replaceState(null, "", "/#/verify?token=tok-link-789");
    const f = mockVerify(200, { id: "o1", slug: "riverside", status: "pending_approval" });
    render(<VerifyPage onNavigate={() => {}} />);
    expect(window.location.hash).toBe("#/verify");
    expect(await screen.findByRole("heading", { name: "Waiting for approval" })).toBeTruthy();
    expect(String(f.mock.calls[0]?.[0])).toMatch(/\/tenancy\/register\/verify$/);
    expect(JSON.parse(String(f.mock.calls[0]?.[1]?.body))).toEqual({ token: "tok-link-789" });
  });

  it("keeps the link's token under React StrictMode (initialisers run twice) and confirms it exactly once", async () => {
    window.history.replaceState(null, "", "/#/verify?token=tok-strict");
    const f = mockVerify(200, { id: "o1", slug: "riverside", status: "pending_approval" });
    render(
      <StrictMode>
        <VerifyPage onNavigate={() => {}} />
      </StrictMode>,
    );
    expect(await screen.findByRole("heading", { name: "Waiting for approval" })).toBeTruthy();
    expect(f).toHaveBeenCalledTimes(1);
    expect(JSON.parse(String(f.mock.calls[0]?.[1]?.body))).toEqual({ token: "tok-strict" });
    expect(window.location.hash).toBe("#/verify");
  });

  it("without a token, shows the code form and sends nothing until the visitor submits", async () => {
    window.history.replaceState(null, "", "/#/verify");
    const f = mockVerify(200, { id: "o1", slug: "riverside", status: "pending_approval" });
    render(<VerifyPage onNavigate={() => {}} />);
    expect(screen.getByRole("heading", { name: "Check your email to confirm your address" })).toBeTruthy();
    expect(f).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText("Verification code"), { target: { value: "typed-code" } });
    fireEvent.click(screen.getByRole("button", { name: "Confirm email" }));
    expect(await screen.findByRole("heading", { name: "Waiting for approval" })).toBeTruthy();
  });

  it("an invalid link token shows the error and the form to try again", async () => {
    window.history.replaceState(null, "", "/#/verify?token=old");
    mockVerify(400, { detail: "invalid or expired token" });
    render(<VerifyPage onNavigate={() => {}} />);
    expect(await screen.findByText(/invalid, has expired or has already been used/)).toBeTruthy();
    expect(screen.getByLabelText("Verification code")).toBeTruthy();
  });
});
