import { Badge, List, ListRow, type WidgetProps } from "@eos/ui-kit";
import { getCollectionsReport, type CollectionsReport } from "../api/client";
import { amount, MODE_LABEL, percent, rupees } from "./format";
import { useWidgetData, WidgetStatus } from "./useWidgetData";

/** Today's total against the previous day's, as a word and a tone (never colour alone). */
function Change({ report }: { report: CollectionsReport }) {
  const today = amount(report.total);
  const before = amount(report.previous_day_total);
  if (before === 0) return <Badge tone="neutral">No collections the previous day</Badge>;
  const diff = today - before;
  if (diff === 0) return <Badge tone="neutral">Same as the previous day</Badge>;
  const pct = percent(Math.abs(diff), before);
  return diff > 0 ? (
    <Badge tone="success">{`Up ${pct}% on the previous day`}</Badge>
  ) : (
    <Badge tone="warning">{`Down ${pct}% on the previous day`}</Badge>
  );
}

/**
 * fees-accounts.collections-today on the Finance Staff dashboard: amount collected today, the number of
 * payments, the change on the previous day and the split by payment mode (GET /reports/collections).
 */
export function CollectionsToday(_props: WidgetProps) {
  const load = useWidgetData((signal) => getCollectionsReport(undefined, signal));
  const report = load.state === "ready" ? load.data : null;
  const empty =
    report && report.count === 0 && amount(report.total) === 0
      ? { title: "No collections yet today", body: `Previous day: ${rupees(report.previous_day_total)}` }
      : null;
  return (
    <WidgetStatus load={load} empty={empty}>
      {report && (
        <div className="eos-fees">
          <dl className="eos-fees__summary">
            <div className="eos-fees__headline">
              <dt>Collected today</dt>
              <dd>{rupees(report.total)}</dd>
            </div>
            <div>
              <dt>Payments</dt>
              <dd>{report.count}</dd>
            </div>
            <div>
              <dt>Previous day</dt>
              <dd>{rupees(report.previous_day_total)}</dd>
            </div>
          </dl>
          <Change report={report} />
          {report.by_mode.length > 0 && (
            <List divided label="Collections by payment mode">
              {report.by_mode.map((m, i) => (
                <ListRow
                  key={m.mode}
                  index={i}
                  title={MODE_LABEL[m.mode] ?? m.mode}
                  meta={m.count === 1 ? "1 payment" : `${m.count} payments`}
                  trailing={<strong>{rupees(m.amount)}</strong>}
                />
              ))}
            </List>
          )}
        </div>
      )}
    </WidgetStatus>
  );
}
