import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import App from "../../src/admin/App";
import { ShieldCheck } from "../../src/admin/lib/icons";
import { BrowserRouter, Link, Route, Routes, useParams, useSearchParams } from "../../src/admin/lib/router";

beforeAll(() => {
  // jsdom has neither; the charts and a few pages use them.
  globalThis.ResizeObserver ??= class {
    observe() {}
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver;
  window.matchMedia ??= ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener() {},
    removeListener() {},
    addEventListener() {},
    removeEventListener() {},
    dispatchEvent: () => false,
  })) as typeof window.matchMedia;
});

afterEach(() => {
  cleanup();
  window.location.hash = "";
});

function goTo(path: string) {
  act(() => {
    window.location.hash = path;
    window.dispatchEvent(new HashChangeEvent("hashchange"));
  });
}

describe("admin router", () => {
  function Module() {
    const { moduleId } = useParams<{ moduleId: string }>();
    const [params] = useSearchParams();
    return <p>module {moduleId} role {params.get("role") ?? "-"}</p>;
  }

  it("matches params and the query string from the hash, and follows links", () => {
    goTo("/modules/lms?role=student");
    render(
      <BrowserRouter>
        <Routes>
          <Route path="/modules/:moduleId" element={<Module />} />
          <Route path="*" element={<Link to="/modules/fees">fees</Link>} />
        </Routes>
      </BrowserRouter>,
    );
    expect(screen.getByText("module lms role student")).toBeTruthy();

    goTo("/elsewhere");
    act(() => {
      fireEvent.click(screen.getByText("fees"));
    });
    expect(window.location.hash).toBe("#/modules/fees");
    expect(screen.getByText("module fees role -")).toBeTruthy();
  });
});

describe("admin icons", () => {
  it("render like lucide-react", () => {
    const { container } = render(<ShieldCheck className="w-4 h-4" />);
    const svg = container.querySelector("svg")!;
    expect(svg.getAttribute("class")).toBe("lucide lucide-shield-check w-4 h-4");
    expect(svg.getAttribute("viewBox")).toBe("0 0 24 24");
    expect(svg.getAttribute("stroke-width")).toBe("2");
    expect(svg.getAttribute("aria-hidden")).toBe("true");
    expect(svg.querySelectorAll("path")).toHaveLength(2);
  });
});

/** A fake identity API: `admins` decides what /auth/me says about the account. */
function fakeApi(account: { is_super_admin: boolean; roles: string[]; name?: string }) {
  const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.endsWith("/health")) return json({ status: "ok" });
    if (url.endsWith("/identity/auth/login")) {
      const body = JSON.parse(String(init?.body)) as { password: string };
      return body.password === "right" ? json({ token: "t1" }) : json({ detail: "Invalid email or password" }, 401);
    }
    if (url.endsWith("/identity/auth/me"))
      return json({ id: "u1", organisation_id: null, email: "ops@eos.test", name: account.name ?? "Asha Rao", permissions: [], impersonated_by: null, ...account });
    return json({ detail: "not found" }, 404);
  });
}

async function signInWith(email: string, password: string) {
  const id = await screen.findByPlaceholderText("e.g. name@your-institution.edu");
  fireEvent.change(id, { target: { value: email } });
  fireEvent.change(screen.getByPlaceholderText("••••••••••••"), { target: { value: password } });
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: /Sign In to Education OS/ }));
  });
}

describe("admin sign-in with the API", () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("sends a signed-out visitor to the login page, without demo logins", async () => {
    vi.stubGlobal("fetch", fakeApi({ is_super_admin: true, roles: [] }));
    goTo("/dashboard");
    render(<App />);
    await screen.findByText("Sign In to Portal");
    expect(window.location.hash).toBe("#/login");
    expect(screen.queryByText("Quick Prototype Demo Logins")).toBeNull();
  });

  it("rejects a wrong password", async () => {
    vi.stubGlobal("fetch", fakeApi({ is_super_admin: true, roles: [] }));
    goTo("/login");
    render(<App />);
    await signInWith("ops@eos.test", "wrong");
    expect((await screen.findByRole("alert")).textContent).toBe("Incorrect email or password.");
    expect(window.location.hash).toBe("#/login");
  });

  it("rejects an account that is not an administrator", async () => {
    vi.stubGlobal("fetch", fakeApi({ is_super_admin: false, roles: ["student"] }));
    goTo("/login");
    render(<App />);
    await signInWith("student@eos.test", "right");
    expect((await screen.findByRole("alert")).textContent).toMatch(/not an administrator/);
    expect(localStorage.getItem("eos.token")).toBeNull();
  });

  it("lets a super admin in, shows who is signed in, and signs out", async () => {
    vi.stubGlobal("fetch", fakeApi({ is_super_admin: true, roles: [] }));
    goTo("/login");
    render(<App />);
    await signInWith("ops@eos.test", "right");
    await waitFor(() => expect(window.location.hash).toBe("#/dashboard"));
    // Shown in the top bar and in the dashboard greeting.
    expect((await screen.findAllByText("Asha Rao")).length).toBeGreaterThanOrEqual(2);
    expect(localStorage.getItem("eos.token")).toBe("t1");

    act(() => {
      fireEvent.click(screen.getAllByText("Asha Rao")[0]!);
    });
    act(() => {
      fireEvent.click(screen.getByText("Logout"));
    });
    await screen.findByText("Sign In to Portal");
    expect(localStorage.getItem("eos.token")).toBeNull();
  });

  it("keeps an organisation admin signed in across reloads", async () => {
    vi.stubGlobal("fetch", fakeApi({ is_super_admin: false, roles: ["org-admin"], organisation_id: null } as never));
    localStorage.setItem("eos.token", "t1");
    goTo("/users");
    render(<App />);
    await screen.findByText("Asha Rao");
    expect(window.location.hash).toBe("#/users");
  });
});

describe("admin dashboard in preview (no API)", () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("offline"))));
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("still asks to sign in first, with the design's demo logins", async () => {
    render(<App />);
    await screen.findByText("Quick Prototype Demo Logins");
    expect(window.location.hash).toBe("#/login");
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /Sign In to Education OS/ }));
    });
    await waitFor(() => expect(window.location.hash).toBe("#/dashboard"));
  });

  it.each([
    "/dashboard",
    "/admissions",
    "/users",
    "/roles",
    "/dashboards",
    "/dashboards?role=student",
    "/modules",
    "/modules/examinations",
    "/modules/athlete-performance",
    "/audit-logs",
  ])("renders %s once signed in", async (path) => {
    sessionStorage.setItem("eos.admin.preview", "1");
    goTo(path);
    const { container } = render(<App />);
    await waitFor(() => expect(container.querySelector("main")).not.toBeNull());
    expect(window.location.hash).toBe(`#${path}`);
    expect(container.textContent!.length).toBeGreaterThan(50);
  });
});
