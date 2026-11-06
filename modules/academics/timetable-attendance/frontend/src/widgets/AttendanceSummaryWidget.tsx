import { Badge, EmptyState, ErrorState, Icons, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import { getMyAttendanceSummary } from "../api/client";
import { percent } from "./format";
import { useWidgetData } from "./useWidgetData";

/**
 * timetable-attendance.attendance-summary on the Student dashboard and every layout extending it: the caller's
 * attendance per course this term, with the shortage flag below the threshold (GET /me/attendance-summary, FR-13).
 * Excused classes are not counted; a course with no counted class shows a dash. No active term, or no closed class
 * yet, is the empty state.
 */
export function AttendanceSummaryWidget(_props: WidgetProps) {
  const { state, reload } = useWidgetData(getMyAttendanceSummary, "your attendance");

  if (state.kind === "loading") return <SkeletonLines lines={3} />;
  if (state.kind === "error") {
    const { title, detail, retry } = state.failure;
    return (
      <ErrorState title={title} onRetry={retry ? reload : undefined}>
        {detail}
      </ErrorState>
    );
  }
  const summary = state.data;
  if (!summary || summary.items.length === 0) {
    return (
      <EmptyState icon={<Icons.PieChart />} title="No attendance recorded yet">
        Your attendance appears here once your classes have been taken.
      </EmptyState>
    );
  }
  return (
    <>
      <p className="eos-muted">
        Overall {percent(summary.overall_percentage)} · minimum {summary.threshold_percent}%
      </p>
      <List divided label="Attendance by course">
        {summary.items.map((item, i) => (
          <ListRow
            key={item.course_offering_id}
            index={i}
            icon={Icons.BookOpen}
            tone={item.below_threshold ? "warning" : "accent"}
            title={[item.course_code, item.course_title].filter(Boolean).join(" ") || "Course"}
            meta={`${item.attended} of ${item.classes_held} attended${item.excused ? ` · ${item.excused} excused` : ""}`}
            trailing={
              <Badge tone={item.below_threshold ? "danger" : item.percentage === null ? "neutral" : "success"}>
                {item.below_threshold ? `${percent(item.percentage)} short` : percent(item.percentage)}
              </Badge>
            }
          />
        ))}
      </List>
    </>
  );
}
