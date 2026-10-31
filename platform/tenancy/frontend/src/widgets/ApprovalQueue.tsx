import { Badge, Icons, List, ListRow, type WidgetProps } from "@eos/ui-kit";
import { approvalQueue, humanise, initials, listOrganisations, timeAgo } from "../api/client";
import { useWidgetData, WidgetStatus } from "./useWidgetData";

/** Rows shown; the badge counts all of them. */
const SHOWN = 6;

/**
 * tenancy.approval-queue on the Super Admin dashboard: what waits for the super admin, oldest first. New
 * registrations (pending_approval) and active organisations' academic package changes (requested_academy_type),
 * from GET /admin/organisations. Approving happens on the super admin screens (#95); this only shows the queue.
 */
export function ApprovalQueue(_props: WidgetProps) {
  const load = useWidgetData((signal) => listOrganisations(signal).then(approvalQueue), "the approval queue");
  const queue = load.state === "ready" ? load.data : null;
  const empty = queue && queue.length === 0 ? { title: "Nothing waiting for approval", body: "New registrations and package changes appear here." } : null;
  return (
    <WidgetStatus load={load} empty={empty} icon={<Icons.BadgeCheck />} lines={4}>
      {queue && (
        <>
          <p className="eos-tenancy__muted">
            <Badge tone="warning">{`${queue.length} waiting`}</Badge>
          </p>
          <List divided label="Waiting for approval">
            {queue.slice(0, SHOWN).map((a, i) => (
              <ListRow
                key={`${a.organisation.id}-${a.kind}`}
                index={i}
                initials={initials(a.organisation.name)}
                tone="warning"
                title={a.organisation.name}
                meta={
                  a.kind === "registration"
                    ? `New registration · ${humanise(a.package)} · ${timeAgo(a.organisation.created_at)}`
                    : `Package change · ${humanise(a.organisation.academy_type)} → ${humanise(a.package)}`
                }
                trailing={<Badge tone={a.kind === "registration" ? "warning" : "info"}>{a.kind === "registration" ? "Registration" : "Package"}</Badge>}
              />
            ))}
          </List>
          {queue.length > SHOWN && <p className="eos-tenancy__muted">{`and ${queue.length - SHOWN} more`}</p>}
        </>
      )}
    </WidgetStatus>
  );
}
