import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Badge, Button, DataTable, EmptyState, Icons, List, ListRow, PageHero, Panel, PanelHeader, ProgressList, Segmented, StatGrid, ThemeScope, themeForSuite } from "../src";

describe("Button", () => {
  it("renders the variant and size classes and defaults to type=button", () => {
    render(<Button variant="primary" size="sm">Save</Button>);
    const b = screen.getByRole("button", { name: "Save" });
    expect(b.className).toContain("eos-btn--primary");
    expect(b.className).toContain("eos-btn--sm");
    expect(b.getAttribute("type")).toBe("button");
  });
});

describe("StatGrid", () => {
  it("renders one card per stat with label, value and delta", () => {
    render(<StatGrid stats={[{ label: "Students", value: "3,842", icon: Icons.Users, delta: "+4.8%", note: "vs last term" }, { label: "Approvals", value: "38", delta: "12 urgent", deltaTone: "alert" }]} />);
    expect(screen.getByRole("region", { name: "Key figures" })).toBeTruthy();
    expect(screen.getByText("Students")).toBeTruthy();
    expect(screen.getByText("3,842")).toBeTruthy();
    expect(screen.getByText("12 urgent").className).toBe("");
    expect(screen.getByText("12 urgent").parentElement?.className).toContain("eos-stat__delta--alert");
  });

  it("makes a card a link when it has an href", () => {
    render(<StatGrid stats={[{ label: "Fees", value: "₹8.4 Cr", href: "#/modules/finance-operations/fees-accounts" }]} />);
    expect(screen.getByRole("link", { name: /Fees/ }).getAttribute("href")).toBe("#/modules/finance-operations/fees-accounts");
  });
});

describe("Panel and PageHero", () => {
  it("renders the header title as a heading with subtitle and action", () => {
    render(
      <Panel>
        <PanelHeader title="Upcoming" subtitle="Next two weeks" action={<button type="button">View all</button>} />
      </Panel>,
    );
    expect(screen.getByRole("heading", { level: 2, name: "Upcoming" })).toBeTruthy();
    expect(screen.getByText("Next two weeks")).toBeTruthy();
    expect(screen.getByRole("button", { name: "View all" })).toBeTruthy();
  });

  it("renders the hero as an h1 with eyebrow and actions", () => {
    render(<PageHero eyebrow="Sports College" title="Good morning, Kavya" subtitle="Dashboard" actions={<button type="button">Add</button>} />);
    expect(screen.getByRole("heading", { level: 1, name: "Good morning, Kavya" })).toBeTruthy();
    expect(screen.getByText("Sports College")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Add" })).toBeTruthy();
  });
});

describe("DataTable", () => {
  const rows = [
    { id: "a", name: "Rohan", attendance: 69.4 },
    { id: "b", name: "Aarav", attendance: 71 },
  ];
  it("renders headers, row headers and numeric cells", () => {
    render(
      <DataTable
        label="Students"
        rowKey={(r) => r.id}
        rows={rows}
        columns={[
          { key: "name", header: "Name", primary: true },
          { key: "attendance", header: "Attendance", numeric: true, cell: (r) => `${r.attendance}%` },
        ]}
        caption="Showing 2"
      />,
    );
    expect(screen.getByRole("table", { name: "Students" })).toBeTruthy();
    expect(screen.getByRole("rowheader", { name: "Rohan" })).toBeTruthy();
    expect(screen.getByText("69.4%").className).toContain("eos-num");
    expect(screen.getByText("Showing 2")).toBeTruthy();
  });

  it("shows the empty message when there are no rows", () => {
    render(<DataTable rowKey={(r: { id: string }) => r.id} rows={[]} columns={[{ key: "id", header: "Id" }]} empty="No students yet" />);
    expect(screen.getByText("No students yet")).toBeTruthy();
  });
});

describe("List rows", () => {
  it("renders a button row with an arrow and calls onClick", () => {
    const open = vi.fn();
    render(
      <List>
        <ListRow title="Leave request" meta="Thu and Fri" icon={Icons.Clock} trailing="12" onClick={open} />
      </List>,
    );
    fireEvent.click(screen.getByRole("button", { name: /Leave request/ }));
    expect(open).toHaveBeenCalledTimes(1);
    expect(screen.getByText("12")).toBeTruthy();
  });

  it("renders a date tile", () => {
    render(
      <List divided>
        <ListRow title="Admission review" date="2026-10-09" />
      </List>,
    );
    expect(screen.getByText("09")).toBeTruthy();
    expect(screen.getByText("Oct")).toBeTruthy();
  });
});

describe("ProgressList, Segmented, Badge, EmptyState", () => {
  it("renders every row with its share", () => {
    render(<ProgressList relativeToFirst items={[{ label: "Applications", count: 1284 }, { label: "Confirmed", count: 486 }]} />);
    expect(screen.getByText("Applications")).toBeTruthy();
    expect(screen.getByText("37.9%")).toBeTruthy();
  });

  it("segmented control marks the selected option and reports changes", () => {
    const onChange = vi.fn();
    render(<Segmented label="View" value="bars" options={[["bars", "Bars"], ["trend", "Trend"]]} onChange={onChange} />);
    expect(screen.getByRole("tab", { name: "Bars" }).getAttribute("aria-selected")).toBe("true");
    fireEvent.click(screen.getByRole("tab", { name: "Trend" }));
    expect(onChange).toHaveBeenCalledWith("trend");
  });

  it("badge and empty state carry words, not colour alone", () => {
    render(
      <>
        <Badge tone="danger" dot>Overdue</Badge>
        <EmptyState title="No bookings yet">Create the first one.</EmptyState>
      </>,
    );
    expect(screen.getByText("Overdue").className).toContain("eos-badge--danger");
    expect(screen.getByText("No bookings yet")).toBeTruthy();
  });
});

describe("ThemeScope", () => {
  it("sets the accent variables for a suite", () => {
    const { container } = render(
      <ThemeScope theme={themeForSuite("sports")}>
        <span>x</span>
      </ThemeScope>,
    );
    const div = container.firstElementChild as HTMLElement;
    expect(div.style.getPropertyValue("--accent")).toBe("#047857");
  });
  it("falls back to the brand theme", () => {
    expect(themeForSuite("nope").accent).toBe("#4338ca");
  });
});
