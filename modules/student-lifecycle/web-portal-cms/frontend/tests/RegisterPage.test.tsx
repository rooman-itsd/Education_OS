import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { RegisterPage } from "../src/public/pages/RegisterPage";

const TYPES = [
  { id: "music-academy", title: "Music Academy / Conservatory", description: "Lessons and recitals.", specialized_suites: [] },
  { id: "sports-college", title: "Sports University / Sports College", description: "Sports.", specialized_suites: ["sports"] },
];

type Reply = { status: number; body?: unknown } | "network-error" | Promise<never>;

const json = (status: number, body: unknown) =>
  Promise.resolve({ ok: status < 400, status, statusText: "", json: async () => body } as Response);

/** What tenancy returns from POST /register in production: the token goes by email, not in the body. */
const REGISTERED = { id: "o1", slug: "riverside-sports-college", name: "Riverside Sports College", academy_type: "sports-college", status: "pending_verification" };
/** The same in dev mode (EOS_DEV_MODE=true): the token is in the body. */
const REGISTERED_DEV = { ...REGISTERED, verification_token: "tok-dev-123" };
const VERIFIED = { id: "o1", slug: "riverside-sports-college", status: "pending_approval" };

/**
 * fetch stub routed by path: GET /tenancy/academy-types, POST /tenancy/register and POST
 * /tenancy/register/verify answer as given; "network-error" rejects like an unreachable server.
 * Every call goes through the real public-client.
 */
