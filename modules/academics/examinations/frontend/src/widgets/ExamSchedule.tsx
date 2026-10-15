import type { WidgetProps } from "@eos/ui-kit";
import { listUpcomingSessions } from "../api/client";
import type { ExamSession } from "../api/types";
import { useWidgetData, WidgetStatus } from "./useWidgetData";

/** How many upcoming sessions the widget lists. */
export const SCHEDULE_LIMIT = 6;

const day = new Intl.DateTimeFormat(undefined, { weekday: "short", day: "numeric", month: "short" });
const time = new Intl.DateTimeFormat(undefined, { hour: "2-digit", minute: "2-digit" });

function paperLabel(p: ExamSession["papers"][number]): string {
  const name = [p.course_code, p.course_title].filter(Boolean).join(" · ") || "Paper";
  return p.component_code ? `${name} (${p.component_code})` : name;
}

/** examinations.schedule: upcoming exam sessions (GET /sessions?date_from=today). */
export function ExamSchedule(_props: WidgetProps) {
  const load = useWidgetData((signal) => listUpcomingSessions(SCHEDULE_LIMIT, signal));
  const page = load.state === "ready" ? load.data : null;
  return (
    <WidgetStatus load={load} empty={page && page.items.length === 0 ? "No upcoming exam sessions." : null}>
      {page && (
        <div className="eos-exam">
          <ul className="eos-exam__list">
            {page.items.map((s) => {
              const starts = new Date(s.starts_at);
              const short = s.invigilators_assigned < s.invigilators_required;
              return (
                <li key={s.id} className="eos-exam__session">
                  <div className="eos-exam__when">
                    <strong>{day.format(starts)}</strong>
                    <span>
                      {time.format(starts)}–{time.format(new Date(s.ends_at))}
                    </span>
                  </div>
                  <div className="eos-exam__what">
                    <strong>{s.papers.length ? s.papers.map(paperLabel).join(", ") : "No papers"}</strong>
                    <span className="eos-exam__muted">{s.venue_label || "Venue not set"}</span>
                  </div>
                  <dl className="eos-exam__facts">
                    <div>
                      <dt>Candidates</dt>
                      <dd>{s.candidate_count}</dd>
                    </div>
                    <div data-warn={short || undefined}>
                      <dt>Invigilators</dt>
                      <dd title={short ? "Fewer invigilators assigned than required" : undefined}>
                        {s.invigilators_assigned}/{s.invigilators_required}
                        {short ? " · short" : null}
                      </dd>
                    </div>
                  </dl>
                </li>
              );
            })}
          </ul>
          {page.total > page.items.length ? (
            <p className="eos-exam__muted">
              Showing {page.items.length} of {page.total} upcoming sessions
            </p>
          ) : null}
        </div>
      )}
    </WidgetStatus>
  );
}
