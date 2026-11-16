import { RegulatoryReportsApiError, type FilingStatus, type FilingSummary } from "../api/client";

export type Failure = { title: string; detail?: string; retry: boolean };
export type Tone = "danger" | "warning" | "info" | "success" | "neutral";

/**
 * What the error state says, as the helpdesk and amc-vendor-support widgets do. A missing or unreachable service (404,
 * 502, 503, network failure) is "not available yet", not the user's connection; retrying cannot fix 401 or 403.
 */
export function describeFailure(e: unknown, what: string): Failure {
  if (!(e instanceof RegulatoryReportsApiError) || [404, 502, 503].includes(e.status)) {
    return { title: "Regulatory report data is not available yet.", retry: true };
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

/** When a filing is due, always in words: "Overdue by 2 days", "Due today", "Due in 5 days". */
export function dueLabel(f: Pick<FilingSummary, "due_on" | "overdue">, today?: Date): { text: string; tone: Tone } {
  const n = daysUntil(f.due_on, today);
  if (f.overdue || n < 0) {
    const late = Math.max(-n, 1);
    return { text: `Overdue by ${late} ${late === 1 ? "day" : "days"}`, tone: "danger" };
  }
  if (n === 0) return { text: "Due today", tone: "danger" };
  return { text: `Due in ${n} ${n === 1 ? "day" : "days"}`, tone: n <= 7 ? "warning" : "info" };
}

const STATUS: Record<FilingStatus, { text: string; tone: Tone }> = {
  open: { text: "Open", tone: "neutral" },
  in_preparation: { text: "In preparation", tone: "info" },
  under_review: { text: "Under review", tone: "warning" },
  submitted: { text: "Submitted", tone: "success" },
  acknowledged: { text: "Acknowledged", tone: "success" },
  not_applicable: { text: "Not applicable", tone: "neutral" },
};

/** A filing's status in words. */
export const statusLabel = (status: FilingStatus) => STATUS[status] ?? { text: status, tone: "neutral" as Tone };

/** "State Council · 2025-26": who it is filed with, and for which period. */
export const filingMeta = (f: FilingSummary) => `${f.authority} · ${f.period_label}`;
