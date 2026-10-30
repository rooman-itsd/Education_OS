import { Badge, Icons, type WidgetProps } from "@eos/ui-kit";
import { getReconciliationSummary, type CountAmount, type ReconciliationSummary } from "../api/client";
import { day, moment, rupees } from "./format";
import { useWidgetData, WidgetStatus } from "./useWidgetData";

const EMPTY = {
  title: "No online payments today",
  body: "Fee payments made through SBIePay, their settlement and the day's reconciliation appear here.",
  icon: <Icons.CreditCard />,
};

function count(c: { count: number } | undefined): number {
  return c?.count ?? 0;
}

/** Empty only when the day has no payment in any state and has not been reconciled (a run can find mismatches on its own). */
function isEmpty(s: ReconciliationSummary | null): boolean {
  if (!s) return false;
  const none = count(s.succeeded) === 0 && count(s.settled) === 0 && count(s.pending) === 0 && count(s.failed) === 0;
  return none && !s.last_run_at;
}

/** One figure of the summary: the count, with the amount of those payments under it when the contract gives one. */
function Figure({ label, ca }: { label: string; ca: CountAmount | { count: number } | undefined }) {
  const amount = ca && "amount" in ca ? ca.amount : undefined;
  return (
    <div>
      <dt>{label}</dt>
      <dd>
        <span className="eos-sbiepay__count">{count(ca)}</span>
        {amount !== undefined && <span className="eos-sbiepay__value">{rupees(amount)}</span>}
      </dd>
    </div>
  );
}

/** Whether the day was reconciled, with the mismatches of the latest run, as words and a tone (never colour alone). */
function Status({ summary }: { summary: ReconciliationSummary }) {
  if (!summary.last_run_at) {
    return (
      <p className="eos-sbiepay__status">
        <Badge tone="warning">Not reconciled yet</Badge>
      </p>
    );
  }
  const mismatches = summary.mismatches ?? 0;
  const at = moment(summary.last_run_at);
  return (
    <>
      <p className="eos-sbiepay__status">
        {mismatches > 0 ? (
          <Badge tone="danger">{mismatches === 1 ? "1 mismatch" : `${mismatches} mismatches`}</Badge>
        ) : (
          <Badge tone="success">No mismatches</Badge>
        )}
      </p>
      <p className="eos-sbiepay__muted">{at ? `Last reconciled ${at}` : "Reconciled"}</p>
    </>
  );
}

/**
 * payment-sbiepay.reconciliation on the Finance Staff dashboard: today's online payments through SBIePay
 * (succeeded, settled, pending and failed, each with its amount where the contract gives one), the mismatches of
 * the latest settlement reconciliation for the day, and when it ran (GET /reconciliation/summary). Read-only.
 */
export function Reconciliation(_props: WidgetProps) {
  const load = useWidgetData((signal) => getReconciliationSummary(undefined, signal));
  const summary = load.state === "ready" ? load.data : null;

  return (
    <WidgetStatus load={load} empty={isEmpty(summary) ? EMPTY : null} lines={4}>
      {summary && (
        <div className="eos-sbiepay">
          <section aria-label="Payments">
            <h3 className="eos-sbiepay__heading">{`Payments on ${day(summary.date)}`}</h3>
            <dl className="eos-sbiepay__summary">
              <Figure label="Succeeded" ca={summary.succeeded} />
              <Figure label="Settled" ca={summary.settled} />
              <Figure label="Pending" ca={summary.pending} />
              <Figure label="Failed" ca={summary.failed} />
            </dl>
          </section>
          <section aria-label="Reconciliation">
            <h3 className="eos-sbiepay__heading">Reconciliation</h3>
            <Status summary={summary} />
          </section>
        </div>
      )}
    </WidgetStatus>
  );
}
