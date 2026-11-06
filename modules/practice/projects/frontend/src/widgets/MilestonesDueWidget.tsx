import { Badge, EmptyState, Icons, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import { getMyMilestones, type MilestoneDue } from "../api/client";
import { LoadFailure, useLoad } from "./useLoad";

/** Days ahead the dashboard card looks (the endpoint's default, PRD open question 3). */
export const WITHIN_DAYS = 14;

const fetchDue = (signal?: AbortSignal) => getMyMilestones(WITHIN_DAYS, signal);

function when(m: MilestoneDue) {
  const days = m.days_left ?? 0;
  if (m.overdue || days < 0) return <Badge tone="danger">Overdue</Badge>;
  if (m.status === "returned") return <Badge tone="warning">Returned</Badge>;
  if (days === 0) return <Badge tone="warning">Due today</Badge>;
  return <Badge tone="info">{days === 1 ? "1 day" : `${days} days`}</Badge>;
}

/**
 * projects.milestones-due on a learner's dashboard: pending, returned and overdue milestones of the caller's active
 * projects due in the next two weeks, earliest first (GET /me/milestones). The shell renders the panel and its title.
 */
export function MilestonesDueWidget(_props: WidgetProps) {
  const [state, reload] = useLoad(fetchDue);

  if (state.kind === "loading") return <SkeletonLines lines={3} />;
  if (state.kind === "error") return <LoadFailure error={state.error} what="milestones" onRetry={reload} />;
  if (state.data.length === 0) {
    return (
      <EmptyState icon={<Icons.CalendarCheck2 />} title="Nothing due in the next two weeks">
        Milestones of your active projects appear here as they come due.
      </EmptyState>
    );
  }

  return (
    <List divided label="Milestones due">
      {state.data.map((m, i) => (
        <ListRow
          key={m.id}
          index={i}
          date={m.due_on}
          tone={m.overdue ? "danger" : "accent"}
          title={m.title}
          meta={m.project_title}
          trailing={when(m)}
        />
      ))}
    </List>
  );
}
