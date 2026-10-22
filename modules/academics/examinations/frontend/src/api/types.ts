// Response shapes from contracts/openapi.yaml (PR #183), for the endpoints the Examination Staff
// widgets read. Written by hand until the generated client (openapi-typescript) is set up; keep
// them identical to the contract.

export type SessionStatus = "scheduled" | "cancelled" | "completed";

/** components.schemas.ExamSession */
export interface ExamSession {
  id: string;
  organisation_id: string;
  exam_cycle_id: string;
  starts_at: string;
  ends_at: string;
  /** Free text until venue ownership is settled (PRD Q3). */
  venue_label?: string | null;
  status: SessionStatus;
  cancel_reason?: string | null;
  papers: {
    exam_paper_id: string;
    course_offering_id: string;
    course_code?: string;
    course_title?: string;
    component_code?: string;
  }[];
  candidate_count: number;
  invigilators_required: number;
  invigilators_assigned: number;
}

/** GET /sessions */
export interface ExamSessionPage {
  items: ExamSession[];
  total: number;
}

/** components.schemas.HallTicketReport (GET /reports/hall-tickets) */
export interface HallTicketReport {
  items: {
    exam_cycle_id: string;
    exam_cycle_name?: string;
    eligible_students: number;
    issued: number;
    withheld: number;
    revoked: number;
    not_issued: number;
    withheld_reasons?: { reason: string; count: number }[];
  }[];
}

export type ResultsStage =
  | "marks_entry"
  | "moderation"
  | "awaiting_lock"
  | "awaiting_computation"
  | "awaiting_approval"
  | "awaiting_publication";

/** components.schemas.ResultsPendingReport (GET /reports/results-pending) */
export interface ResultsPendingReport {
  items: {
    exam_cycle_id: string;
    exam_cycle_name?: string;
    /** One row per pipeline stage still holding papers or results. */
    stages: {
      stage: ResultsStage;
      /** Papers for paper stages; course offerings for result stages. */
      count: number;
      oldest_since?: string | null;
    }[];
  }[];
}
