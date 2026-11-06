import { EmptyState, Icons, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import { getActiveProjects, type Project } from "../api/client";
import { LoadFailure, shortDate, useLoad } from "./useLoad";

/** How many projects the dashboard card shows. */
export const ACTIVE_LIMIT = 5;

const fetchActive = (signal?: AbortSignal) => getActiveProjects(ACTIVE_LIMIT, signal);

function meta(p: Project): string {
  const team = p.member_count === 1 ? "1 member" : `${p.member_count ?? 0} members`;
  const ends = p.ends_on ? ` · ends ${shortDate(p.ends_on)}` : "";
  return `${p.kind ? `${p.kind} · ` : ""}${team}${ends}`;
}

/**
 * projects.active on guide and coordinator dashboards: active projects, ending soonest first (GET
 * /projects?status=active). A guide sees the projects they guide; a coordinator sees every project.
 */
export function ActiveProjectsWidget(_props: WidgetProps) {
  const [state, reload] = useLoad(fetchActive);

  if (state.kind === "loading") return <SkeletonLines lines={3} />;
  if (state.kind === "error") return <LoadFailure error={state.error} what="active projects" onRetry={reload} />;
  if (state.data.items.length === 0) {
    return (
      <EmptyState icon={<Icons.Layers />} title="No active projects">
        Approved projects appear here while the teams work on them.
      </EmptyState>
    );
  }

  return (
    <List divided label="Active projects">
      {state.data.items.map((p, i) => (
        <ListRow
          key={p.id}
          index={i}
          icon={Icons.Layers}
          title={p.title}
          meta={meta(p)}
          trailing={
            <span aria-label="Milestones accepted">
              {p.milestones_accepted ?? 0}/{p.milestones_total ?? 0}
            </span>
          }
        />
      ))}
    </List>
  );
}
