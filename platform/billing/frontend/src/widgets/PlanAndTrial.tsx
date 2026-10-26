import { useState } from "react";
import { Badge, Button, Icons, List, ListRow, type BadgeTone, type WidgetProps } from "@eos/ui-kit";
import { describeFailure, getPlans, getSubscription, longDate, money, upgrade, type Plan, type Subscription, type SubscriptionStatus } from "../api/client";
import { useWidgetData, WidgetStatus } from "./useWidgetData";

const STATUS: Record<SubscriptionStatus, { label: string; tone: BadgeTone }> = {
  trialing: { label: "Trial", tone: "info" },
  active: { label: "Active", tone: "success" },
  past_due: { label: "Payment overdue", tone: "danger" },
  cancelled: { label: "Cancelled", tone: "neutral" },
  read_only: { label: "Read only", tone: "warning" },
};

/**
 * billing.plan-and-trial on the Organisation Admin dashboard: the plan the organisation is on, its status,
 * when the trial ends or the period renews, and the package change: every other published plan with its
 * price and a button that starts the upgrade (GET /subscription, GET /plans, POST /subscription/upgrade).
 * Switching is offered to the organisation admin only (billing:subscription:manage).
 */
export function PlanAndTrial({ role }: WidgetProps) {
  const load = useWidgetData(
    async (signal) => {
      const [subscription, plans] = await Promise.all([getSubscription(signal), getPlans(signal)]);
      return { subscription, plans };
    },
    "the plan",
  );
  const [busy, setBusy] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  const choose = async (plan: Plan) => {
    setBusy(plan.id);
    setNote(null);
    try {
      const r = await upgrade(plan.id);
      if (r.payment_url) {
        window.location.assign(r.payment_url);
        return;
      }
      setNote(`Switched to ${plan.title}. Refreshing your dashboard…`);
      window.location.reload();
    } catch (e) {
      setNote(describeFailure(e, "the plan change").title);
    } finally {
      setBusy(null);
    }
  };

  const data = load.state === "ready" ? load.data : null;
  return (
    <WidgetStatus load={load} empty={null} lines={4}>
      {data && <Body sub={data.subscription} plans={data.plans} canSwitch={role === "org-admin"} busy={busy} note={note} onChoose={choose} />}
    </WidgetStatus>
  );
}

function Body({ sub, plans, canSwitch, busy, note, onChoose }: { sub: Subscription; plans: Plan[]; canSwitch: boolean; busy: string | null; note: string | null; onChoose: (p: Plan) => void }) {
  const current = plans.find((p) => p.id === sub.plan);
  const status = STATUS[sub.status] ?? { label: sub.status, tone: "neutral" as BadgeTone };
  const when =
    sub.status === "trialing" && sub.trial_ends_at
      ? `Trial ends ${longDate(sub.trial_ends_at)}`
      : sub.current_period_ends_at
        ? `${sub.status === "cancelled" ? "Access until" : "Renews"} ${longDate(sub.current_period_ends_at)}`
        : null;
  const others = plans.filter((p) => p.published && p.id !== sub.plan);
  return (
    <div className="eos-billing">
      <div className="eos-billing__plan">
        <div>
          <strong className="eos-billing__title">{current?.title ?? sub.plan}</strong>
          <span className="eos-billing__muted">
            {current ? (current.price_per_month > 0 ? `${money(current.price_per_month, current.currency)} per month` : "Free") : null}
            {when ? ` · ${when}` : null}
          </span>
        </div>
        <Badge tone={status.tone}>{status.label}</Badge>
      </div>
      {sub.pending_plan && <p className="eos-billing__muted">Payment for {plans.find((p) => p.id === sub.pending_plan)?.title ?? sub.pending_plan} is pending.</p>}
      {canSwitch && others.length > 0 && (
        <>
          <h3 className="eos-billing__heading">Change plan</h3>
          <List divided label="Available plans">
            {others.map((p, i) => (
              <ListRow
                key={p.id}
                index={i}
                icon={Icons.CreditCard}
                title={p.title}
                meta={`${p.price_per_month > 0 ? `${money(p.price_per_month, p.currency)} per month` : "Free"} · up to ${p.limits.users} users`}
                trailing={
                  <Button onClick={() => onChoose(p)} disabled={busy !== null} aria-label={`Switch to ${p.title}`}>
                    {busy === p.id ? "Switching…" : "Switch"}
                  </Button>
                }
              />
            ))}
          </List>
        </>
      )}
      {note && (
        <p className="eos-billing__note" role="status">
          {note}
        </p>
      )}
    </div>
  );
}
