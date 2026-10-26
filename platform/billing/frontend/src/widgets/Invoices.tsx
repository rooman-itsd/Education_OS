import { Badge, List, ListRow, type BadgeTone, type WidgetProps } from "@eos/ui-kit";
import { getInvoices, getPlans, longDate, money, type Invoice } from "../api/client";
import { useWidgetData, WidgetStatus } from "./useWidgetData";

const SHOWN = 5;
const TONE: Record<Invoice["status"], BadgeTone> = { paid: "success", due: "warning", draft: "neutral", void: "neutral" };
const LABEL: Record<Invoice["status"], string> = { paid: "Paid", due: "Due", draft: "Draft", void: "Void" };

/**
 * billing.invoices on the Organisation Admin dashboard: the newest invoices, one per paid period, with the
 * plan, the period and the amount (GET /invoices). The shell renders the panel and its title; this is the body.
 */
export function Invoices(_props: WidgetProps) {
  const load = useWidgetData(
    async (signal) => {
      const [invoices, plans] = await Promise.all([getInvoices(signal), getPlans(signal).catch(() => [])]);
      return { invoices, titles: new Map(plans.map((p) => [p.id, p.title])) };
    },
    "invoices",
  );
  const data = load.state === "ready" ? load.data : null;
  const empty = data && data.invoices.length === 0 ? { title: "No invoices yet", body: "The trial is free. The first invoice is issued when a paid plan starts." } : null;
  return (
    <WidgetStatus load={load} empty={empty} lines={3}>
      {data && (
        <List divided label="Invoices">
          {data.invoices.slice(0, SHOWN).map((inv, i) => (
            <ListRow
              key={inv.id}
              index={i}
              date={inv.issued_at.slice(0, 10)}
              title={`${data.titles.get(inv.plan) ?? inv.plan} · ${money(inv.amount, inv.currency)}`}
              meta={`${longDate(inv.period_start)} to ${longDate(inv.period_end)}`}
              trailing={<Badge tone={TONE[inv.status] ?? "neutral"}>{LABEL[inv.status] ?? inv.status}</Badge>}
            />
          ))}
          {data.invoices.length > SHOWN && <ListRow title={`${data.invoices.length - SHOWN} more`} tone="neutral" />}
        </List>
      )}
    </WidgetStatus>
  );
}
