import { vi } from "vitest";
import type { CalendarEntry, MyRole, Page, PreparationEntry } from "../src/api/client";

/** A fetch stub that answers once with this status and body. */
export function answer(status: number, body: unknown) {
  return vi.fn().mockResolvedValue({ ok: status < 400, status, statusText: "", json: async () => body });
}

export function page<T>(items: T[], total = items.length): Page<T> {
  return { items, total };
}

export const entry = (over: Partial<CalendarEntry> = {}): CalendarEntry => ({
  id: "p-1",
  title: "Twelfth Night",
  kind: "performance",
  status: "scheduled",
  department: "Drama",
  venue: "Main Hall",
  starts_at: "2026-11-30T19:30:00+00:00",
  ends_at: "2026-11-30T22:00:00+00:00",
  call_time: "2026-11-30T18:30:00+00:00",
  cast_confirmed: 0,
  ...over,
});

export const myRole = (over: Partial<MyRole> = {}): MyRole => ({
  role_id: "r-1",
  production_id: "p-1",
  role_name: "Viola",
  role_kind: "cast",
  role_status: "invited",
  title: "Twelfth Night",
  kind: "performance",
  status: "scheduled",
  venue: "Main Hall",
  starts_at: "2026-11-30T19:30:00+00:00",
  call_time: "2026-11-30T18:30:00+00:00",
  ...over,
});

export const preparing = (over: Partial<PreparationEntry> = {}): PreparationEntry => ({
  id: "p-1",
  title: "Degree Show",
  kind: "exhibition",
  status: "in_preparation",
  department: "Design",
  starts_at: "2026-12-10T10:00:00+00:00",
  lead_user_id: "u-1",
  tasks_open: 2,
  tasks_total: 5,
  tasks_overdue: 0,
  next_task_due_at: "2026-11-20T10:00:00+00:00",
  cast_unanswered: 0,
  ...over,
});
