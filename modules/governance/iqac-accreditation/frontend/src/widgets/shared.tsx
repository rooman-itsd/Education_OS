import { IqacAccreditationApiError, type ActionItemSummary, type ActionStatus } from "../api/client";

export type Failure = { title: string; detail?: string; retry: boolean };
export type Tone = "danger" | "warning" | "info" | "success" | "neutral";

/**
 * What the error state says, as the regulatory-reports, helpdesk and amc-vendor-support widgets do. A missing or
 * unreachable service (404, 502, 503, network failure) is "not available yet", not the user's connection; retrying
 * cannot fix 401 or 403.
 */
export function describeFailure(e: unknown, what: string): Failure {
  if (!(e instanceof IqacAccreditationApiError) || [404, 502, 503].includes(e.status)) {
    return { title: "IQAC data is not available yet.", retry: true };
  }
  if (e.status === 401) return { title: "Sign in again to see this.", retry: false };
  if (e.status === 403) return { title: "You do not have access to this.", retry: false };
  return { title: `Could not load ${what}`, detail: "Try again in a moment.", retry: true };
}

const DAY = 86_400_000;

/** Whole days from today (local date) to an ISO date; negative when it has passed. */
export function daysUntil(isoDate: string, today: Date = new Date()): number {
  const [y = 0, m = 1, d = 1] = isoDate.split("-").map(Number);
  const due = Date.UTC(y, m - 1, d);
  const now = Date.UTC(today.getFullYear(), today.getMonth(), today.getDate());
  return Math.round((due - now) / DAY);
}

/** When an action item is due, always in words: "Overdue by 2 days", "Due today", "Due in 5 days". */
export function dueLabel(item: Pick<ActionItemSummary, "due_on" | "overdue">, today?: Date): { text: string; tone: Tone } {
  const n = daysUntil(item.due_on, today);
  if (item.overdue || n < 0) {
    const late = Math.max(-n, 1);
    return { text: `Overdue by ${late} ${late === 1 ? "day" : "days"}`, tone: "danger" };
  }
  if (n === 0) return { text: "Due today", tone: "danger" };
  return { text: `Due in ${n} ${n === 1 ? "day" : "days"}`, tone: n <= 7 ? "warning" : "info" };
}

const STATUS: Record<ActionStatus, string> = {
  open: "Open",
  in_progress: "In progress",
  done: "Done",
  cancelled: "Cancelled",
};

/** An action item's status in words. */
export const statusLabel = (status: ActionStatus): string => STATUS[status] ?? status;
