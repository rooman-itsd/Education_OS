import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AppShell, Icons, Notice, type NavSection } from "../src";

const sections: NavSection[] = [
  { entries: [{ id: "dashboard", label: "Dashboard", href: "#/", icon: Icons.LayoutDashboard }] },
  {
    label: "Education OS",
    entries: [
      {
        id: "academics",
        label: "B · Academics",
        icon: Icons.BookOpen,
        color: "#a78bfa",
        items: [
          { id: "lms", label: "Learning (LMS)", href: "#/modules/academics/lms" },
          { id: "examinations", label: "Examinations", href: "#/modules/academics/examinations", locked: true },
        ],
      },
    ],
  },
];

function Shell({ current = "#/" }: { current?: string }) {
  const navigate = vi.fn();
  return (
    <AppShell
      sidebar={{ sections, currentHref: current, homeHref: "#/" }}
      topbar={{ crumbs: [{ label: "Education OS", href: "#/" }, { label: "Dashboard" }], onNavigate: navigate, user: { name: "Kavya Menon", role: "Head of Department", email: "kavya@example.org" }, onSignOut: vi.fn(), search: [{ label: "Learning (LMS)", href: "#/modules/academics/lms", tag: "MOD" }] }}
      organisation={{ name: "Westbrook Conservatory", detail: "Music academy · Trial plan", connected: false }}
      notice={<Notice>Preview mode</Notice>}
    >
      <p>Page body</p>
    </AppShell>
  );
}

describe("AppShell", () => {
  it("renders navigation, breadcrumb, organisation, notice and content", () => {
    render(<Shell />);
    expect(screen.getByRole("navigation", { name: "Main" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Dashboard" }).getAttribute("aria-current")).toBe("page");
    expect(screen.getByRole("navigation", { name: "Breadcrumb" }).textContent).toContain("Dashboard");
    expect(screen.getByText("Westbrook Conservatory")).toBeTruthy();
    expect(screen.getByText("Preview")).toBeTruthy();
    expect(screen.getByRole("status").textContent).toContain("Preview mode");
    expect(screen.getByText("Page body")).toBeTruthy();
    expect(screen.getByText("Kavya Menon")).toBeTruthy();
  });

  it("opens the suite that holds the current page and marks a locked module", () => {
    render(<Shell current="#/modules/academics/lms" />);
    const group = screen.getByRole("button", { name: /Academics/ });
    expect(group.getAttribute("aria-expanded")).toBe("true");
    expect(group.getAttribute("aria-current")).toBe("location");
    expect(screen.getByRole("link", { name: "Learning (LMS)" }).getAttribute("aria-current")).toBe("page");
    expect(screen.getByRole("link", { name: /Examinations/ }).className).toContain("eos-sidebar__child--locked");
  });

  it("folds a suite when its header is clicked and collapses the sidebar", () => {
    render(<Shell current="#/modules/academics/lms" />);
    const group = screen.getByRole("button", { name: /Academics/ });
    fireEvent.click(group);
    expect(group.getAttribute("aria-expanded")).toBe("false");
    fireEvent.click(screen.getByRole("button", { name: "Collapse sidebar" }));
    expect(document.querySelector(".eos-shell--collapsed")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Expand sidebar" })).toBeTruthy();
  });

  it("opens the account menu and signs out", () => {
    render(<Shell />);
    fireEvent.click(screen.getByRole("button", { name: /Kavya Menon/ }));
    expect(screen.getByRole("menu")).toBeTruthy();
    expect(screen.getByRole("menuitem", { name: "Sign out" })).toBeTruthy();
  });

  it("opens the search dialog with Ctrl K and lists results", () => {
    render(<Shell />);
    fireEvent.keyDown(window, { key: "k", ctrlKey: true });
    expect(screen.getByRole("dialog", { name: "Search" })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Learning \(LMS\)/ })).toBeTruthy();
  });
});
