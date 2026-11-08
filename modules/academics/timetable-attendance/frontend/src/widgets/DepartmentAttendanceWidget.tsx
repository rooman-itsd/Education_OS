import { Badge, EmptyState, ErrorState, Icons, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import { getDepartmentAttendance } from "../api/client";
import { percent } from "./format";
import { useWidgetData } from "./useWidgetData";

/** How many course sections the dashboard card shows. */
export const DEPARTMENT_LIMIT = 6;

/**
 * timetable-attendance.department-attendance on the Department Admin dashboard: attendance per course offering and
 * section of the department this term, with how many students are below the threshold
 * (GET /reports/department-attendance, FR-14). Until the platform can tell the module the caller's department
 * (PRD Q9) the API refuses with `department_unknown`, which the widget says in words.
 */
export function DepartmentAttendanceWidget(_props: WidgetProps) {
  const { state, reload } = useWidgetData(getDepartmentAttendance, "department attendance");

  if (state.kind === "loading") return <SkeletonLines lines={3} />;
  if (state.kind === "error") {
    const { title, detail, retry } = state.failure;
    return (
      <ErrorState title={title} onRetry={retry ? reload : undefined}>
        {detail}
      </ErrorState>
    );
  }
  const report = state.data;
  if (!report || report.items.length === 0) {
    return (
      <EmptyState icon={<Icons.PieChart />} title="No department attendance yet">
        Attendance per course and section appears here once classes have been taken this term.
      </EmptyState>
    );
  }
  const shown = report.items.slice(0, DEPARTMENT_LIMIT);
  return (
    <>
      <p className="eos-muted">
        Overall {percent(report.overall_percentage)} · minimum {report.threshold_percent}%
      </p>
      <List divided label="Attendance by course and section">
        {shown.map((row, i) => (
          <ListRow
            key={`${row.course_offering_id}-${row.section_id}`}
            index={i}
            icon={Icons.Building2}
            tone={row.students_below_threshold ? "warning" : "accent"}
            title={[row.course_code || "Course", row.section_code ? `Section ${row.section_code}` : ""].filter(Boolean).join(" · ")}
            meta={`${row.classes_held} classes held · average ${percent(row.average_percentage)}`}
            trailing={
              <Badge tone={row.students_below_threshold ? "danger" : "success"}>
                {row.students_below_threshold ? `${row.students_below_threshold} below minimum` : "None below minimum"}
              </Badge>
            }
          />
        ))}
      </List>
      {report.items.length > shown.length && <p className="eos-muted">and {report.items.length - shown.length} more</p>}
    </>
  );
}
