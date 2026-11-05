import { Badge, EmptyState, ErrorState, Icons, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import { dateTile, getMyRoles, placeAndTime, shortDate, type MyRole, type Page, type RoleStatus } from "../api/client";
import { useLoader } from "./useLoader";

type Tone = "danger" | "warning" | "info" | "success" | "neutral";

/** Status in words, and the tone of each; a status always comes with a word, never colour alone. */
const LABEL: Partial<Record<RoleStatus, string>> = {
  invited: "Reply needed",
  confirmed: "Confirmed",
};
const TONE: Partial<Record<RoleStatus, Tone>> = {
  invited: "warning",
  confirmed: "success",
};

const SHOWN = 5;

/**
 * productions.my-roles on the performer dashboards (actor, dancer): the parts and crew jobs the caller holds
 * in productions that have not finished, soonest first, and which of them still need an answer
 * (GET /my-roles). It reads only the caller's own rows, whatever else their role may read.
 */
export function MyRolesWidget(_props: WidgetProps) {
  const { state, reload } = useLoader<Page<MyRole>>((signal) => getMyRoles({ limit: 50 }, signal), "your parts");

  if (state.kind === "loading") return <SkeletonLines lines={4} />;
  if (state.kind === "error") {
    const { title, detail, retry } = state.failure;
    return (
      <ErrorState title={title} onRetry={retry ? reload : undefined}>
        {detail}
      </ErrorState>
    );
  }
  if (state.data.items.length === 0) {
    return (
      <EmptyState icon={<Icons.Megaphone />} title="No parts yet">
        A part you are offered appears here, with its dates and whether you still have to answer.
      </EmptyState>
    );
  }

  return (
    <List divided label="Your parts">
      {state.data.items.slice(0, SHOWN).map((role, i) => (
        <ListRow
          key={role.role_id}
          index={i}
          date={dateTile(role.starts_at)}
          icon={dateTile(role.starts_at) ? undefined : Icons.Megaphone}
          tone={TONE[role.role_status] ?? "neutral"}
          title={`${role.role_name} · ${role.title}`}
          meta={
            role.starts_at
              ? placeAndTime(role) || shortDate(role.starts_at)
              : role.status === "in_preparation"
                ? "In preparation, no dates yet"
                : "No dates yet"
          }
          trailing={
            <Badge tone={TONE[role.role_status] ?? "neutral"}>{LABEL[role.role_status] ?? role.role_status}</Badge>
          }
        />
      ))}
      {state.data.total > SHOWN && (
        <ListRow title={`${state.data.total - SHOWN} more`} tone="neutral" icon={Icons.Users} />
      )}
    </List>
  );
}
