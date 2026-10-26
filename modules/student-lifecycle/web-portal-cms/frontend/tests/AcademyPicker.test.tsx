import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AcademyType } from "../src/api/public-client";
import { AcademyPicker } from "../src/public/components/AcademyPicker";

const TYPES: AcademyType[] = [
  { id: "music-academy", title: "Music Academy / Conservatory", description: "Lessons, practice rooms.", specialized_suites: [] },
  { id: "sports-college", title: "Sports University / Sports College", description: "Common suites plus sports.", specialized_suites: ["sports"] },
  { id: "law-college", title: "Law College / Law University", description: "", specialized_suites: [] },
];

afterEach(cleanup);

describe("AcademyPicker", () => {
  it("renders one radio per academy type, inside a radio group", () => {
    render(<AcademyPicker types={TYPES} value="" onChange={() => {}} />);
    expect(screen.getByRole("radiogroup")).toBeTruthy();
    expect(screen.getAllByRole("radio")).toHaveLength(3);
    expect(screen.getByRole("radio", { name: /Music Academy/ })).toBeTruthy();
  });

  it("shows each type's title and description, and no specialized-suite tag", () => {
    render(<AcademyPicker types={TYPES} value="" onChange={() => {}} />);
    expect(screen.getByText("Sports University / Sports College")).toBeTruthy();
    expect(screen.getByText("Lessons, practice rooms.")).toBeTruthy();
    expect(screen.queryByText(/Specialized suite/i)).toBeNull();
  });

  it("is single-choice: choosing another type replaces the first (one academy_type per organisation)", () => {
    const { rerender } = render(<AcademyPicker types={TYPES} value="sports-college" onChange={() => {}} />);
    rerender(<AcademyPicker types={TYPES} value="law-college" onChange={() => {}} />);
    const checked = screen.getAllByRole("radio").filter((r) => (r as HTMLInputElement).checked);
    expect(checked).toHaveLength(1);
    expect((checked[0] as HTMLInputElement).value).toBe("law-college");
  });

  it("marks only the chosen type as checked and selected", () => {
    const { container } = render(<AcademyPicker types={TYPES} value="sports-college" onChange={() => {}} />);
    const sports = screen.getByRole("radio", { name: /Sports University/ }) as HTMLInputElement;
    const music = screen.getByRole("radio", { name: /Music Academy/ }) as HTMLInputElement;
    expect(sports.checked).toBe(true);
    expect(music.checked).toBe(false);
    expect(container.querySelectorAll(".wpc-ap__card.is-selected")).toHaveLength(1);
  });

  it("reports the chosen id when a card is clicked", () => {
    const onChange = vi.fn();
    render(<AcademyPicker types={TYPES} value="" onChange={onChange} />);
    fireEvent.click(screen.getByText("Law College / Law University"));
    expect(onChange).toHaveBeenCalledWith("law-college");
  });
});
