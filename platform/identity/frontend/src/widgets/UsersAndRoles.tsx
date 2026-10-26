import { Badge, Icons, List, ListRow, type WidgetProps } from "@eos/ui-kit";
import { byRole, humanise, listUsers } from "../api/client";
import { useWidgetData, WidgetStatus } from "./useWidgetData";

const SHOWN = 6;

/**
 * identity.users-and-roles on the Organisation Admin dashboard: how many people have access and which roles
 * they hold (GET /users). The shell renders the panel and its title; this is the body.
 */
export function UsersAndRoles(_props: WidgetProps) {
  const load = useWidgetData((signal) => listUsers(signal), "users");
  const users = load.state === "ready" ? load.data : null;
  const empty = users && users.length === 0 ? { title: "No users yet", body: "People you add appear here with their roles." } : null;
  return (
    <WidgetStatus load={load} empty={empty} icon={<Icons.Users />} lines={4}>
      {users && (
        <List divided label="Users by role">
          <ListRow
            icon={Icons.Users}
            title={`${users.length} ${users.length === 1 ? "user" : "users"}`}
            meta={`${users.filter((u) => u.status === "active").length} active`}
            trailing={users.some((u) => u.status !== "active") ? <Badge tone="warning">{`${users.filter((u) => u.status !== "active").length} disabled`}</Badge> : undefined}
          />
          {byRole(users)
            .slice(0, SHOWN)
            .map((r, i) => (
              <ListRow key={r.role} index={i + 1} icon={Icons.UserCheck} title={humanise(r.role)} trailing={<Badge>{String(r.count)}</Badge>} />
            ))}
          {byRole(users).length > SHOWN && <ListRow title={`${byRole(users).length - SHOWN} more roles`} tone="neutral" />}
        </List>
      )}
    </WidgetStatus>
  );
}