function mockApi({
  types = { status: 200, body: TYPES } as Reply,
  register = { status: 201, body: REGISTERED_DEV } as Reply,
  verify = { status: 200, body: VERIFIED } as Reply,
} = {}) {
  const fetchMock = vi.fn((url: string, _init?: RequestInit) => {
    const reply = url.endsWith("/tenancy/academy-types")
      ? types
      : url.endsWith("/tenancy/register")
        ? register
        : url.endsWith("/tenancy/register/verify")
          ? verify
          : null;
    if (!reply) return Promise.reject(new Error(`unexpected ${url}`));
    if (reply === "network-error") return Promise.reject(new TypeError("Failed to fetch"));
    if (reply instanceof Promise) return reply;
    return json(reply.status, reply.body);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const registerCalls = (f: ReturnType<typeof mockApi>) => f.mock.calls.filter(([url]) => String(url).endsWith("/tenancy/register"));
const verifyCalls = (f: ReturnType<typeof mockApi>) => f.mock.calls.filter(([url]) => String(url).endsWith("/tenancy/register/verify"));
const verifyBody = (f: ReturnType<typeof mockApi>, i = 0) => JSON.parse(String(verifyCalls(f)[i]![1]?.body));

async function renderReady() {
  render(<RegisterPage onNavigate={() => {}} />);
  await screen.findByRole("radio", { name: /Sports University/ });
}

function fillValidForm() {
  fireEvent.click(screen.getByRole("radio", { name: /Sports University/ }));
  fireEvent.change(screen.getByLabelText("Organisation name"), { target: { value: "  Riverside Sports College " } });
  fireEvent.change(screen.getByLabelText("Full name"), { target: { value: " Asha Rao " } });
  fireEvent.change(screen.getByLabelText("Work email"), { target: { value: " asha@riverside.example.com " } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: "Passw0rd!x" } });
  fireEvent.click(screen.getByRole("checkbox"));
}

const submit = () => fireEvent.click(screen.getByRole("button", { name: /Submit registration/ }));

// jsdom has no scrolling; the page scrolls to the top after a successful submit.
beforeEach(() => {
  vi.stubGlobal("scrollTo", vi.fn());
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("RegisterPage: loading the academy packages", () => {
  it("shows a loader, then one card per type from GET /tenancy/academy-types", async () => {
    const f = mockApi();
    render(<RegisterPage onNavigate={() => {}} />);
    expect(screen.getByText("Loading academy packages…")).toBeTruthy();
    expect(await screen.findAllByRole("radio")).toHaveLength(2);
    expect(String(f.mock.calls[0]?.[0])).toMatch(/\/tenancy\/academy-types$/);
  });

  it("shows an error with a retry when the packages can't be loaded, and recovers on retry", async () => {
    const f = mockApi({ types: "network-error" });
    render(<RegisterPage onNavigate={() => {}} />);
    expect(await screen.findByText("Couldn't load academy packages")).toBeTruthy();
    f.mockImplementation((url: string, _init?: RequestInit) =>
      url.endsWith("/tenancy/academy-types") ? json(200, TYPES) : Promise.reject(new Error(url)),
    );
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findAllByRole("radio")).toHaveLength(2);
  });
});

describe("RegisterPage: the form", () => {
  it("suggests the short name from the organisation name until the visitor edits it", async () => {
    mockApi();
    await renderReady();
    const slug = screen.getByLabelText("Short name") as HTMLInputElement;
    fireEvent.change(screen.getByLabelText("Organisation name"), { target: { value: "Riverside Sports" } });
    expect(slug.value).toBe("riverside-sports");
    fireEvent.change(slug, { target: { value: "RIVER" } });
    expect(slug.value).toBe("river");
    fireEvent.change(screen.getByLabelText("Organisation name"), { target: { value: "Something Else" } });
    expect(slug.value).toBe("river");
  });

  it("selecting a card checks it", async () => {
    mockApi();
    await renderReady();
    const music = screen.getByRole("radio", { name: /Music Academy/ }) as HTMLInputElement;
    fireEvent.click(music);
    expect(music.checked).toBe(true);
  });

  it("does not submit an invalid form: shows every error and focuses the package picker first", async () => {
    const f = mockApi();
    await renderReady();
    submit();
    expect(await screen.findByText("Choose your academy package.")).toBeTruthy();
    expect(screen.getByText("Accept the terms to continue.")).toBeTruthy();
    expect(screen.getByLabelText("Password").getAttribute("aria-invalid")).toBe("true");
    expect(document.activeElement).toBe(screen.getAllByRole("radio")[0]);
    expect(registerCalls(f)).toHaveLength(0);
  });

  it("rejects a malformed email before sending anything", async () => {
    const f = mockApi();
    await renderReady();
    fillValidForm();
    fireEvent.change(screen.getByLabelText("Work email"), { target: { value: "asha..rao@riverside" } });
    submit();
    expect(await screen.findByText(/Enter a valid email address/)).toBeTruthy();
    expect(screen.getByLabelText("Work email").getAttribute("aria-invalid")).toBe("true");
    expect(registerCalls(f)).toHaveLength(0);
  });

  it("caps the name and email inputs at the server's column lengths", async () => {
    mockApi();
    await renderReady();
    expect(screen.getByLabelText("Organisation name").getAttribute("maxlength")).toBe("200");
    expect(screen.getByLabelText("Full name").getAttribute("maxlength")).toBe("200");
    expect(screen.getByLabelText("Work email").getAttribute("maxlength")).toBe("254");
    expect(screen.getByLabelText("Short name").getAttribute("maxlength")).toBe("40");
  });

  it("clears a field's error as soon as it is fixed after a failed submit", async () => {
    mockApi();
    await renderReady();
    submit();
    expect(await screen.findByText("Use at least 8 characters.")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Password"), { target: { value: "Passw0rd!x" } });
    expect(screen.queryByText("Use at least 8 characters.")).toBeNull();
  });
});

describe("RegisterPage: submitting to POST /tenancy/register", () => {
  it("sends exactly the contract's fields (trimmed, terms accepted, no plan)", async () => {
    const f = mockApi();
    await renderReady();
    fillValidForm();
    submit();
    await screen.findByRole("heading", { name: "Waiting for approval" });

    const [, init] = registerCalls(f)[0]!;
    expect(init?.method).toBe("POST");
    expect(JSON.parse(String(init?.body))).toEqual({
      organisation_name: "Riverside Sports College",
      slug: "riverside-sports-college",
      academy_type: "sports-college",
      admin: { name: "Asha Rao", email: "asha@riverside.example.com", password: "Passw0rd!x" },
      accepted_terms: true,
    });
  });

  it("dev mode: verifies with the token from the register response, then shows 'Waiting for approval' with the short name", async () => {
    const f = mockApi({ register: { status: 201, body: REGISTERED_DEV } });
    await renderReady();
    fillValidForm();
    submit();
    expect(await screen.findByRole("heading", { name: "Waiting for approval" })).toBeTruthy();
    expect(verifyCalls(f)).toHaveLength(1);
    expect(verifyCalls(f)[0]![1]?.method).toBe("POST");
    expect(verifyBody(f)).toEqual({ token: "tok-dev-123" });
    expect(screen.getByText(/Your email is verified/)).toBeTruthy();
    expect(screen.getByText(/waiting for approval by the Education OS administration team/)).toBeTruthy();
    expect(screen.getByText("riverside-sports-college")).toBeTruthy();
    expect(screen.getByText("asha@riverside.example.com")).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "Check your email" })).toBeNull();
  });

  it("dev mode: when tenancy auto-approves (verify returns active) it says the organisation is approved and offers sign-in", async () => {
    mockApi({ verify: { status: 200, body: { ...VERIFIED, status: "active" } } });
    await renderReady();
    fillValidForm();
    submit();
    expect(await screen.findByRole("heading", { name: "Approved, you can sign in" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Sign in" }).getAttribute("href")).toBe("/app");
    expect(screen.getByText("riverside-sports-college")).toBeTruthy();
    expect(screen.queryByText(/waiting for approval/i)).toBeNull();
  });

  it("production: without a token in the response it asks the visitor to check their email, and does not claim approval", async () => {
    const f = mockApi({ register: { status: 201, body: REGISTERED } });
    await renderReady();
    fillValidForm();
    submit();
    expect(await screen.findByRole("heading", { name: "Check your email" })).toBeTruthy();
    expect(screen.getByText("asha@riverside.example.com")).toBeTruthy();
    expect(screen.getByLabelText("Verification token")).toBeTruthy();
    expect(verifyCalls(f)).toHaveLength(0);
    expect(screen.queryByRole("heading", { name: "Waiting for approval" })).toBeNull();
  });

  it("production: pasting the emailed token posts it to /tenancy/register/verify, then shows 'Waiting for approval'", async () => {
    const f = mockApi({ register: { status: 201, body: REGISTERED } });
    await renderReady();
    fillValidForm();
    submit();
    await screen.findByRole("heading", { name: "Check your email" });
    fireEvent.change(screen.getByLabelText("Verification token"), { target: { value: "  tok-from-email  " } });
    fireEvent.click(screen.getByRole("button", { name: "Verify email" }));
    expect(await screen.findByRole("heading", { name: "Waiting for approval" })).toBeTruthy();
    expect(verifyCalls(f)).toHaveLength(1);
    expect(verifyBody(f)).toEqual({ token: "tok-from-email" });
    expect(screen.getByText("riverside-sports-college")).toBeTruthy();
  });

  it.each([400, 404])("production: a wrong token (%i) shows a message, keeps the input and its value, and does not move on", async (status) => {
    const f = mockApi({ register: { status: 201, body: REGISTERED }, verify: { status, body: { detail: "invalid or expired token" } } });
    await renderReady();
    fillValidForm();
    submit();
    await screen.findByRole("heading", { name: "Check your email" });
    const input = screen.getByLabelText("Verification token") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "wrong-token" } });
    fireEvent.click(screen.getByRole("button", { name: "Verify email" }));
    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(/isn't valid or has expired/);
    expect(screen.getByLabelText("Verification token")).toBe(input);
    expect(input.value).toBe("wrong-token");
    expect(input.getAttribute("aria-invalid")).toBe("true");
    expect(verifyCalls(f)).toHaveLength(1);
    expect(screen.queryByRole("heading", { name: "Waiting for approval" })).toBeNull();
    await waitFor(() => expect((screen.getByRole("button", { name: "Verify email" }) as HTMLButtonElement).disabled).toBe(false));
  });

  it("production: an empty token is not sent", async () => {
    const f = mockApi({ register: { status: 201, body: REGISTERED } });
    await renderReady();
    fillValidForm();
    submit();
    await screen.findByRole("heading", { name: "Check your email" });
    fireEvent.click(screen.getByRole("button", { name: "Verify email" }));
    expect(await screen.findByText("Paste the verification token from the email.")).toBeTruthy();
    expect(verifyCalls(f)).toHaveLength(0);
  });

  it("disables the button while sending, so the form cannot be submitted twice", async () => {
    const f = mockApi({ register: new Promise<never>(() => {}) });
    await renderReady();
    fillValidForm();
    submit();
    const button = await screen.findByRole("button", { name: "Submitting…" });
    expect((button as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(button);
    expect(registerCalls(f)).toHaveLength(1);
  });

  it("409: shows that the short name is taken, on the short name field, and keeps the form", async () => {
    mockApi({ register: { status: 409, body: { detail: "slug already in use" } } });
    await renderReady();
    fillValidForm();
    submit();
    expect(await screen.findByText("This short name is already taken. Choose another.")).toBeTruthy();
    expect(screen.getByLabelText("Short name").getAttribute("aria-invalid")).toBe("true");
    expect(screen.queryByRole("heading", { name: "Waiting for approval" })).toBeNull();
  });

  it("403: says registration is closed", async () => {
    mockApi({ register: { status: 403, body: { detail: "registration is closed" } } });
    await renderReady();
    fillValidForm();
    submit();
    const alert = await screen.findByText(/New registrations are closed right now/);
    expect(alert.getAttribute("role")).toBe("alert");
  });

  it("422: asks the visitor to check the form", async () => {
    mockApi({ register: { status: 422, body: { detail: [{ loc: ["body", "admin", "email"], msg: "invalid" }] } } });
    await renderReady();
    fillValidForm();
    submit();
    expect(await screen.findByText(/Some details weren't accepted/)).toBeTruthy();
  });

  it("network failure: says the service couldn't be reached and lets the visitor try again", async () => {
    mockApi({ register: "network-error" });
    await renderReady();
    fillValidForm();
    submit();
    expect(await screen.findByText(/Couldn't reach the service/)).toBeTruthy();
    await waitFor(() => expect((screen.getByRole("button", { name: /Submit registration/ }) as HTMLButtonElement).disabled).toBe(false));
  });
});
