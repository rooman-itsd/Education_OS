import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../../src/admin/App";
import { PHOTO_MAX_BYTES, preparePhoto } from "../../src/admin/lib/profileStore";

beforeAll(() => {
  globalThis.ResizeObserver ??= class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
});

describe("My Profile (preview)", () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    sessionStorage.setItem("eos.admin.preview", "1");
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("offline"))));
    act(() => {
      window.location.hash = "/profile";
    });
  });
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("shows the header, read-only organisation and role, and unavailable security features", async () => {
    render(<App />);
    expect(await screen.findByText("Personal Information")).toBeTruthy();
    expect(screen.getByRole("button", { name: /Edit Profile/ })).toBeTruthy();
    expect(screen.getByLabelText("Change profile photo")).toBeTruthy();
    expect(screen.getByText("Organisation Information")).toBeTruthy();
    expect(screen.getByText("Change Password")).toBeTruthy();
    expect(screen.getAllByText("Not available yet").length).toBeGreaterThan(0);
    // No way to change the own role on this page.
    expect(screen.queryByRole("combobox")).toBeNull();
  });

  it("validates required fields, saves details and shows them", async () => {
    render(<App />);
    await screen.findByText("Personal Information");
    fireEvent.click(screen.getByRole("button", { name: /Edit Profile/ }));
    const first = screen.getByLabelText(/First Name/) as HTMLInputElement;
    fireEvent.change(first, { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: /Save Changes/ }));
    expect(screen.getByText("First name is required.")).toBeTruthy();

    fireEvent.change(first, { target: { value: "Asha" } });
    fireEvent.change(screen.getByLabelText(/Last Name/), { target: { value: "Rao" } });
    fireEvent.change(screen.getByLabelText(/Phone Number/), { target: { value: "abc" } });
    fireEvent.click(screen.getByRole("button", { name: /Save Changes/ }));
    expect(screen.getByText(/valid phone number/)).toBeTruthy();

    fireEvent.change(screen.getByLabelText(/Phone Number/), { target: { value: "+91 98765 43210" } });
    fireEvent.change(screen.getByLabelText(/Job Title/), { target: { value: "Registrar" } });
    fireEvent.click(screen.getByRole("button", { name: /Save Changes/ }));
    await waitFor(() => expect(screen.queryByRole("button", { name: /Save Changes/ })).toBeNull());
    expect(screen.getAllByText("Asha Rao").length).toBeGreaterThan(0);
    expect(screen.getByText("+91 98765 43210")).toBeTruthy();
    expect(JSON.parse(localStorage.getItem("eos.admin.profile.preview")!).jobTitle).toBe("Registrar");
  });

  it("cancel keeps the saved values", async () => {
    render(<App />);
    await screen.findByText("Personal Information");
    fireEvent.click(screen.getByRole("button", { name: /Edit Profile/ }));
    fireEvent.change(screen.getByLabelText(/Job Title/), { target: { value: "Changed" } });
    fireEvent.click(screen.getByRole("button", { name: /Cancel/ }));
    expect(screen.queryByText("Changed")).toBeNull();
  });
});

describe("profile photo checks", () => {
  it("refuses other file types and files over the size limit", async () => {
    await expect(preparePhoto(new File(["x"], "a.gif", { type: "image/gif" }))).rejects.toThrow(/JPG, PNG or WebP/);
    const big = new File([new Uint8Array(PHOTO_MAX_BYTES + 1)], "a.png", { type: "image/png" });
    await expect(preparePhoto(big)).rejects.toThrow(/limit is 2 MB/);
  });
});
