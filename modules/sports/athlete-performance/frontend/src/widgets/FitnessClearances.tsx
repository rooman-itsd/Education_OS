import { Badge, Icons, List, ListRow, type WidgetProps } from "@eos/ui-kit";
import { getClearanceReport, type ClearanceReportRow } from "../api/client";
import { athletes, CLEARANCE, day, initials } from "./format";
import { useWidgetData, WidgetStatus } from "./useWidgetData";

/** Rows listed, most urgent first (the server's order), before "and N more". */
export const SHOWN = 8;
/** A clearance whose valid_until is at most this many days away is lapsing soon. */
export const LAPSING_DAYS = 14;

const EMPTY = { title: "No athletes yet", body: "Athletes' fitness clearance appears here once their profiles are added." };

/** What the row says under the name: the restriction, when it lapsed or lapses, or that none was recorded. */
function meta(r: ClearanceReportRow): string {
  const parts: string[] = [];
  if (r.restrictions && r.status === "restricted") parts.push(r.restrictions);
  // A not-cleared row keeps the valid_until of the clearance that lapsed; none recorded has neither.
  if (r.status === "not_cleared" && r.valid_until) parts.push(`Lapsed on ${day(r.valid_until)}`);
  else if (r.valid_until) parts.push(`Valid until ${day(r.valid_until)}`);
  else if (r.status === "not_cleared" && !r.set_at) parts.push("No clearance recorded");
  else if (r.status !== "not_cleared") parts.push("No end date");
  return parts.join(" · ");
}

function tone(r: ClearanceReportRow): "danger" | "warning" | "success" {
  if (r.status === "not_cleared") return "danger";
  return r.status === "restricted" || r.lapsing_soon ? "warning" : "success";
}

/**
 * athlete-performance.fitness-clearances on the Medical Staff dashboard: whether athletes are cleared, restricted or
 * not cleared to train and compete, until when, and whose clearance lapses within LAPSING_DAYS days, most urgent
 * first. One request: GET /reports/clearances, whose counts cover every active athlete, not only the rows shown.
 */
export function FitnessClearances(_props: WidgetProps) {
  const load = useWidgetData((signal) => getClearanceReport({ lapsing_within_days: LAPSING_DAYS, limit: SHOWN }, signal));
  const data = load.state === "ready" ? load.data : null;
  const rest = data ? data.total - data.items.length : 0;
  return (
    <WidgetStatus load={load} empty={data && data.total === 0 ? EMPTY : null} lines={5} icon={<Icons.ShieldCheck />}>
      {data && (
        <div className="eos-ap">
          <dl className="eos-ap__summary" aria-label="Clearance summary">
            <div className="eos-ap__headline">
              <dt>Cleared</dt>
              <dd>{data.counts.cleared}</dd>
            </div>
            <div data-warn={data.counts.restricted > 0 || undefined}>
              <dt>Restricted</dt>
              <dd>{data.counts.restricted}</dd>
            </div>
            <div data-warn={data.counts.not_cleared > 0 || undefined}>
              <dt>Not cleared</dt>
              <dd>{data.counts.not_cleared}</dd>
            </div>
            <div data-warn={data.counts.lapsing_soon > 0 || undefined}>
              <dt>Lapsing soon</dt>
              <dd>{data.counts.lapsing_soon}</dd>
            </div>
          </dl>
          <List divided label="Fitness clearances">
            {data.items.map((r, i) => {
              const status = CLEARANCE[r.status];
              return (
                <ListRow
                  key={r.athlete_id}
                  index={i}
                  initials={initials(r.full_name)}
                  tone={tone(r)}
                  title={r.full_name}
                  meta={meta(r)}
                  trailing={
                    <span className="eos-ap__trailing">
                      <Badge tone={status.tone}>{status.label}</Badge>
                      {r.lapsing_soon && <Badge tone="warning">Lapsing soon</Badge>}
                    </span>
                  }
                />
              );
            })}
          </List>
          {rest > 0 && <p className="eos-ap__muted">{`and ${athletes(rest)} more`}</p>}
        </div>
      )}
    </WidgetStatus>
  );
}
