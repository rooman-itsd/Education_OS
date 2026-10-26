import { Badge, Icons, List, ListRow, type WidgetProps } from "@eos/ui-kit";
import { getMyDues, type MyDueInvoice, type MyDues } from "../api/client";
import { amount, day, rupees } from "./format";
import { useWidgetData, WidgetStatus } from "./useWidgetData";

const EMPTY = { title: "No fees due", body: "New fee demands appear here when they are raised." };

/** Total due, the overdue part (in a danger badge when there is one) and the next due date. */
function DuesSummary({ dues }: { dues: MyDues }) {
  const overdue = amount(dues.overdue) > 0;
  return (
    <dl className="eos-fees__summary">
      <div className="eos-fees__headline">
        <dt>Total due</dt>
        <dd>{rupees(dues.total_due)}</dd>
      </div>
      <div>
        <dt>Overdue</dt>
        <dd>{overdue ? <Badge tone="danger">{`${rupees(dues.overdue)} overdue`}</Badge> : "Nothing overdue"}</dd>
      </div>
      <div>
        <dt>Next due</dt>
        <dd>{day(dues.next_due_date)}</dd>
      </div>
    </dl>
  );
}

/** One row per unpaid invoice: title, number and due date, balance and an overdue badge. */
function DuesList({ invoices }: { invoices: MyDueInvoice[] }) {
  return (
    <List divided label="Fees due">
      {invoices.map((inv, i) => (
        <ListRow
          key={inv.id}
          index={i}
          icon={inv.overdue ? Icons.AlertTriangle : Icons.FileText}
          tone={inv.overdue ? "danger" : "accent"}
          title={inv.title}
          meta={`${inv.number} · Due ${day(inv.due_date)}`}
          trailing={
            <span className="eos-fees__trailing">
              <strong>{rupees(inv.balance)}</strong>
              {inv.overdue && <Badge tone="danger">Overdue</Badge>}
            </span>
          }
        />
      ))}
    </List>
  );
}

const isEmpty = (dues: MyDues | null) => dues !== null && dues.invoices.length === 0 && amount(dues.total_due) === 0;

/** How many dues the compact applicant card lists before "and N more". */
const COMPACT_ROWS = 3;

/**
 * fees-accounts.fee-due on the Applicant dashboard: what the applicant owes (usually the application
 * fee), the overdue part and the next due date, with the first few dues (GET /me/dues).
 */
export function FeeDue(_props: WidgetProps) {
  const load = useWidgetData((signal) => getMyDues(signal));
  const dues = load.state === "ready" ? load.data : null;
  const rest = dues ? dues.invoices.length - COMPACT_ROWS : 0;
  return (
    <WidgetStatus load={load} empty={isEmpty(dues) ? EMPTY : null}>
      {dues && (
        <div className="eos-fees">
          <DuesSummary dues={dues} />
          <DuesList invoices={dues.invoices.slice(0, COMPACT_ROWS)} />
          {rest > 0 && <p className="eos-fees__muted">{`and ${rest} more`}</p>}
        </div>
      )}
    </WidgetStatus>
  );
}

/**
 * fees-accounts.fee-dues on the Student dashboard: total due, the overdue part and the next due date,
 * then every unpaid or part-paid invoice, earliest due first (GET /me/dues).
 */
export function FeeDues(_props: WidgetProps) {
  const load = useWidgetData((signal) => getMyDues(signal));
  const dues = load.state === "ready" ? load.data : null;
  return (
    <WidgetStatus load={load} empty={isEmpty(dues) ? EMPTY : null} lines={4}>
      {dues && (
        <div className="eos-fees">
          <DuesSummary dues={dues} />
          <DuesList invoices={dues.invoices} />
        </div>
      )}
    </WidgetStatus>
  );
}
