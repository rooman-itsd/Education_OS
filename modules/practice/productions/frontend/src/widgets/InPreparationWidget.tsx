import { Badge, EmptyState, ErrorState, Icons, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import { getInPreparation, shortDate, type Page, type PreparationEntry } from "../api/client";
import { useLoader } from "./useLoader";

const SHOWN = 5;

/** What is still outstanding on a production, in words: overdue first, then the plain counts. */
function outstanding(entry: PreparationEntry): string {
  const parts: string[] = [];
  if (entry.tasks_overdue > 0) parts.push(`${entry.tasks_overdue} overdue`);
  if (entry.tasks_open > 0) parts.push(`${entry.tasks_open} of ${entry.tasks_total} tasks open`);
  if (entry.cast_unanswered > 0) {
    parts.push(`${entry.cast_unanswered} ${entry.cast_unanswered === 1 ? "invitation" : "invitations"} unanswered`);
  }
  if (parts.length === 0) parts.push("ready to schedule");
  return parts.join(" · ");
}

/**
 * productions.in-preparation on the lead dashboards (director, choreographer, studio instructor, the mentors):
 * the productions being got ready, most pressing first, with what is still outstanding on each — overdue
 * tasks, open tasks and invitations nobody has answered (GET /in-preparation).
 */
export function InPreparationWidget(_props: WidgetProps) {
  const { state, reload } = useLoader<Page<PreparationEntry>>(
    (signal) => getInPreparation({ limit: SHOWN }, signal),
    "what is in preparation",
  );

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
      <EmptyState icon={<Icons.ClipboardList />} title="Nothing in preparation">
        A production being got ready appears here with what is still outstanding.
      </EmptyState>
    );
  }

  return (
    <List divided label="In preparation">
      {state.data.items.map((entry, i) => (
        <ListRow
          key={entry.id}
          index={i}
          icon={entry.tasks_overdue > 0 ? Icons.AlertTriangle : Icons.ClipboardList}
          tone={entry.tasks_overdue > 0 ? "danger" : entry.tasks_open > 0 ? "warning" : "success"}
          title={entry.title}
          meta={outstanding(entry)}
          trailing={
            <Badge tone={entry.tasks_overdue > 0 ? "danger" : "neutral"}>
              {entry.starts_at ? shortDate(entry.starts_at) : "No date"}
            </Badge>
          }
        />
      ))}
      {state.data.total > state.data.items.length && (
        <ListRow
          title={`${state.data.total - state.data.items.length} more in preparation`}
          tone="neutral"
          icon={Icons.Layers}
        />
      )}
    </List>
  );
}
