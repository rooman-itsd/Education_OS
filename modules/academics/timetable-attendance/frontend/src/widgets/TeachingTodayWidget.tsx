import { Badge, EmptyState, ErrorState, Icons, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import { getMyTeachingSchedule, localDate, type ScheduledClass } from "../api/client";
import { className, classMeta } from "./format";
import { useWidgetData } from "./useWidgetData";

const fetchTeaching = (signal?: AbortSignal) => getMyTeachingSchedule(localDate(), signal);

/** The attendance state of a class, in words (FR-6: "with each class's attendance session state"). */
export function attendanceBadge(c: ScheduledClass) {
  if (c.status === "cancelled") return <Badge tone="danger">Cancelled</Badge>;
  const session = c.attendance_session;
  if (session?.status === "closed" || c.status === "completed") return <Badge tone="success">Attendance taken</Badge>;
  if (session?.status === "open") return <Badge tone="warning">Attendance open</Badge>;
  return <Badge>Not taken</Badge>;
}

/**
 * timetable-attendance.today-classes on the Faculty dashboard and every layout extending it: the classes the caller
 * teaches today, in the viewer's date, with each one's attendance state (GET /me/teaching-schedule).
 */
export function TeachingTodayWidget(_props: WidgetProps) {
  const { state, reload } = useWidgetData(fetchTeaching, "your classes");

  if (state.kind === "loading") return <SkeletonLines lines={3} />;
  if (state.kind === "error") {
    const { title, detail, retry } = state.failure;
    return (
      <ErrorState title={title} onRetry={retry ? reload : undefined}>
        {detail}
      </ErrorState>
    );
  }
  const { items } = state.data;
  if (items.length === 0) {
    return (
      <EmptyState icon={<Icons.CalendarCheck2 />} title="No classes to teach today">
        The classes you teach today appear here, with their attendance.
      </EmptyState>
    );
  }
  return (
    <List divided label="Classes you teach today">
      {items.map((c, i) => (
        <ListRow key={c.id} index={i} icon={Icons.Presentation} title={className(c)} meta={classMeta(c)} trailing={attendanceBadge(c)} />
      ))}
    </List>
  );
}
