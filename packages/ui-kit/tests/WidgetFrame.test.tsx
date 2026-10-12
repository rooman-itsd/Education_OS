import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { WidgetFrame } from "../src";

describe("WidgetFrame", () => {
  it("renders the title and children when ready", () => {
    render(
      <WidgetFrame title="Fee dues" size="1x1">
        <span>₹ 1,200</span>
      </WidgetFrame>,
    );
    expect(screen.getByRole("heading", { name: "Fee dues" })).toBeTruthy();
    expect(screen.getByText("₹ 1,200")).toBeTruthy();
  });

  it("shows the loading, empty and error states instead of children", () => {
    const { rerender } = render(
      <WidgetFrame title="x" size="1x1" state="loading">
        <span>body</span>
      </WidgetFrame>,
    );
    expect(screen.queryByText("body")).toBeNull();
    expect(screen.getByLabelText("Loading")).toBeTruthy();
    rerender(<WidgetFrame title="x" size="1x1" state="empty" message="No dues" />);
    expect(screen.getByText("No dues")).toBeTruthy();
    rerender(<WidgetFrame title="x" size="1x1" state="error" message="Timed out" />);
    expect(screen.getByRole("alert").textContent).toContain("Timed out");
  });

  it("marks its grid span and kind for the dashboard grid", () => {
    render(<WidgetFrame title="x" size="2x1" kind="table" state="empty" />);
    const el = document.querySelector(".eos-widget")!;
    expect(el.getAttribute("data-span")).toBe("2x1");
    expect(el.getAttribute("data-kind")).toBe("table");
  });
});
