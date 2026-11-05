import { Badge, EmptyState, ErrorState, Icons, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import { getMyGradingQueue, type GradingQueueItem } from "../api/client";
import { useWidgetData } from "./useWidgetData";

/** How many items the dashboard card shows; the badge still counts them all. */
export const QUEUE_LIMIT = 5;

function shortDate(iso: string | null | undefined): string {
  if (!iso) return "";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

function waitingLabel(item: GradingQueueItem): string {
  const noun = item.item_type === "quiz" ? "attempt" : "submission";
  return `${item.waiting_count} ${noun}${item.waiting_count === 1 ? "" : "s"}`;
}

/**
 * lms.assignments-to-grade on the Faculty dashboard and every layout extending it: assignments and quizzes in the
 * course spaces the caller teaches with work waiting for a grade, oldest waiting first (GET /me/grading-queue).
 * The shell renders the panel and its title; this is the body.
 */
export function AssignmentsToGradeWidget(_props: WidgetProps) {
  const { state, reload } = useWidgetData(getMyGradingQueue, "work to grade");

  if (state.kind === "loading") return <SkeletonLines lines={3} />;
  if (state.kind === "error") {
    const { title, detail, retry } = state.failure;
    return (
      <ErrorState title={title} onRetry={retry ? reload : undefined}>
        {detail}
      </ErrorState>
    );
  }
  const { items, total } = state.data;
  if (items.length === 0) {
    return (
      <EmptyState icon={<Icons.CheckCircle2 />} title="Nothing waiting to be graded">
        Submissions and quiz attempts that need your grade appear here.
      </EmptyState>
    );
  }

  const shown = items.slice(0, QUEUE_LIMIT);
  return (
    <>
      <List divided label="Work to grade">
        {shown.map((item, i) => (
          <ListRow
            key={`${item.item_type}-${item.item_id}`}
            index={i}
            icon={item.item_type === "quiz" ? Icons.ClipboardList : Icons.FileText}
            title={item.title}
            meta={
              <>
                {item.course_title ?? "Course"} · waiting since {shortDate(item.oldest_waiting_since)}
                {item.due_at && <> · due {shortDate(item.due_at)}</>}
              </>
            }
            trailing={<Badge tone="warning">{waitingLabel(item)}</Badge>}
          />
        ))}
      </List>
      {total > shown.length && <p className="eos-muted">and {total - shown.length} more</p>}
    </>
  );
}
