import { Badge, EmptyState, ErrorState, Icons, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import { getMyAttendanceToMark, type AttendanceToMarkItem } from "../api/client";
import { className, clock, shortDate } from "./format";
import { useWidgetData } from "./useWidgetData";

/** How many classes the dashboard card shows; the rest are counted below the list. */
export const MARK_LIMIT = 5;

function state(item: AttendanceToMarkItem) {
  if (!item.counts) return <Badge tone="warning">Not opened</Badge>;
  const { unmarked } = item.counts;
  return <Badge tone={unmarked ? "warning" : "info"}>{unmarked ? `${unmarked} unmarked` : "Ready to close"}</Badge>;
}

/**
 * timetable-attendance.attendance-to-mark on the Faculty dashboard and every layout extending it: the caller's
 * classes that have started and still wait for attendance inside the marking window, oldest first
 * (GET /me/attendance-to-mark, FR-12).
 */
export function AttendanceToMarkWidget(_props: WidgetProps) {
  const { state: s, reload } = useWidgetData(getMyAttendanceToMark, "attendance to mark");

  if (s.kind === "loading") return <SkeletonLines lines={3} />;
  if (s.kind === "error") {
    const { title, detail, retry } = s.failure;
    return (
      <ErrorState title={title} onRetry={retry ? reload : undefined}>
        {detail}
      </ErrorState>
    );
  }
  const { items, total } = s.data;
  if (items.length === 0) {
    return (
      <EmptyState icon={<Icons.CheckCircle2 />} title="No attendance waiting to be marked">
        Classes you have taught appear here until their attendance is closed.
      </EmptyState>
    );
  }
  const shown = items.slice(0, MARK_LIMIT);
  return (
    <>
      <List divided label="Attendance to mark">
        {shown.map((item, i) => (
          <ListRow
            key={item.scheduled_class.id}
            index={i}
            icon={Icons.UserCheck}
            title={className(item.scheduled_class)}
            meta={`${shortDate(item.scheduled_class.starts_at)} at ${clock(item.scheduled_class.starts_at)} · mark by ${shortDate(item.marking_deadline)} ${clock(item.marking_deadline)}`}
            trailing={state(item)}
          />
        ))}
      </List>
      {total > shown.length && <p className="eos-muted">and {total - shown.length} more</p>}
    </>
  );
}
