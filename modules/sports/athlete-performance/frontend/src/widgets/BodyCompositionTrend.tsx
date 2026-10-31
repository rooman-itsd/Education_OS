import { Badge, Icons, List, ListRow, type WidgetProps } from "@eos/ui-kit";
import { getSquadSummary, listFitnessTests, listMetrics, type FitnessTest, type Metric, type Trend } from "../api/client";
import { athletes, initials, measure, TREND } from "./format";
import { useWidgetData, WidgetStatus } from "./useWidgetData";

/**
 * The contract has no metric category. A metric counts as body composition when a fitness test named for body
 * composition (the contract's example: "a body composition check") measures it, or when its name says so.
 */
const BODY_TEST = /body[\s-]*comp/i;
const BODY_METRIC =
  /body[\s-]*(fat|mass|water|composition)|^\s*(body[\s-]*)?weight\b(?!\s*(lifted|class|categor))|\bbmi\b|lean[\s-]*mass|muscle[\s-]*mass|fat[\s-]*(mass|free)|skinfold|waist|hip[\s-]*circ|visceral/i;

/** Which metrics of the catalogue are body composition, by fitness test or by name. */
export function bodyCompositionMetrics(metrics: Metric[], tests: FitnessTest[]): Map<string, Metric> {
  const fromTests = new Set(tests.filter((t) => BODY_TEST.test(t.name)).flatMap((t) => t.metric_ids));
  return new Map(metrics.filter((m) => fromTests.has(m.id) || BODY_METRIC.test(m.name)).map((m) => [m.id, m]));
}

/** Metrics summarised, and athletes listed under "To review". */
const METRICS_SHOWN = 4;
const REVIEW_SHOWN = 5;

const EMPTY = {
  title: "No body composition results yet",
  body: "Body fat, weight and other body composition measurements appear here once they are recorded.",
};

interface MetricSummary {
  metric: Metric;
  measured: number;
  average: number;
  trends: Record<Trend, number>;
}

interface Review {
  athleteId: string;
  name: string;
  declining: { metric: Metric; value?: number }[];
}

/**
 * athlete-performance.body-composition-trend on the Nutritionist dashboard: for each body-composition metric, how
 * many athletes are measured, the average of their latest values and how many are improving, steady or declining
 * (the trend follows the metric's direction), then the athletes whose body composition is declining.
 * GET /reports/squad-summary, with GET /metrics and GET /fitness-tests to tell which metrics are body composition.
 */
export function BodyCompositionTrend(_props: WidgetProps) {
  const load = useWidgetData(async (signal) => {
    const [summary, metrics, tests] = await Promise.all([getSquadSummary(signal), listMetrics(signal), listFitnessTests(signal)]);
    const body = bodyCompositionMetrics(metrics.items, tests.items);
    const byMetric = new Map<string, { values: number[]; trends: Record<Trend, number> }>();
    const review: Review[] = [];
    for (const row of summary.items) {
      const declining: Review["declining"] = [];
      for (const m of row.metrics ?? []) {
        const metric = m.metric_id ? body.get(m.metric_id) : undefined;
        if (!metric) continue;
        const entry = byMetric.get(metric.id) ?? { values: [], trends: { improving: 0, steady: 0, declining: 0, no_data: 0 } };
        if (m.latest_value != null) entry.values.push(m.latest_value);
        entry.trends[m.trend ?? "no_data"] += 1;
        byMetric.set(metric.id, entry);
        if (m.trend === "declining") declining.push({ metric, value: m.latest_value });
      }
      if (declining.length > 0) review.push({ athleteId: row.athlete_id, name: row.full_name, declining });
    }
    const summaries: MetricSummary[] = [...byMetric.entries()]
      .map(([id, e]) => ({
        metric: body.get(id)!,
        measured: e.values.length,
        average: e.values.length ? e.values.reduce((a, b) => a + b, 0) / e.values.length : NaN,
        trends: e.trends,
      }))
      .sort((a, b) => b.measured - a.measured || a.metric.name.localeCompare(b.metric.name));
    return { summaries, review };
  });
  const data = load.state === "ready" ? load.data : null;
  return (
    <WidgetStatus load={load} empty={data && data.summaries.length === 0 ? EMPTY : null} lines={5} icon={<Icons.Scale />}>
      {data && (
        <div className="eos-ap">
          <ul className="eos-ap__series" aria-label="Body composition by metric">
            {data.summaries.slice(0, METRICS_SHOWN).map((s) => (
              <li key={s.metric.id} className="eos-ap__trend" aria-label={s.metric.name}>
                <span className="eos-ap__trend-text">
                  <strong>{s.metric.name}</strong>
                  <span className="eos-ap__muted">{`${athletes(s.measured)} measured · Average ${measure(s.average, s.metric.unit)}`}</span>
                </span>
                <span className="eos-ap__trailing">
                  {(["improving", "steady", "declining"] as const)
                    .filter((t) => s.trends[t] > 0)
                    .map((t) => (
                      <Badge key={t} tone={TREND[t].tone}>{`${s.trends[t]} ${TREND[t].label.toLowerCase()}`}</Badge>
                    ))}
                </span>
              </li>
            ))}
          </ul>
          {data.review.length > 0 && (
            <section aria-label="To review">
              <h3 className="eos-ap__heading">To review</h3>
              <List divided label="Athletes with declining body composition">
                {data.review.slice(0, REVIEW_SHOWN).map((r, i) => (
                  <ListRow
                    key={r.athleteId}
                    index={i}
                    initials={initials(r.name)}
                    tone="warning"
                    title={r.name}
                    meta={r.declining.map((d) => `${d.metric.name} ${measure(d.value, d.metric.unit)}`).join(" · ")}
                    trailing={<Badge tone="warning">Declining</Badge>}
                  />
                ))}
              </List>
              {data.review.length > REVIEW_SHOWN && (
                <p className="eos-ap__muted">{`and ${athletes(data.review.length - REVIEW_SHOWN)} more`}</p>
              )}
            </section>
          )}
        </div>
      )}
    </WidgetStatus>
  );
}
