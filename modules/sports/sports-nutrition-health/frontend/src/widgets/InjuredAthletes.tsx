import { Badge, Icons, List, ListRow, type WidgetProps } from "@eos/ui-kit";
import { listInjuries, type Injury } from "../api/client";
import { athleteLabel, day, daysUntil, injuries, INJURY_STATUS, SEVERITY } from "./format";
import { useWidgetData, WidgetStatus } from "./useWidgetData";

/** Injuries fetched per status, and rows listed before "and N more". */
export const FETCHED = 200;
export const SHOWN = 8;

const EMPTY = { title: "No injured athletes", body: "Athletes with an active or recovering injury appear here once it is reported." };

/** Active before recovering, then most severe, then the soonest expected return (none recorded last). */
export function byUrgency(a: Injury, b: Injury): number {
  return (
    (a.status === b.status ? 0 : a.status === "active" ? -1 : 1) ||
    SEVERITY[a.severity].rank - SEVERITY[b.severity].rank ||
    (a.expected_return_on ?? "9999").localeCompare(b.expected_return_on ?? "9999")
  );
}

/** Under the athlete: what and since when, and the expected return. Never the clinical notes. */
function meta(i: Injury): string {
  const what = i.injury_type ? `${i.body_part} ${i.injury_type.toLowerCase()}` : i.body_part;
  let back = "No return date";
  if (i.expected_return_on) {
    back = daysUntil(i.expected_return_on) < 0 ? `Was expected back ${day(i.expected_return_on)}` : `Expected back ${day(i.expected_return_on)}`;
  }
  return `${what} · Since ${day(i.occurred_on)} · ${back}`;
}

/**
 * sports-nutrition-health.injured-athletes on the Medical Staff dashboard: athletes with an active or recovering
 * injury, what it is, its severity and the expected return, most urgent first. GET /injuries?status=active and
 * GET /injuries?status=recovering (the contract filters one status per request); the counts are the server totals.
 * Clinical notes are dropped by the client and never shown.
 */
export function InjuredAthletes(_props: WidgetProps) {
  const load = useWidgetData(async (signal) => {
    const [active, recovering] = await Promise.all([
      listInjuries({ status: "active", limit: FETCHED }, signal),
      listInjuries({ status: "recovering", limit: FETCHED }, signal),
    ]);
    const rows = [...active.items, ...recovering.items].sort(byUrgency);
    return { rows, active: active.total, recovering: recovering.total };
  });
  const data = load.state === "ready" ? load.data : null;
  const total = data ? data.active + data.recovering : 0;
  const people = data ? new Set(data.rows.map((r) => r.athlete_id)).size : 0;
  const rest = total - SHOWN;
  return (
    <WidgetStatus load={load} empty={data && total === 0 ? EMPTY : null} lines={5} icon={<Icons.ShieldAlert />}>
      {data && (
        <div className="eos-snh">
          <dl className="eos-snh__summary" aria-label="Injury summary">
            <div className="eos-snh__headline">
              <dt>Athletes</dt>
              <dd>{people}</dd>
            </div>
            <div data-warn={data.active > 0 || undefined}>
              <dt>Active</dt>
              <dd>{data.active}</dd>
            </div>
            <div>
              <dt>Recovering</dt>
              <dd>{data.recovering}</dd>
            </div>
          </dl>
          <List divided label="Injured athletes">
            {data.rows.slice(0, SHOWN).map((r, i) => {
              const status = INJURY_STATUS[r.status];
              const severity = SEVERITY[r.severity];
              return (
                <ListRow
                  key={r.id}
                  index={i}
                  icon={Icons.User}
                  tone={r.status === "active" ? (r.severity === "minor" ? "warning" : "danger") : "info"}
                  title={athleteLabel(r.athlete_id)}
                  meta={meta(r)}
                  trailing={
                    <span className="eos-snh__trailing">
                      <Badge tone={status.tone}>{status.label}</Badge>
                      <Badge tone={severity.tone}>{severity.label}</Badge>
                    </span>
                  }
                />
              );
            })}
          </List>
          {rest > 0 && <p className="eos-snh__muted">{`and ${injuries(rest)} more`}</p>}
        </div>
      )}
    </WidgetStatus>
  );
}
