import { Badge, Icons, type BadgeTone, type WidgetProps } from "@eos/ui-kit";
import {
  getPerformanceHistory,
  listAssessments,
  listAthletes,
  listMetrics,
  listResults,
  type Metric,
  type PerformanceHistory,
} from "../api/client";
import { dayOf, measure, metricName } from "./format";
import { Sparkline } from "./Sparkline";
import { useWidgetData, WidgetStatus } from "./useWidgetData";

/** Metrics shown, the most recently measured first; one history request each. */
export const METRICS_SHOWN = 4;
/** Points drawn per metric. */
const POINTS = 12;

const EMPTY = { title: "No results recorded yet", body: "Your results and fitness test measurements appear here once your coach records them." };

interface Series {
  metric: Metric | undefined;
  metricId: string;
  history: PerformanceHistory;
}

/** Change from the first value to the latest, judged by the metric's direction. */
function change(series: Series): { label: string; tone: BadgeTone } | null {
  const points = series.history.points;
  if (points.length < 2) return null;
  const first = points[0]!.value;
  const latest = points[points.length - 1]!.value;
  const diff = latest - first;
  if (diff === 0) return { label: "No change", tone: "neutral" };
  const better = series.metric?.direction === "lower_is_better" ? diff < 0 : diff > 0;
  const amount = measure(Math.abs(diff), series.metric?.unit);
  const since = dayOf(points[0]!.at);
  return better
    ? { label: `Improved ${amount} since ${since}`, tone: "success" }
    : { label: `Down ${amount} since ${since}`, tone: "warning" };
}

/**
 * athlete-performance.performance-trend on the Athlete dashboard: the signed-in athlete's own results over time for
 * their most recently measured metrics, with the change since the first value and the matching benchmark.
 * GET /athletes (self-scoped: the athlete's own profile), GET /results and GET /assessments for that athlete to find
 * the metrics with values, GET /metrics for names and units, then GET /athletes/{id}/history per metric.
 */
export function PerformanceTrend(_props: WidgetProps) {
  const load = useWidgetData(async (signal): Promise<Series[]> => {
    const own = await listAthletes({ limit: 1 }, signal);
    const athlete = own.items[0];
    if (!athlete) return [];
    const [metrics, results, assessments] = await Promise.all([
      listMetrics(signal),
      listResults(athlete.id, 200, signal),
      listAssessments(athlete.id, 50, signal),
    ]);
    // When each metric was last measured, from results (newest first) and assessments (newest first).
    const last = new Map<string, number>();
    const seen = (id: string, at: number) => last.set(id, Math.max(last.get(id) ?? -Infinity, at));
    for (const r of results.items) seen(r.metric_id, Date.parse(r.recorded_at));
    for (const a of assessments.items) for (const m of a.measurements) seen(m.metric_id, Date.parse(`${a.assessed_on}T00:00:00Z`));
    const ids = [...last.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, METRICS_SHOWN)
      .map(([id]) => id);
    const byId = new Map(metrics.items.map((m) => [m.id, m]));
    const histories = await Promise.all(ids.map((id) => getPerformanceHistory(athlete.id, id, signal)));
    return ids.map((id, i) => ({ metric: byId.get(id), metricId: id, history: histories[i]! })).filter((s) => s.history.points.length > 0);
  });
  const series = load.state === "ready" ? load.data : null;
  return (
    <WidgetStatus load={load} empty={series && series.length === 0 ? EMPTY : null} lines={5} icon={<Icons.TrendingUp />}>
      {series && (
        <ul className="eos-ap eos-ap__series" aria-label="Your results by metric">
          {series.map((s) => {
            const points = s.history.points;
            const latest = points[points.length - 1]!;
            const name = metricName(s.metric, s.metricId);
            const delta = change(s);
            const benchmark = s.history.benchmark;
            return (
              <li key={s.metricId} className="eos-ap__trend" aria-label={name}>
                <span className="eos-ap__trend-text">
                  <strong>{name}</strong>
                  <span className="eos-ap__latest">{measure(latest.value, s.metric?.unit)}</span>
                  <span className="eos-ap__muted">
                    {`Latest ${dayOf(latest.at)} · ${points.length === 1 ? "1 result" : `${points.length} results`}`}
                    {benchmark && ` · Target ${measure(benchmark.target_value, s.metric?.unit)} (${benchmark.level})`}
                  </span>
                </span>
                <span className="eos-ap__trend-side">
                  <Sparkline values={points.slice(-POINTS).map((p) => p.value)} target={benchmark?.target_value} />
                  {delta && <Badge tone={delta.tone}>{delta.label}</Badge>}
                </span>
              </li>
            );
          })}
        </ul>
      )}
    </WidgetStatus>
  );
}

