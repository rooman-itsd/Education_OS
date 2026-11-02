import { Badge, Icons, List, ListRow, type WidgetProps } from "@eos/ui-kit";
import { humanise, initials, listOrganisations, newest, statusInfo, timeAgo } from "../api/client";
import { useWidgetData, WidgetStatus } from "./useWidgetData";

/**
 * tenancy.recent-registrations on the Super Admin dashboard: the five newest organisations with their package,
 * plan and status, from GET /admin/organisations.
 */
export function RecentRegistrations(_props: WidgetProps) {
  const load = useWidgetData((signal) => listOrganisations(signal).then((orgs) => newest(orgs, 5)), "the recent registrations");
  const orgs = load.state === "ready" ? load.data : null;
  const empty = orgs && orgs.length === 0 ? { title: "No registrations yet" } : null;
  return (
    <WidgetStatus load={load} empty={empty} icon={<Icons.UserPlus />} lines={5}>
      {orgs && (
        <List divided label="Recent registrations">
          {orgs.map((o, i) => {
            const info = statusInfo(o.status);
            return (
              <ListRow
                key={o.id}
                index={i}
                initials={initials(o.name)}
                title={o.name}
                meta={[humanise(o.academy_type), o.plan ? `${humanise(o.plan)} plan` : null, timeAgo(o.created_at)].filter(Boolean).join(" · ")}
                trailing={<Badge tone={info.tone}>{info.label}</Badge>}
              />
            );
          })}
        </List>
      )}
    </WidgetStatus>
  );
}
