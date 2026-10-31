import { Badge, Icons, List, ListRow, type WidgetProps } from "@eos/ui-kit";
import { cents, getSubscriptionReport, money, recurringByCurrency } from "../api/client";
import { useWidgetData, WidgetStatus } from "./useWidgetData";

/**
 * billing.revenue-by-plan on the Super Admin dashboard: monthly recurring revenue in all and per plan (active
 * subscriptions at the plan's monthly price), with what was paid in the last 30 days, from GET
 * /admin/reports/subscriptions. Plans without any active subscription or payment are left out.
 */
export function RevenueByPlan(_props: WidgetProps) {
  const load = useWidgetData((signal) => getSubscriptionReport(signal), "revenue");
  const data = load.state === "ready" ? load.data : null;
  const earning = (data?.plans ?? []).filter((p) => p.subscriptions.active > 0 || cents(p.paid_last_30_days) > 0);
  const empty = data && earning.length === 0 ? { title: "No paid subscriptions yet", body: "Revenue appears once an organisation is on a paid plan." } : null;
  return (
    <WidgetStatus load={load} empty={empty} lines={4}>
      {data && (
        <>
          <p className="eos-billing__note">
            {recurringByCurrency(earning)
              .map((t) => `${money(t.cents / 100, t.currency)} a month`)
              .join(" + ")}
          </p>
          <List divided label="Revenue by plan">
            {earning.map((p, i) => (
              <ListRow
                key={p.plan}
                index={i}
                icon={Icons.IndianRupee}
                tone="success"
                title={p.title}
                meta={`${p.subscriptions.active} active · ${money(cents(p.paid_last_30_days) / 100, p.currency)} paid in ${data.paid_window_days} days`}
                trailing={<Badge tone="success">{`${money(cents(p.monthly_recurring) / 100, p.currency)}/mo`}</Badge>}
              />
            ))}
          </List>
        </>
      )}
    </WidgetStatus>
  );
}
