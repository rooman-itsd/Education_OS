import { Badge, Icons, List, ListRow, type WidgetProps } from "@eos/ui-kit";
import { getSubscriptionReport, statusBreakdown } from "../api/client";
import { useWidgetData, WidgetStatus } from "./useWidgetData";

/**
 * billing.subscriptions-by-plan on the Super Admin dashboard: how many organisations are on each plan, and in which
 * subscription status, from GET /admin/reports/subscriptions. Plans nobody is on are left out.
 */
export function SubscriptionsByPlan(_props: WidgetProps) {
  const load = useWidgetData((signal) => getSubscriptionReport(signal), "subscriptions");
  const data = load.state === "ready" ? load.data : null;
  const used = (data?.plans ?? []).filter((p) => p.total > 0);
  const empty = data && used.length === 0 ? { title: "No subscriptions yet" } : null;
  return (
    <WidgetStatus load={load} empty={empty} lines={4}>
      {data && (
        <List divided label="Subscriptions by plan">
          {used.map((p, i) => (
            <ListRow
              key={p.plan}
              index={i}
              icon={Icons.Layers}
              title={p.title}
              meta={statusBreakdown(p.subscriptions)}
              trailing={<Badge tone="info">{String(p.total)}</Badge>}
            />
          ))}
        </List>
      )}
    </WidgetStatus>
  );
}
