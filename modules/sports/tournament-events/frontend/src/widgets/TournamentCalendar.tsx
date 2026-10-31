import { Badge, Icons, List, ListRow, type WidgetProps } from "@eos/ui-kit";
import { getCalendar, type CalendarEntry } from "../api/client";
import { calendarDays, dateTime, isoDay, isoDayOf, items } from "./format";
import { useWidgetData, WidgetStatus } from "./useWidgetData";

/** Days the calendar covers, today included: four weeks (the backend takes at most 366). */
export const DAYS = 28;
/** Rows listed, by time (the server's order), before "and N more". */
export const SHOWN = 8;

const EMPTY = {
  title: "Nothing on the calendar",
  body: "Published tournaments and their fixtures for the next four weeks appear here.",
};

function meta(e: CalendarEntry): string {
  const when = e.kind === "tournament" ? calendarDays(e.starts_at, e.ends_at) : dateTime(e.starts_at);
  return e.venue ? `${when} · ${e.venue}` : when;
}

/**
 * tournament-events.calendar on the Coach dashboard: the published tournaments (ongoing ones included) and their
 * fixtures that are not cancelled over the next four weeks, by time. One request: GET /calendar for today through
 * DAYS - 1 days ahead; drafts and cancelled tournaments are never on it.
 */
export function TournamentCalendar(_props: WidgetProps) {
  const load = useWidgetData((signal) => getCalendar({ from: isoDay(), to: isoDay(DAYS - 1) }, signal));
  const data = load.state === "ready" ? load.data.items : null;
  const count = (kind: CalendarEntry["kind"]) => (data ?? []).filter((e) => e.kind === kind).length;
  const rest = data ? data.length - SHOWN : 0;
  return (
    <WidgetStatus load={load} empty={data && data.length === 0 ? EMPTY : null} lines={5} icon={<Icons.CalendarRange />}>
      {data && (
        <div className="eos-te">
          <dl className="eos-te__summary" aria-label="Calendar summary">
            <div className="eos-te__headline">
              <dt>Tournaments</dt>
              <dd>{count("tournament")}</dd>
            </div>
            <div>
              <dt>Fixtures</dt>
              <dd>{count("fixture")}</dd>
            </div>
          </dl>
          <List divided label="Tournament calendar">
            {data.slice(0, SHOWN).map((e, i) => (
              <ListRow
                key={`${e.kind}-${e.id}`}
                index={i}
                date={isoDayOf(e.starts_at)}
                tone={e.kind === "tournament" ? "accent" : "info"}
                title={e.title}
                meta={meta(e)}
                trailing={<Badge tone={e.kind === "tournament" ? "accent" : "info"}>{e.kind === "tournament" ? "Tournament" : "Fixture"}</Badge>}
              />
            ))}
          </List>
          {rest > 0 && <p className="eos-te__muted">{`and ${items(rest)} more`}</p>}
        </div>
      )}
    </WidgetStatus>
  );
}
