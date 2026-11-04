import { Icons, List, ListRow, type WidgetProps } from "@eos/ui-kit";
import { listSessions } from "../api/client";
import { localToday, sessions, sessionStart } from "./format";
import { useWidgetData, WidgetStatus, type Empty } from "./useWidgetData";

/** Rows listed, earliest first (the server's order), before "and N more". */
export const SHOWN = 6;

/** Sessions still to come: scheduled, starting today or later. One request; `total` counts every such session. */
function useUpcomingSessions() {
  return useWidgetData((signal) => listSessions({ status: "scheduled", from_date: localToday(), limit: SHOWN }, signal));
}

function UpcomingSessions({ label, summary, empty }: { label: string; summary: string; empty: Empty }) {
  const load = useUpcomingSessions();
  const data = load.state === "ready" ? load.data : null;
  const rest = data ? data.total - data.items.length : 0;
  return (
    <WidgetStatus load={load} empty={data && data.total === 0 ? empty : null} lines={4} icon={<Icons.CalendarRange />}>
      {data && (
        <div className="eos-tva">
          <dl className="eos-tva__summary" aria-label={summary}>
            <div className="eos-tva__headline">
              <dt>Scheduled</dt>
              <dd>{data.total}</dd>
            </div>
          </dl>
          <List divided label={label}>
            {data.items.map((s, i) => (
              <ListRow
                key={s.id}
                index={i}
                icon={Icons.CalendarRange}
                tone="info"
                title={s.title}
                meta={[sessionStart(s.scheduled_start), s.location].filter(Boolean).join(" · ")}
              />
            ))}
          </List>
          {rest > 0 && <p className="eos-tva__muted">{`and ${sessions(rest)} more`}</p>}
        </div>
      )}
    </WidgetStatus>
  );
}

const COACH_EMPTY = { title: "No sessions scheduled", body: "Training sessions you schedule appear here, earliest first." };
const ATHLETE_EMPTY = { title: "No training sessions scheduled", body: "Sessions your coach schedules for you appear here." };

/**
 * training-video-analysis.session-plan on the Coach dashboard: the coming training sessions (GET /sessions?status=scheduled),
 * earliest first, with how many are scheduled in all. The layout used to name this athlete-performance.session-plan;
 * training plans and sessions belong to this module.
 */
export function SessionPlan(_props: WidgetProps) {
  return <UpcomingSessions label="Upcoming training sessions" summary="Session summary" empty={COACH_EMPTY} />;
}

/**
 * training-video-analysis.training-schedule on the Athlete dashboard: the athlete's own coming sessions. The server
 * narrows an athlete to the sessions they attend, so this is the same request as the coach's.
 */
export function TrainingSchedule(_props: WidgetProps) {
  return <UpcomingSessions label="My training schedule" summary="Schedule summary" empty={ATHLETE_EMPTY} />;
}
