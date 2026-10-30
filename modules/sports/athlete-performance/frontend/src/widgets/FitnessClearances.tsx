import { Badge, Icons, List, ListRow, type WidgetProps } from "@eos/ui-kit";
import { getClearance, listAthletes, type Athlete, type FitnessClearance } from "../api/client";
import { athletes, CLEARANCE, day, initials, isoDay } from "./format";
import { useWidgetData, WidgetStatus } from "./useWidgetData";

/**
 * The contract has no list of clearances and the squad summary (which carries the status) needs report:read, which
 * medical staff do not hold; so the widget reads the clearance of each of the first CHECKED active athletes
 * (by name), one GET /athletes/{id}/clearance each, in parallel.
 */
export const CHECKED = 20;
/** Rows listed, most urgent first, before "and N more". */
const SHOWN = 8;
/** A clearance whose valid_until is at most this many days away is lapsing soon. */
export const LAPSING_DAYS = 14;

const EMPTY = { title: "No athletes yet", body: "Athletes' fitness clearance appears here once their profiles are added." };

type Urgency = "not_cleared" | "restricted" | "lapsing" | "cleared";
const ORDER: Urgency[] = ["not_cleared", "restricted", "lapsing", "cleared"];

interface Row {
  athlete: Athlete;
  clearance: FitnessClearance;
  urgency: Urgency;
  /** Not cleared because valid_until has passed. */
  lapsed: boolean;
  /** Cleared or restricted, and valid_until is within LAPSING_DAYS days. */
  lapsing: boolean;
}

function row(athlete: Athlete, clearance: FitnessClearance, today: string, soon: string): Row {
  const until = clearance.valid_until;
  const lapsed = clearance.status === "not_cleared" && !!until && until < today;
  const lapsing = clearance.status !== "not_cleared" && !!until && until >= today && until <= soon;
  const urgency: Urgency = clearance.status === "cleared" ? (lapsing ? "lapsing" : "cleared") : clearance.status;
  return { athlete, clearance, urgency, lapsed, lapsing };
}

/** What the row says under the name: the restriction, when it lapsed or lapses, or that none was recorded. */
function meta({ clearance, lapsed }: Row): string {
  const parts: string[] = [];
  if (clearance.restrictions && clearance.status === "restricted") parts.push(clearance.restrictions);
  if (lapsed) parts.push(`Lapsed on ${day(clearance.valid_until)}`);
  else if (clearance.valid_until) parts.push(`Valid until ${day(clearance.valid_until)}`);
  else if (clearance.status === "not_cleared" && !clearance.set_at) parts.push("No clearance recorded");
  else if (clearance.status !== "not_cleared") parts.push("No end date");
  return parts.join(" · ");
}

/**
 * athlete-performance.fitness-clearances on the Medical Staff dashboard: whether athletes are cleared, restricted or
 * not cleared to train and compete, until when, and whose clearance lapses within LAPSING_DAYS days, most urgent
 * first (GET /athletes?status=active, then GET /athletes/{id}/clearance per athlete, capped at CHECKED).
 */
export function FitnessClearances(_props: WidgetProps) {
  const load = useWidgetData(async (signal) => {
    const page = await listAthletes({ status: "active", limit: CHECKED }, signal);
    const clearances = await Promise.all(page.items.map((a) => getClearance(a.id, signal)));
    const today = isoDay();
    const soon = isoDay(LAPSING_DAYS);
    const rows = page.items.map((a, i) => row(a, clearances[i]!, today, soon));
    // Stable sort: by urgency, then the API's order (by name).
    rows.sort((x, y) => ORDER.indexOf(x.urgency) - ORDER.indexOf(y.urgency));
    return { rows, total: page.total };
  });
  const data = load.state === "ready" ? load.data : null;
  const rows = data?.rows ?? [];
  const count = (status: FitnessClearance["status"]) => rows.filter((r) => r.clearance.status === status).length;
  const lapsing = rows.filter((r) => r.lapsing).length;
  const rest = rows.length - SHOWN;
  return (
    <WidgetStatus load={load} empty={data && rows.length === 0 ? EMPTY : null} lines={5} icon={<Icons.ShieldCheck />}>
      {data && (
        <div className="eos-ap">
          <dl className="eos-ap__summary" aria-label="Clearance summary">
            <div className="eos-ap__headline">
              <dt>Cleared</dt>
              <dd>{count("cleared")}</dd>
            </div>
            <div data-warn={count("restricted") > 0 || undefined}>
              <dt>Restricted</dt>
              <dd>{count("restricted")}</dd>
            </div>
            <div data-warn={count("not_cleared") > 0 || undefined}>
              <dt>Not cleared</dt>
              <dd>{count("not_cleared")}</dd>
            </div>
            <div data-warn={lapsing > 0 || undefined}>
              <dt>Lapsing soon</dt>
              <dd>{lapsing}</dd>
            </div>
          </dl>
          <List divided label="Fitness clearances">
            {rows.slice(0, SHOWN).map((r, i) => {
              const status = CLEARANCE[r.clearance.status];
              return (
                <ListRow
                  key={r.athlete.id}
                  index={i}
                  initials={initials(r.athlete.full_name)}
                  tone={r.urgency === "not_cleared" ? "danger" : r.urgency === "cleared" ? "success" : "warning"}
                  title={r.athlete.full_name}
                  meta={meta(r)}
                  trailing={
                    <span className="eos-ap__trailing">
                      <Badge tone={status.tone}>{status.label}</Badge>
                      {r.lapsing && <Badge tone="warning">Lapsing soon</Badge>}
                    </span>
                  }
                />
              );
            })}
          </List>
          {rest > 0 && <p className="eos-ap__muted">{`and ${athletes(rest)} more`}</p>}
          {data.total > rows.length && (
            <p className="eos-ap__muted">{`Checked the first ${rows.length} of ${data.total} active athletes, by name.`}</p>
          )}
        </div>
      )}
    </WidgetStatus>
  );
}
