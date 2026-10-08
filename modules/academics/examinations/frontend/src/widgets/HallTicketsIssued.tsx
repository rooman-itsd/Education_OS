import type { WidgetProps } from "@eos/ui-kit";
import { getHallTicketReport } from "../api/client";
import { useWidgetData, WidgetStatus } from "./useWidgetData";

/** examinations.hall-tickets-issued: hall-ticket counts per active exam cycle (GET /reports/hall-tickets). */
export function HallTicketsIssued(_props: WidgetProps) {
  const load = useWidgetData((signal) => getHallTicketReport(signal));
  const report = load.state === "ready" ? load.data : null;
  return (
    <WidgetStatus
      load={load}
      empty={report && report.items.length === 0 ? "No exam cycle is scheduled or in progress." : null}
    >
      {report && (
        <div className="eos-exam">
          {report.items.map((c) => {
            const pct = c.eligible_students > 0 ? Math.round((c.issued / c.eligible_students) * 100) : 0;
            const reasons = c.withheld_reasons ?? [];
            return (
              <section key={c.exam_cycle_id} className="eos-exam__cycle" aria-label={c.exam_cycle_name ?? "Exam cycle"}>
                <h3 className="eos-exam__cycle-name">{c.exam_cycle_name ?? "Exam cycle"}</h3>
                <div
                  className="eos-exam__bar"
                  role="progressbar"
                  aria-label="Hall tickets issued"
                  aria-valuemin={0}
                  aria-valuemax={c.eligible_students}
                  aria-valuenow={c.issued}
                >
                  <span style={{ width: `${pct}%` }} />
                </div>
                <dl className="eos-exam__counts">
                  <div>
                    <dt>Eligible</dt>
                    <dd>{c.eligible_students}</dd>
                  </div>
                  <div>
                    <dt>Issued</dt>
                    <dd>{c.issued}</dd>
                  </div>
                  <div>
                    <dt>Not issued</dt>
                    <dd>{c.not_issued}</dd>
                  </div>
                  <div data-warn={c.withheld > 0 || undefined}>
                    <dt>Withheld</dt>
                    <dd>{c.withheld}</dd>
                  </div>
                  <div data-warn={c.revoked > 0 || undefined}>
                    <dt>Revoked</dt>
                    <dd>{c.revoked}</dd>
                  </div>
                </dl>
                {reasons.length > 0 ? (
                  <ul className="eos-exam__reasons" aria-label="Withheld reasons">
                    {reasons.map((r) => (
                      <li key={r.reason}>
                        <span>{r.reason}</span>
                        <strong>{r.count}</strong>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </section>
            );
          })}
        </div>
      )}
    </WidgetStatus>
  );
}
