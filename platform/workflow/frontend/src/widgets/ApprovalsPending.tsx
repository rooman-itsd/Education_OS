import { Icons, List, ListRow, type WidgetProps } from "@eos/ui-kit";
import { humanise, pendingRequests, timeAgo } from "../api/client";
import { useWidgetData, WidgetStatus } from "./useWidgetData";

export const SHOWN = 8;

/**
 * workflow.approvals-pending on the Department Admin dashboard: items waiting for review and sign-off.
 */
export function ApprovalsPending(_props: WidgetProps) {
  const load = useWidgetData((signal) => pendingRequests(SHOWN, signal), "pending approvals");
  const page = load.state === "ready" ? load.data : null;
  const empty =
    page && page.items.length === 0
      ? { title: "No pending approvals", body: "You have reviewed all pending workflow items." }
      : null;

  return (
    <WidgetStatus load={load} empty={empty} icon={<Icons.FileCheck2 />} lines={5}>
      {page && (
        <List divided label="Pending approvals">
          {page.items.slice(0, SHOWN).map((r, i) => (
            <ListRow
              key={r.id}
              index={i}
              icon={r.is_overdue ? Icons.AlertTriangle : Icons.Clock}
              tone={r.is_overdue ? "danger" : "accent"}
              title={r.title}
              meta={[
                humanise(r.entity_type),
                r.requester_name ?? "User",
                r.is_overdue ? "Overdue" : `Submitted ${timeAgo(r.submitted_at)}`,
              ]
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

