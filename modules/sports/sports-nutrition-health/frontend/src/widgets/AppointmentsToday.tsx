import { Badge, Icons, List, ListRow, type WidgetProps } from "@eos/ui-kit";
import { listAppointments, type Appointment } from "../api/client";
import { APPOINTMENT_STATUS, APPOINTMENT_TYPE, appointments, athleteLabel, localDay, timeOf } from "./format";
import { useWidgetData, WidgetStatus } from "./useWidgetData";

/** Appointments fetched per UTC day, and rows listed before "and N more". */
export const FETCHED = 200;
export const SHOWN = 8;

const EMPTY = { title: "No appointments today", body: "Physiotherapy, medical and nutrition sessions scheduled for today appear here." };

/**
 * Today's appointments in the viewer's local day. The backend's `?on=` is a UTC calendar day, and a local day
 * overlaps two of them unless the viewer is on UTC (in India, 00:00 to 05:30 local is the previous UTC day). So
 * this asks for each UTC day the local day overlaps and keeps the appointments scheduled within local midnight to
 * midnight, earliest first.
 */
export async function appointmentsToday(signal: AbortSignal, now = new Date()): Promise<Appointment[]> {
  const { start, end, utcDays } = localDay(now);
  const pages = await Promise.all(utcDays.map((on) => listAppointments({ on, limit: FETCHED }, signal)));
  const seen = new Set<string>();
  return pages
    .flatMap((p) => p.items)
    .filter((a) => {
      const t = Date.parse(a.scheduled_at);
      if (seen.has(a.id) || !(t >= start.getTime() && t < end.getTime())) return false;
      seen.add(a.id);
      return true;
    })
    .sort((a, b) => Date.parse(a.scheduled_at) - Date.parse(b.scheduled_at));
}

/**
 * sports-nutrition-health.appointments-today on the Medical Staff dashboard: the organisation's physiotherapy,
 * medical and nutrition appointments today, by time, with their status. GET /appointments?on=<UTC day> once or twice
 * (see appointmentsToday). Appointment notes are clinical and are dropped by the client.
 */
export function AppointmentsToday(_props: WidgetProps) {
  const load = useWidgetData((signal) => appointmentsToday(signal));
  const rows = load.state === "ready" ? load.data : null;
  const count = (status: Appointment["status"]) => rows?.filter((a) => a.status === status).length ?? 0;
  const rest = (rows?.length ?? 0) - SHOWN;
  return (
    <WidgetStatus load={load} empty={rows && rows.length === 0 ? EMPTY : null} lines={4} icon={<Icons.CalendarCheck2 />}>
      {rows && (
        <div className="eos-snh">
          <dl className="eos-snh__summary" aria-label="Appointments summary">
            <div className="eos-snh__headline">
              <dt>Today</dt>
              <dd>{rows.length}</dd>
            </div>
            <div>
              <dt>Scheduled</dt>
              <dd>{count("scheduled")}</dd>
            </div>
            <div>
              <dt>Completed</dt>
              <dd>{count("completed")}</dd>
            </div>
          </dl>
          <List divided label="Today's appointments">
            {rows.slice(0, SHOWN).map((a, i) => {
              const status = APPOINTMENT_STATUS[a.status];
              return (
                <ListRow
                  key={a.id}
                  index={i}
                  icon={Icons.Clock}
                  tone={a.status === "scheduled" ? "accent" : "neutral"}
                  title={`${timeOf(a.scheduled_at)} · ${APPOINTMENT_TYPE[a.appointment_type]}`}
                  meta={[athleteLabel(a.athlete_id), `${a.duration_minutes ?? 30} min`, a.injury_id ? "Injury follow-up" : ""]
                    .filter(Boolean)
                    .join(" · ")}
                  trailing={<Badge tone={status.tone}>{status.label}</Badge>}
                />
              );
            })}
          </List>
          {rest > 0 && <p className="eos-snh__muted">{`and ${appointments(rest)} more`}</p>}
        </div>
      )}
    </WidgetStatus>
  );
}
