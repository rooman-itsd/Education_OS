import { Badge, EmptyState, Icons, List, ListRow, SkeletonLines, type BadgeTone, type WidgetProps } from "@eos/ui-kit";
import { getMyProjects, type MyProject, type ProjectStatus } from "../api/client";
import { LoadFailure, shortDate, useLoad } from "./useLoad";

const STATUS: Record<ProjectStatus, { label: string; tone: BadgeTone }> = {
  proposed: { label: "Proposed", tone: "info" },
  active: { label: "Active", tone: "success" },
  submitted: { label: "Submitted", tone: "accent" },
  completed: { label: "Completed", tone: "neutral" },
  rejected: { label: "Rejected", tone: "danger" },
  cancelled: { label: "Cancelled", tone: "neutral" },
};

function progress(p: MyProject): string {
  const total = p.milestones_total ?? 0;
  return total === 0 ? "No milestones yet" : `${p.milestones_accepted ?? 0} of ${total} milestones accepted`;
}

/**
 * projects.my-projects on a learner's dashboard: the projects the caller is on, in progress first, with progress and
 * the next milestone (GET /me/projects). The shell renders the panel and its title; this is the body.
 */
export function MyProjectsWidget(_props: WidgetProps) {
  const [state, reload] = useLoad(getMyProjects);

  if (state.kind === "loading") return <SkeletonLines lines={3} />;
  if (state.kind === "error") return <LoadFailure error={state.error} what="your projects" onRetry={reload} />;
  if (state.data.length === 0) {
    return (
      <EmptyState icon={<Icons.FolderOpen />} title="You are not on a project yet">
        Projects you propose or join appear here.
      </EmptyState>
    );
  }

  return (
    <List divided label="My projects">
      {state.data.map((p, i) => {
        const status = STATUS[p.status] ?? STATUS.active;
        const next = p.next_milestone;
        return (
          <ListRow
            key={p.id}
            index={i}
            icon={Icons.FolderOpen}
            title={p.title}
            meta={
              <>
                {p.my_role === "lead" ? "Lead" : "Member"} · {progress(p)}
                {next && (
                  <>
                    {" "}
                    · next: {next.title}, due {shortDate(next.due_on)}
                  </>
                )}
              </>
            }
            trailing={<Badge tone={status.tone}>{status.label}</Badge>}
          />
        );
      })}
    </List>
  );
}
