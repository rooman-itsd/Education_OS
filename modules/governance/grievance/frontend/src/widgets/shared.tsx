import { GrievanceApiError, type CaseStatus, type CommitteeKind, type Track } from "../api/client";

export type Failure = { title: string; detail?: string; retry: boolean };

/**
 * What the error state says, as the regulatory-reports and helpdesk widgets do. A missing or unreachable service (404,
 * 502, 503, network failure) is "not available yet", not the user's connection; retrying cannot fix 401 or 403.
 */
export function describeFailure(e: unknown, what: string): Failure {
  if (!(e instanceof GrievanceApiError) || [404, 502, 503].includes(e.status)) {
    return { title: "Grievance data is not available yet.", retry: true };
  }
  if (e.status === 401) return { title: "Sign in again to see this.", retry: false };
  if (e.status === 403) return { title: "You do not have access to this.", retry: false };
  return { title: `Could not load ${what}`, detail: "Try again in a moment.", retry: true };
}

export const TRACK_LABEL: Record<Track, string> = {
  student_grievance: "Student grievances",
  ragging: "Ragging complaints",
  sexual_harassment: "Sexual harassment complaints",
};

export const KIND_LABEL: Record<CommitteeKind, string> = {
  sgrc: "Student Grievance Redressal Committee",
  anti_ragging: "Anti-ragging committee",
  icc: "Internal Committee",
  ombudsperson: "Ombudsperson",
};

export const STATUS_LABEL: Record<CaseStatus, string> = {
  submitted: "submitted",
  acknowledged: "acknowledged",
  under_inquiry: "under inquiry",
  decided: "decided",
  appealed: "appealed",
  appeal_decided: "appeal decided",
  closed: "closed",
  not_admitted: "not admitted",
  withdrawn: "withdrawn",
};

/** "1 open case", "3 open cases". */
export const openLabel = (n: number) => `${n} open ${n === 1 ? "case" : "cases"}`;

/** "No overdue cases" in words, never colour alone. */
export const overdueLabel = (n: number) => (n === 0 ? "None overdue" : `${n} overdue`);

/** "2 submitted · 1 under inquiry", in the order the API sends the statuses. */
export const statusSummary = (by: { status: CaseStatus; count: number }[]) =>
  by.map(({ status, count }) => `${count} ${STATUS_LABEL[status] ?? status}`).join(" · ");
