import type { WidgetProps } from "@eos/ui-kit";
import { getMyExamSchedule } from "../api/client";
import type { EligibilityStatus, MyExamSessionItem } from "../api/types";
import { useWidgetData, WidgetStatus } from "./useWidgetData";

/** How many exams the widget lists; the endpoint has no page size, so the rest is counted, not hidden silently. */
export const EXAM_LIMIT = 6;

const day = new Intl.DateTimeFormat(undefined, { weekday: "short", day: "numeric", month: "short" });
const time = new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit" });

const ELIGIBILITY_LABEL: Record<EligibilityStatus, string> = {
  eligible: "Eligible",
  pending: "Eligibility pending",
  ineligible: "Not eligible",
};

/** Formats an ISO timestamp, or returns null when it is not a valid date (Intl throws on an invalid Date). */
function when(iso: string, fmt: Intl.DateTimeFormat): string | null {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : fmt.format(d);
}

function hours(e: MyExamSessionItem): string {
  const starts = when(e.starts_at, time);
  const ends = when(e.ends_at, time);
  return starts && ends ? `${starts}–${ends}` : "Time not set";
}

/** The course the exam is for, with the component when the paper is one of several ("CS201 · END"). */
function what(e: MyExamSessionItem): string {
  const course = e.course_code || e.course_title || "Exam";
  return e.component_code ? `${course} · ${e.component_code}` : course;
}

/** examinations.upcoming-assessments: the exams the caller sits (GET /me/exam-schedule). Exam sessions only: coursework deadlines are not listed. */
export function UpcomingAssessments(_props: WidgetProps) {
  const load = useWidgetData((signal) => getMyExamSchedule(signal));
  const items = load.state === "ready" ? load.data.items : null;
  return (
    <WidgetStatus load={load} empty={items && items.length === 0 ? "No upcoming exams." : null}>
      {items && (
        <div className="eos-exam">
          <ul className="eos-exam__list" aria-label="Upcoming exams">
            {items.slice(0, EXAM_LIMIT).map((e) => (
              <li key={`${e.exam_session_id}:${e.exam_paper_id}`} className="eos-exam__duty" data-eligibility={e.eligibility_status}>
                <div className="eos-exam__when">
                  <strong>{when(e.starts_at, day) ?? "Date not set"}</strong>
                  <span>{hours(e)}</span>
                </div>
                <div className="eos-exam__what">
                  <strong>{what(e)}</strong>
                  <span className="eos-exam__muted">{e.venue_label || "Venue not set"}</span>
                </div>
                <span className="eos-exam__status" data-status={e.eligibility_status}>
                  {ELIGIBILITY_LABEL[e.eligibility_status] ?? e.eligibility_status}
                </span>
              </li>
            ))}
          </ul>
          {items.length > EXAM_LIMIT ? (
            <p className="eos-exam__muted">
              Showing {EXAM_LIMIT} of {items.length} upcoming exams
            </p>
          ) : null}
        </div>
      )}
    </WidgetStatus>
  );
}
