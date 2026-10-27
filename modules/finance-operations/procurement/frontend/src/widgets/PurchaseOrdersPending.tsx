import { Badge, Icons, List, ListRow, type BadgeTone, type WidgetProps } from "@eos/ui-kit";
import { getPurchaseOrdersPending, type CountValue, type PendingReport, type PurchaseOrderStatus } from "../api/client";
import { day, rupees, STATUS_LABEL } from "./format";
import { useWidgetData, WidgetStatus } from "./useWidgetData";

const EMPTY = {
  title: "No purchase orders pending",
  body: "Orders awaiting approval or delivery and invoices awaiting payment appear here.",
  icon: <Icons.ShoppingBag />,
};

/** Badge tone of an order's status: returned orders need someone's action, issued ones are with the vendor. */
const STATUS_TONE: Record<PurchaseOrderStatus, BadgeTone> = {
  draft: "neutral",
  submitted: "warning",
  returned: "danger",
  issued: "info",
  partially_received: "info",
  received: "success",
  closed: "neutral",
  cancelled: "neutral",
};

function count(cv: CountValue | undefined): number {
  return cv?.count ?? 0;
}

function isEmpty(report: PendingReport | null): boolean {
  if (!report) return false;
  const none =
    count(report.awaiting_approval) === 0 &&
    count(report.awaiting_delivery) === 0 &&
    count(report.overdue_delivery) === 0 &&
    count(report.invoices_awaiting_payment) === 0;
  return none && (report.oldest ?? []).length === 0;
}

/** One figure of the summary: the count, with the value of those items under it. */
function Figure({ label, cv, warn = false }: { label: string; cv: CountValue | undefined; warn?: boolean }) {
  return (
    <div data-warn={warn || undefined}>
      <dt>{label}</dt>
      <dd>
        <span className="eos-procurement__count">{count(cv)}</span>
        <span className="eos-procurement__value">{rupees(cv?.value)}</span>
      </dd>
    </div>
  );
}

/**
 * procurement.purchase-orders-pending on the Finance Staff dashboard: orders awaiting approval, issued orders
 * awaiting delivery with the overdue ones, approved invoices awaiting payment, each with its value, and the
 * oldest pending orders (GET /reports/purchase-orders-pending).
 */
export function PurchaseOrdersPending(_props: WidgetProps) {
  const load = useWidgetData((signal) => getPurchaseOrdersPending(signal));
  const report = load.state === "ready" ? load.data : null;
  const overdue = count(report?.overdue_delivery);
  const oldest = report?.oldest ?? [];

  return (
    <WidgetStatus load={load} empty={isEmpty(report) ? EMPTY : null} lines={5}>
      {report && (
        <div className="eos-procurement">
          <dl className="eos-procurement__summary">
            <Figure label="Awaiting approval" cv={report.awaiting_approval} />
            <Figure label="Awaiting delivery" cv={report.awaiting_delivery} />
            <Figure label="Overdue deliveries" cv={report.overdue_delivery} warn={overdue > 0} />
            <Figure label="Invoices awaiting payment" cv={report.invoices_awaiting_payment} />
          </dl>
          {overdue > 0 && (
            <p className="eos-procurement__alert">
              <Badge tone="danger">{overdue === 1 ? "1 delivery overdue" : `${overdue} deliveries overdue`}</Badge>
            </p>
          )}
          {oldest.length > 0 && (
            <section aria-label="Oldest pending orders">
              <h3 className="eos-procurement__heading">Oldest pending orders</h3>
              <List divided label="Oldest pending orders">
                {oldest.map((o, i) => (
                  <ListRow
                    key={o.id}
                    index={i}
                    icon={Icons.ShoppingBag}
                    tone="accent"
                    title={o.number}
                    meta={
                      <span className="eos-procurement__meta">
                        <span>{o.vendor_name}</span>
                        <span>{`Pending since ${day(o.since)}`}</span>
                      </span>
                    }
                    trailing={
                      <span className="eos-procurement__trailing">
                        <strong>{rupees(o.total)}</strong>
                        <Badge tone={STATUS_TONE[o.status] ?? "neutral"}>{STATUS_LABEL[o.status] ?? o.status}</Badge>
                      </span>
                    }
                  />
                ))}
              </List>
            </section>
          )}
        </div>
      )}
    </WidgetStatus>
  );
}
