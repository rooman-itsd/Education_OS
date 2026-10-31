import { Icons, List, ListRow, type WidgetProps } from "@eos/ui-kit";
import { humanise, recentRecords, timeAgo } from "../api/client";
import { useWidgetData, WidgetStatus } from "./useWidgetData";

export const SHOWN = 8;

/**
 * audit.super-admin-actions on the Super Admin dashboard: platform and cross-organisation administrative
 * actions recorded across the system (GET /records without organisation_id).
 */
export function SuperAdminActions(_props: WidgetProps) {
  const load = useWidgetData((signal) => recentRecords(SHOWN, signal), "super admin actions");
  const page = load.state === "ready" ? load.data : null;
  const empty =
    page && page.items.length === 0
      ? { title: "No platform actions yet", body: "Platform-level and administrative changes appear here." }
      : null;
  return (
    <WidgetStatus load={load} empty={empty} icon={<Icons.Shield />} lines={5}>
      {page && (
        <List divided label="Super Admin actions">
          {page.items.slice(0, SHOWN).map((r, i) => (
            <ListRow
              key={r.id}
              index={i}
              icon={r.redacted ? Icons.EyeOff : Icons.Shield}
              tone={r.redacted ? "neutral" : "accent"}
              title={r.summary || humanise(r.action)}
              meta={[humanise(r.module), r.actor_name ?? (r.actor ? "Super admin" : "System"), timeAgo(r.occurred_at)]
                .filter(Boolean)
                .join(" · ")}
            />
          ))}
          {page.total > SHOWN && <ListRow title={`${page.total - SHOWN} more`} tone="neutral" />}
        </List>
      )}
    </WidgetStatus>
  );
}

