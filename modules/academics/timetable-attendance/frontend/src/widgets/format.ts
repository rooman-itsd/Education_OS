import type { ScheduledClass } from "../api/client";

/** "09:00" in the viewer's time zone; empty for a value that is not a date. */
export function clock(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

/** "5 Nov" in the viewer's time zone. */
export function shortDate(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

/** The class's name: course code and title when the read models know them, else a neutral word (FR-17). */
export function className(c: ScheduledClass): string {
  const name = [c.course_code, c.course_title].filter(Boolean).join(" ");
  return name || "Class";
}

/** "09:00 to 10:00 · Room 4 · Section A": time, then the location and section when known. */
export function classMeta(c: ScheduledClass): string {
  return [
    `${clock(c.starts_at)} to ${clock(c.ends_at)}`,
    c.location_label || "",
    c.section_code ? `Section ${c.section_code}` : "",
  ]
    .filter(Boolean)
    .join(" · ");
}

/** "66.7%", or a dash when no class was counted. */
export function percent(value: number | null | undefined): string {
  if (value === null || value === undefined) return "–";
  return `${Math.round(value * 10) / 10}%`;
}
