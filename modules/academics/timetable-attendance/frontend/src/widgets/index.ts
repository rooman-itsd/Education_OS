import type { DashboardWidget } from "@eos/ui-kit";
import { AttendanceSummaryWidget } from "./AttendanceSummaryWidget";
import { AttendanceToMarkWidget } from "./AttendanceToMarkWidget";
import { DepartmentAttendanceWidget } from "./DepartmentAttendanceWidget";
import { TeachingTodayWidget } from "./TeachingTodayWidget";
import { TodayWidget } from "./TodayWidget";

/**
 * Dashboard widgets exported by timetable-attendance.
 * Ids are "timetable-attendance.<widget>". The role layouts in
 * platform/identity/config/dashboards/*.yaml refer to them by id: today and attendance-summary on student.yaml
 * (and dancer.yaml and the other layouts extending student), today-classes and attendance-to-mark on faculty.yaml
 * (and the layouts extending faculty), department-attendance on department-admin.yaml.
 * A widget imports only from this module and packages/, and fetches data through this module's API client in ../api.
 */
export const widgets: DashboardWidget[] = [
  {
    id: "timetable-attendance.today",
    title: "Today's classes",
    permission: "timetable-attendance:scheduled-class:read-own",
    size: "1x1",
    kind: "list",
    subtitle: "Your timetable for today",
    component: TodayWidget,
  },
  {
    id: "timetable-attendance.attendance-summary",
    title: "My attendance",
    permission: "timetable-attendance:report:read-own",
    size: "1x1",
    kind: "list",
    subtitle: "This term, by course",
    component: AttendanceSummaryWidget,
  },
  {
    id: "timetable-attendance.today-classes",
    title: "Teaching today",
    permission: "timetable-attendance:scheduled-class:read",
    size: "1x1",
    kind: "list",
    subtitle: "Your classes and their attendance",
    component: TeachingTodayWidget,
  },
  {
    id: "timetable-attendance.attendance-to-mark",
    title: "Attendance to mark",
    permission: "timetable-attendance:attendance-record:mark",
    size: "1x1",
    kind: "list",
    subtitle: "Classes still open for marking",
    component: AttendanceToMarkWidget,
  },
  {
    id: "timetable-attendance.department-attendance",
    title: "Department attendance",
    permission: "timetable-attendance:report:read-department",
    size: "2x1",
    kind: "list",
    subtitle: "This term, by course and section",
    component: DepartmentAttendanceWidget,
  },
];
