import { ProgressBar, type WidgetProps } from "@eos/ui-kit";
import { getOutstandingReport, type AgeingBucket } from "../api/client";
import { amount, day, percent, rupees } from "./format";
import { useWidgetData, WidgetStatus } from "./useWidgetData";

const BUCKET_LABEL: Record<AgeingBucket, string> = {
  not_due: "Not yet due",
  "0-30": "0–30 days overdue",
  "31-60": "31–60 days overdue",
  "61-90": "61–90 days overdue",
  "90+": "Over 90 days overdue",
};

/**
 * fees-accounts.outstanding-dues on the Finance Staff dashboard: outstanding and overdue balances, how many
 * people owe, the ageing of what is owed and the fee heads with the most outstanding (GET /reports/outstanding).
 */
export function OutstandingDues(_props: WidgetProps) {
  const load = useWidgetData((signal) => getOutstandingReport(undefined, signal));
  const report = load.state === "ready" ? load.data : null;
  const empty =
    report && amount(report.outstanding) === 0 && report.people_with_dues === 0
      ? { title: "No outstanding dues", body: `Every invoice is paid as of ${day(report.as_of)}.` }
      : null;
  const total = report ? amount(report.outstanding) : 0;
  return (
    <WidgetStatus load={load} empty={empty} lines={5}>
      {report && (
        <div className="eos-fees">
          <dl className="eos-fees__summary">
            <div className="eos-fees__headline">
              <dt>Outstanding</dt>
              <dd>{rupees(report.outstanding)}</dd>
            </div>
            <div data-warn={amount(report.overdue) > 0 || undefined}>
              <dt>Overdue</dt>
              <dd>{rupees(report.overdue)}</dd>
            </div>
            <div>
              <dt>People with dues</dt>
              <dd>{report.people_with_dues}</dd>
            </div>
          </dl>
          <div className="eos-fees__columns">
            {report.ageing.length > 0 && (
              <section aria-label="Ageing">
                <h3 className="eos-fees__heading">Ageing</h3>
                <ul className="eos-fees__bars">
                  {report.ageing.map((a) => {
                    const label = BUCKET_LABEL[a.bucket] ?? a.bucket;
                    return (
                      <li key={a.bucket}>
                        <span className="eos-fees__bar-head">
                          <span>{label}</span>
                          <strong>{rupees(a.amount)}</strong>
                        </span>
                        <ProgressBar value={percent(amount(a.amount), total)} label={label} />
                        <span className="eos-fees__muted">{a.count === 1 ? "1 invoice" : `${a.count} invoices`}</span>
                      </li>
                    );
                  })}
                </ul>
              </section>
            )}
            {report.top_fee_heads.length > 0 && (
              <section aria-label="Top fee heads">
                <h3 className="eos-fees__heading">Top fee heads</h3>
                <ul className="eos-fees__pairs">
                  {report.top_fee_heads.map((h) => (
                    <li key={h.fee_head_id}>
                      <span>{h.name}</span>
                      <strong>{rupees(h.amount)}</strong>
                    </li>
                  ))}
                </ul>
              </section>
            )}
          </div>
          <p className="eos-fees__muted">{`As of ${day(report.as_of)}`}</p>
        </div>
      )}
    </WidgetStatus>
  );
}
