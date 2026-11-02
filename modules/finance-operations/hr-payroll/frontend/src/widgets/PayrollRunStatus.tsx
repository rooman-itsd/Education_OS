import { Badge, Icons, type BadgeTone, type WidgetProps } from "@eos/ui-kit";
import { getCurrentPayrollRun, type PayrollRun, type PayrollRunStatus as RunStatus } from "../api/client";
import { day, indianMonth, month, rupees, RUN_STATUS_LABEL } from "./format";
import { useWidgetData, WidgetStatus } from "./useWidgetData";

const EMPTY = {
  title: "No payroll run this month",
  body: "Once HR starts the payroll for a month, its status appears here.",
  icon: <Icons.Wallet />,
};

/** Badge tone of a run's status: in review and awaiting approval need someone's action, paid is done. */
const STATUS_TONE: Record<RunStatus, BadgeTone> = {
  computing: "neutral",
  review: "warning",
  submitted: "warning",
  approved: "info",
  paid: "success",
  failed: "danger",
};

/** Who acts next on a run (prd.md, flow 3: HR prepares and submits, finance or management approves, finance pays). */
function nextStep(run: PayrollRun): string | null {
  switch (run.status) {
    case "computing":
      return "Being computed";
    case "review":
      return run.note ? "Next: HR to correct it and submit again" : "Next: HR to submit it for approval";
    case "submitted":
      return "Next: finance or management to approve";
    case "approved":
      return "Next: finance to mark it paid";
    case "paid":
      return run.paid_on ? `Paid on ${day(run.paid_on)}` : null;
    default:
      return null;
  }
}

/**
 * hr-payroll.payroll-run-status on the HR Staff dashboard: the run for this month (or the latest), with its status,
 * how many employees it pays, the net total, who acts next and whether it is late (GET /payroll-runs/current).
 * No run yet (404 `not_found`) is the empty state.
 */
export function PayrollRunStatus(_props: WidgetProps) {
  const load = useWidgetData((signal) => getCurrentPayrollRun(signal));
  const run = load.state === "ready" ? load.data : null;
  const thisMonth = indianMonth();
  const exceptions = run?.exceptions?.length ?? 0;
  const returned = run?.status === "review" && !!run.note;
  const next = run ? nextStep(run) : null;

  return (
    <WidgetStatus load={load} empty={load.state === "ready" && !run ? EMPTY : null} lines={4}>
      {run && (
        <div className="eos-hr">
          <div className="eos-hr__title-row">
            <h3 className="eos-hr__period">{month(run.period)}</h3>
            <span className="eos-hr__badges">
              <Badge tone={STATUS_TONE[run.status] ?? "neutral"}>{RUN_STATUS_LABEL[run.status] ?? run.status}</Badge>
              {run.late && <Badge tone="danger">Late</Badge>}
            </span>
          </div>
          {run.period !== thisMonth && <p className="eos-hr__muted">{`No run for ${month(thisMonth)} yet. This is the latest.`}</p>}
          <dl className="eos-hr__summary">
            <div>
              <dt>Employees</dt>
              <dd className="eos-hr__count">{run.employees}</dd>
            </div>
            <div>
              <dt>Net pay</dt>
              <dd className="eos-hr__count">{rupees(run.net_total)}</dd>
            </div>
          </dl>
          {returned && <p className="eos-hr__note" data-warn>{`Returned: ${run.note}`}</p>}
          {next && <p className="eos-hr__next">{next}</p>}
          {run.status !== "approved" && run.status !== "paid" && run.due_on && (
            <p className="eos-hr__muted" data-warn={run.late || undefined}>{`Due ${day(run.due_on)}`}</p>
          )}
          {exceptions > 0 && (
            <p className="eos-hr__alert">
              <Badge tone="warning">{exceptions === 1 ? "1 exception" : `${exceptions} exceptions`}</Badge>
            </p>
          )}
        </div>
      )}
    </WidgetStatus>
  );
}
