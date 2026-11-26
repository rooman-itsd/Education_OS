import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";
import { HistogramPanel, chartSummary } from "../../src/admin/components/ui/panels";

const SERIES = [
  { key: "applied", name: "Applied" },
  { key: "admitted", name: "Admitted" },
];
const DATA = [
  { year: "2023", applied: 1200, admitted: 400 },
  { year: "2024", applied: 3400, admitted: 900 },
  { year: "2025", applied: 2100, admitted: 1100 },
];

beforeAll(() => {
  // jsdom has none of these; the panel's chart and its entrance animation use them.
  globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} } as unknown as typeof ResizeObserver;
  globalThis.IntersectionObserver ??= class { observe() {} unobserve() {} disconnect() {} takeRecords() { return []; } } as unknown as typeof IntersectionObserver;
  window.matchMedia ??= ((query: string) => ({
    matches: false, media: query, onchange: null, addListener() {}, removeListener() {}, addEventListener() {},
    removeEventListener() {}, dispatchEvent: () => false,
  })) as typeof window.matchMedia;
});
afterEach(cleanup);

describe("chartSummary", () => {
  it("names the highest, lowest and latest value of each series with the label they fall on", () => {
    expect(chartSummary("Applications", DATA, "year", SERIES)).toBe(
      "Applications, 3 points. " +
        "Applied: highest 3,400 at 2024, lowest 1,200 at 2023, latest 2,100 at 2025. " +
        "Admitted: highest 1,100 at 2025, lowest 400 at 2023, latest 1,100 at 2025.",
    );
  });

  it("says so when there is no data, and uses the singular for one point", () => {
    expect(chartSummary("Applications", [], "year", SERIES)).toBe("Applications: no data.");
    expect(chartSummary("Applications", [DATA[0]!], "year", [SERIES[0]!])).toContain("1 point.");
  });
});

describe("HistogramPanel accessibility", () => {
  it("gives the chart a text summary as its accessible name", () => {
    render(<HistogramPanel title="Applications" data={DATA} xKey="year" series={SERIES} />);
    const chart = screen.getByRole("img");
    expect(chart.getAttribute("aria-label")).toContain("Applications, 3 points.");
    expect(chart.getAttribute("aria-label")).toContain("Applied: highest 3,400 at 2024");
  });

  it("offers every value in a data table with a caption, column headers and row headers", () => {
    render(<HistogramPanel title="Applications" data={DATA} xKey="year" series={SERIES} />);
    const table = screen.getByRole("table", { name: "Data of Applications" });
    expect(within(table).getAllByRole("columnheader").map((c) => c.textContent)).toEqual(["year", "Applied", "Admitted"]);
    const rows = within(table).getAllByRole("row");
    expect(rows).toHaveLength(1 + DATA.length);
    expect(within(rows[2]!).getByRole("rowheader").textContent).toBe("2024");
    expect(within(rows[2]!).getAllByRole("cell").map((c) => c.textContent)).toEqual(["3,400", "900"]);
  });
});
