import { RtiApiError, type DeadlineItem, type RequestStatus } from "../api/client";

export type Failure = { title: string; detail?: string; retry: boolean };
export type Tone = "danger" | "warning" | "info" | "success" | "neutral";

/**
 * What the error state says, as the helpdesk, amc-vendor-support and regulatory-reports widgets do. A missing or
 * unreachable service (404, 502, 503, network failure) is "not available yet", not the user's connection; retrying
 * cannot fix 401 or 403.
 */
export function describeFailure(e: unknown, what: string): Failure {
  if (!(e instanceof RtiApiError) || [404, 502, 503].includes(e.status)) {
    return { title: "RTI data is not available yet.", retry: true };
  }
  if (e.status === 401) return { title: "Sign in again to see this.", retry: false };
  if (e.status === 403) return { title: "You do not have access to this.", retry: false };
  return { title: `Could not load ${what}`, detail: "Try again in a moment.", retry: true };
}

const DAY = 86_400_000;
/** India is UTC+05:30 all year. Due dates are dates in India, so "today" is too. */
const IST_OFFSET = 5.5 * 60 * 60 * 1000;

/** The calendar date (YYYY-MM-DD) in India at an instant. */
export function dateInIndia(instant: Date | string): string {
  const ms = typeof instant === "string" ? Date.parse(instant) : instant.getTime();
  return new Date(ms + IST_OFFSET).toISOString().slice(0, 10);
}

/** Whole days from today in India to the date the item is due in India; negative once it has passed. */
export function daysUntil(dueAt: string, now: Date = new Date()): number {
  return Math.round((Date.parse(`${dateInIndia(dueAt)}T00:00:00Z`) - Date.parse(`${dateInIndia(now)}T00:00:00Z`)) / DAY);
}

/** When an item is due, always in words: "Overdue by 2 days", "Due today", "Due in 5 days". */
export function dueLabel(item: Pick<DeadlineItem, "due_at" | "overdue">, now?: Date): { text: string; tone: Tone } {
  const n = daysUntil(item.due_at, now);
  if (item.overdue || n < 0) {
    const late = Math.max(-n, 1);
    return { text: `Overdue by ${late} ${late === 1 ? "day" : "days"}`, tone: "danger" };
  }
  if (n === 0) return { text: "Due today", tone: "danger" };
  return { text: `Due in ${n} ${n === 1 ? "day" : "days"}`, tone: n <= 3 ? "warning" : "info" };
}

const STATUS: Record<RequestStatus, string> = {
  received: "Received, not assigned",
  assigned: "Assigned, response due",
  responded: "Responded",
  appealed: "First appeal, decision due",
  appeal_decided: "Appeal decided",
  transferred: "Transferred",
  closed: "Closed",
};

/** What the request is waiting for, in words. */
export const statusLabel = (status: RequestStatus) => STATUS[status] ?? status;
