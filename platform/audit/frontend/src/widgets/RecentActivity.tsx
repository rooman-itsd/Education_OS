import { Icons, List, ListRow, type WidgetProps } from "@eos/ui-kit";
import { humanise, recentRecords, timeAgo } from "../api/client";
import { useWidgetData, WidgetStatus } from "./useWidgetData";

export const SHOWN = 8;

/**
 * audit.recent-activity on the Organisation Admin dashboard: the latest actions recorded in the organisation,
 * who did them and when (GET /records). Until platform/audit is mounted the widget says its data is not
 * available yet. The shell renders the panel and its title; this is the body.
 */
export function RecentActivity(_props: WidgetProps) {
  const load = useWidgetData((signal) => recentRecords(SHOWN, signal), "recent activity");
  const page = load.state === "ready" ? load.data : null;
  const empty = page && page.items.length === 0 ? { title: "Nothing recorded yet", body: "Changes made in your organisation appear here." } : null;
  return (
    <WidgetStatus load={load} empty={empty} icon={<Icons.History />} lines={5}>
      {page && (
        <List divided label="Recent activity">
          {page.items.slice(0, SHOWN).map((r, i) => (
            <ListRow
              key={r.id}
              index={i}
              icon={r.redacted ? Icons.EyeOff : Icons.Activity}
              tone={r.redacted ? "neutral" : "accent"}
              title={r.summary || humanise(r.action)}
              meta={[humanise(r.module), r.actor_name ?? (r.actor ? "A user" : "System"), timeAgo(r.occurred_at)].filter(Boolean).join(" · ")}
            />
          ))}
          {page.total > SHOWN && <ListRow title={`${page.total - SHOWN} more`} tone="neutral" />}
        </List>
      )}
    </WidgetStatus>
  );
}
