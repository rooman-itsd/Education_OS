import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * WCAG 2.5.8 (target size, 24 by 24 CSS px). jsdom does no layout, so this reads the stylesheet for the two rules that
 * a real-browser check at 320px found missing: the topbar menu button shrank from 36px to 21px in the flex row, and the
 * breadcrumb root link was 18px high. The rendered sizes were checked in Chromium; this only keeps the rules in place.
 */
const css = readFileSync(resolve(process.cwd(), "src/styles/shell.css"), "utf8");
const rule = (selector: string) => {
  const start = css.indexOf(`${selector} {`);
  expect(start, `${selector} is missing from shell.css`).toBeGreaterThanOrEqual(0);
  return css.slice(start, css.indexOf("}", start));
};

describe("target size in the shell", () => {
  it("keeps the topbar menu button from shrinking below its 36px width", () => {
    expect(rule(".eos-topbar__menu")).toMatch(/flex:\s*none/);
  });

  it("gives the breadcrumb links a target at least 24px high", () => {
    expect(rule(".eos-breadcrumb a")).toMatch(/min-height:\s*24px/);
  });
});
