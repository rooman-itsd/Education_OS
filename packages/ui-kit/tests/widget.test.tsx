import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Figure, FigureStrip, WidgetFrame } from "../src";

describe("WidgetFrame", () => {
  it("renders the title as a heading and the body when ready", () => {
    render(
      <WidgetFrame title="Fee dues" size="1x1" kind="list">
        <span>₹ 1,200 due</span>
      </WidgetFrame>,
    );
    expect(screen.getByRole("heading", { name: "Fee dues" })).toBeTruthy();
    expect(screen.getByText("₹ 1,200 due")).toBeTruthy();
    expect(document.querySelector('[data-span="1x1"][data-kind="list"]')).toBeTruthy();
  });

  it("shows the locked, empty, loading and error states instead of the body", () => {
    const { rerender } = render(<WidgetFrame title="x" size="1x1" state="locked" message="Not in your plan" />);
    expect(screen.getByText("Not in your plan")).toBeTruthy();
    rerender(<WidgetFrame title="x" size="1x1" state="empty" message="Not built yet" />);
    expect(screen.getByText("Not built yet")).toBeTruthy();
    rerender(<WidgetFrame title="x" size="1x1" state="loading" />);
    expect(document.querySelector('[aria-busy="true"]')).toBeTruthy();
    rerender(<WidgetFrame title="x" size="1x1" state="error" message="Timed out" />);
    expect(screen.getByRole("alert").textContent).toContain("Timed out");
  });
});

describe("Figure", () => {
  it("renders figures inside the strip", () => {
    render(
      <FigureStrip>
        <Figure label="Attendance" value="88.4%" delta="1.6 under target" deltaTone="alert" />
      </FigureStrip>,
    );
    expect(screen.getByRole("region", { name: "Key figures" })).toBeTruthy();
    expect(screen.getByText("88.4%")).toBeTruthy();
  });
});
