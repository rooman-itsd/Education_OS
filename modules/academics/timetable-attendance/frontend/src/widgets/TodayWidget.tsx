import { Badge, EmptyState, ErrorState, Icons, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import { getMySchedule, localDate } from "../api/client";
import { className, classMeta } from "./format";
import { useWidgetData } from "./useWidgetData";

const fetchToday = (signal?: AbortSignal) => getMySchedule(localDate(), signal);

/**
 * timetable-attendance.today on the Student dashboard and every layout extending it (dancer and the other
 * student-type roles): the classes of the caller's sections today, in the viewer's date, by start time
 * (GET /me/schedule). Wording stays neutral ("class"), since a dancer's layout uses it too. The shell renders the
 * panel and its title; this is the body.
 */
export function TodayWidget(_props: WidgetProps) {
  const { state, reload } = useWidgetData(fetchToday, "today's classes");

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
      <EmptyState icon={<Icons.CalendarRange />} title="No classes today">
        Your classes for the day appear here.
      </EmptyState>
    );
  }
  return (
    <List divided label="Today's classes">
      {items.map((c, i) => (
        <ListRow
          key={c.id}
          index={i}
          icon={Icons.Clock}
          tone={c.status === "cancelled" ? "neutral" : "accent"}
          title={className(c)}
          meta={classMeta(c)}
          trailing={c.status === "cancelled" ? <Badge tone="danger">Cancelled</Badge> : undefined}
        />
      ))}
    </List>
  );
}
