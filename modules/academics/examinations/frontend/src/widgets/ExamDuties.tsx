import type { WidgetProps } from "@eos/ui-kit";
import { listMyDuties } from "../api/client";
import type { ExamDuty } from "../api/types";
import { useWidgetData, WidgetStatus } from "./useWidgetData";

/** How many duties the widget lists; the endpoint has no page size, so the rest is counted, not hidden silently. */
export const DUTY_LIMIT = 6;

const day = new Intl.DateTimeFormat(undefined, { weekday: "short", day: "numeric", month: "short" });
const time = new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit" });

const TYPE_LABEL: Record<string, string> = {
  invigilation: "Invigilation",
  evaluation: "Evaluation",
  moderation: "Moderation",
};
const STATUS_LABEL: Record<string, string> = { assigned: "Assigned", cancelled: "Cancelled", completed: "Completed" };

/** Formats an ISO timestamp, or returns null when it is not a valid date (Intl throws on an invalid Date). */
function when(iso: string | null | undefined, fmt: Intl.DateTimeFormat): string | null {
  if (!iso) return null;
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? null : fmt.format(d);
}

/** Invigilation has the session's time; evaluation and moderation are tied to a paper and carry none. */
function whenLabel(d: ExamDuty): { date: string; hours: string } {
  if (d.duty_type !== "invigilation") return { date: "No fixed date", hours: "" };
  const starts = when(d.starts_at, time);
  const ends = when(d.ends_at, time);
  return { date: when(d.starts_at, day) ?? "Date not set", hours: starts && ends ? `${starts}–${ends}` : "Time not set" };
}

function whatLabel(d: ExamDuty): string {
  if (d.duty_type === "invigilation") return d.venue_label || "Venue not set";
  return d.course_code || "Paper";
}

/** examinations.exam-duties: the caller's upcoming exam duties (GET /me/duties). */
export function ExamDuties(_props: WidgetProps) {
  const load = useWidgetData((signal) => listMyDuties(false, signal));
  const items = load.state === "ready" ? load.data.items : null;
  return (
    <WidgetStatus load={load} empty={items && items.length === 0 ? "No upcoming exam duties." : null}>
      {items && (
        <div className="eos-exam">
          <ul className="eos-exam__list">
            {items.slice(0, DUTY_LIMIT).map((d) => {
              const { date, hours } = whenLabel(d);
              return (
                <li key={d.id} className="eos-exam__duty" data-type={d.duty_type} data-status={d.status}>
                  <div className="eos-exam__when">
                    <strong>{date}</strong>
                    {hours ? <span>{hours}</span> : null}
                  </div>
                  <div className="eos-exam__what">
                    <strong>{TYPE_LABEL[d.duty_type] ?? d.duty_type}</strong>
                    <span className="eos-exam__muted">{whatLabel(d)}</span>
                  </div>
                  <span className="eos-exam__status" data-status={d.status}>
                    {STATUS_LABEL[d.status] ?? d.status}
                  </span>
                </li>
              );
            })}
          </ul>
          {items.length > DUTY_LIMIT ? (
            <p className="eos-exam__muted">
              Showing {DUTY_LIMIT} of {items.length} upcoming duties
            </p>
          ) : null}
        </div>
      )}
    </WidgetStatus>
  );
}
