import { ProgressBar, type WidgetProps } from "@eos/ui-kit";
import { getCollectionVsTarget } from "../api/client";
import { amount, month, percent, rupees } from "./format";
import { useWidgetData, WidgetStatus } from "./useWidgetData";

/**
 * fees-accounts.collection-vs-target on the Management dashboard: collected against target for the academic
 * year, as a total with its percent and then month by month (GET /reports/collection-vs-target).
 */
export function CollectionVsTarget(_props: WidgetProps) {
  const load = useWidgetData((signal) => getCollectionVsTarget(undefined, signal));
  const report = load.state === "ready" ? load.data : null;
  const empty =
    report && report.periods.length === 0 && amount(report.target_total) === 0
      ? { title: "No collection targets set", body: `Set targets for ${report.academic_year || "this academic year"} to compare collections against them.` }
      : null;
  const overall = report ? percent(amount(report.collected_total), amount(report.target_total)) : 0;
  return (
    <WidgetStatus load={load} empty={empty} lines={5}>
      {report && (
        <div className="eos-fees">
          <dl className="eos-fees__summary">
            <div className="eos-fees__headline">
              <dt>Collected</dt>
              <dd>{rupees(report.collected_total)}</dd>
            </div>
            <div>
              <dt>Target</dt>
              <dd>{rupees(report.target_total)}</dd>
            </div>
            <div>
              <dt>Achieved</dt>
              <dd>{`${overall}%`}</dd>
            </div>
          </dl>
          <ProgressBar value={overall} label={`Collected against target, ${report.academic_year}`} />
          {report.periods.length > 0 && (
            <ul className="eos-fees__bars" aria-label="Collected against target by month">
              {report.periods.map((p) => {
                const pct = percent(amount(p.collected), amount(p.target));
                const label = month(p.period);
                return (
                  <li key={p.period}>
                    <span className="eos-fees__bar-head">
                      <span>{label}</span>
                      <span>
                        <strong>{rupees(p.collected)}</strong>
                        {` of ${rupees(p.target)} · ${pct}%`}
                      </span>
                    </span>
                    <ProgressBar value={pct} label={`${label} collected against target`} />
                  </li>
                );
              })}
            </ul>
          )}
          <p className="eos-fees__muted">{`Academic year ${report.academic_year}`}</p>
        </div>
      )}
    </WidgetStatus>
  );
}
