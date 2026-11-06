import { vi } from "vitest";
import type { ScheduledClass } from "../src/api/client";

export function answer(status: number, body: unknown) {
  return vi.fn().mockResolvedValue({ ok: status < 400, status, statusText: "", json: async () => body });
}

/** A refusal with the contract's error body ({"detail": {code, message}}). */
export function refuse(status: number, code: string) {
  return answer(status, { detail: { code, message: code } });
}

export const klass = (over: Partial<ScheduledClass> = {}): ScheduledClass => ({
  id: "c1",
  course_offering_id: "o1",
  section_id: "s1",
  instructor_id: "i1",
  course_code: "CS101",
  course_title: "Programming",
  section_code: "A",
  class_date: "2026-11-06",
  starts_at: "2026-11-06T09:00:00+00:00",
  ends_at: "2026-11-06T10:00:00+00:00",
  location_label: "Room 4",
  status: "scheduled",
  cancel_reason: null,
  attendance_session: null,
  ...over,
});
