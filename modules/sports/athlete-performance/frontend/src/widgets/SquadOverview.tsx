import { Badge, Icons, List, ListRow, type WidgetProps } from "@eos/ui-kit";
import { getSquadSummary, listMetrics, type Metric, type SquadSummaryRow } from "../api/client";
import { athletes, CLEARANCE, initials, measure, metricName, TREND } from "./format";
import { useWidgetData, WidgetStatus } from "./useWidgetData";

/** Athletes listed before "and N more". */
const SHOWN = 8;
/** Key metrics shown per athlete; the summary sorts them by name. */
const METRICS_PER_ATHLETE = 3;

const EMPTY = { title: "No athletes yet", body: "Active athletes and their latest results appear here once their profiles are added." };

/** "100 m sprint 11.24 s ↑", the trend as an arrow and, for screen readers, a word. */
function MetricLine({ row, metrics }: { row: NonNullable<SquadSummaryRow["metrics"]>[number]; metrics: Map<string, Metric> }) {
  const id = row.metric_id ?? "";
  const metric = metrics.get(id);
  const trend = TREND[row.trend ?? "no_data"];
  return (
    <span className="eos-ap__metric">
      {`${metricName(metric, id)} ${measure(row.latest_value, metric?.unit)}`}
      {trend.arrow && (
        <span className="eos-ap__arrow" data-trend={row.trend} title={trend.label}>
          {` ${trend.arrow}`}
          <span className="eos-ap__sr">{` ${trend.label.toLowerCase()}`}</span>
        </span>
      )}
    </span>
  );
}

/**
 * athlete-performance.squad-overview on the Coach dashboard: the active athletes, each with the latest value and
 * trend of their key metrics and their fitness clearance (GET /reports/squad-summary, metric names and units from
 * GET /metrics).
 */
export function SquadOverview(_props: WidgetProps) {
  const load = useWidgetData(async (signal) => {
    const [summary, metrics] = await Promise.all([getSquadSummary(signal), listMetrics(signal)]);
    return { rows: summary.items, metrics: new Map(metrics.items.map((m) => [m.id, m])) };
  });
  const data = load.state === "ready" ? load.data : null;
  const rows = data?.rows ?? [];
  const count = (status: string) => rows.filter((r) => r.clearance === status).length;
  const improving = rows.filter((r) => r.metrics?.some((m) => m.trend === "improving")).length;
  const declining = rows.filter((r) => r.metrics?.some((m) => m.trend === "declining")).length;
  const rest = rows.length - SHOWN;
  return (
    <WidgetStatus load={load} empty={data && rows.length === 0 ? EMPTY : null} lines={5} icon={<Icons.Users />}>
      {data && (
        <div className="eos-ap">
          <dl className="eos-ap__summary" aria-label="Squad summary">
            <div className="eos-ap__headline">
              <dt>Athletes</dt>
              <dd>{rows.length}</dd>
            </div>
            <div>
              <dt>Improving</dt>
              <dd>{improving}</dd>
            </div>
            <div data-warn={declining > 0 || undefined}>
              <dt>Declining</dt>
              <dd>{declining}</dd>
            </div>
            <div data-warn={count("not_cleared") > 0 || undefined}>
              <dt>Not cleared</dt>
              <dd>{count("not_cleared")}</dd>
            </div>
          </dl>
          <List divided label="Squad">
            {rows.slice(0, SHOWN).map((r, i) => {
              const shown = (r.metrics ?? []).slice(0, METRICS_PER_ATHLETE);
              const more = (r.metrics?.length ?? 0) - shown.length;
              const clearance = r.clearance ? CLEARANCE[r.clearance] : null;
              return (
                <ListRow
                  key={r.athlete_id}
                  index={i}
                  initials={initials(r.full_name)}
                  tone={r.clearance === "not_cleared" ? "danger" : r.clearance === "restricted" ? "warning" : "accent"}
                  title={r.full_name}
                  meta={
                    shown.length === 0 ? (
                      "No results yet"
                    ) : (
                      <>
                        {shown.map((m, j) => (
                          <span key={m.metric_id ?? j}>
                            {j > 0 && " · "}
                            <MetricLine row={m} metrics={data.metrics} />
                          </span>
                        ))}
                        {more > 0 && ` · +${more} more`}
                      </>
                    )
                  }
                  trailing={clearance && <Badge tone={clearance.tone}>{clearance.label}</Badge>}
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
