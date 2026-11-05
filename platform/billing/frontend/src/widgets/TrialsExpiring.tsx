import { Badge, Icons, List, ListRow, type WidgetProps } from "@eos/ui-kit";
import { endsIn, getSubscriptionReport, longDate } from "../api/client";
import { useWidgetData, WidgetStatus } from "./useWidgetData";

const SHOWN = 6;
/** At or under this many days the row is red, as the trial reminders' last two steps (3 and 1 days). */
const URGENT_DAYS = 3;

/**
 * billing.trials-expiring on the Super Admin dashboard: trials ending in the next 14 days, soonest first, with the
 * organisation and its plan (GET /admin/reports/subscriptions). The shell renders the panel and its title.
 */
export function TrialsExpiring(_props: WidgetProps) {
  const load = useWidgetData((signal) => getSubscriptionReport(signal), "trials ending soon");
  const data = load.state === "ready" ? load.data : null;
  const trials = data?.trials_expiring ?? [];
  const titles = new Map((data?.plans ?? []).map((p) => [p.plan, p.title]));
  const empty = data && trials.length === 0 ? { title: `No trials ending in the next ${data.trial_window_days} days` } : null;
  return (
    <WidgetStatus load={load} empty={empty} lines={4}>
      {data && (
        <List divided label="Trials ending soon">
          {trials.slice(0, SHOWN).map((t, i) => (
            <ListRow
              key={t.organisation_id}
              index={i}
              icon={Icons.Timer}
              tone={t.days_left <= URGENT_DAYS ? "danger" : "warning"}
              title={t.organisation_name ?? "Unnamed organisation"}
              meta={`${titles.get(t.plan) ?? t.plan} · ${longDate(t.trial_ends_at)}`}
              trailing={<Badge tone={t.days_left <= URGENT_DAYS ? "danger" : "warning"}>{endsIn(t.days_left)}</Badge>}
            />
          ))}
          {trials.length > SHOWN && <ListRow title={`${trials.length - SHOWN} more`} tone="neutral" />}
        </List>
      )}
    </WidgetStatus>
  );
}
