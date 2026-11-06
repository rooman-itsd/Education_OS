import type { DashboardWidget } from "@eos/ui-kit";
import { AssignmentsToGradeWidget } from "./AssignmentsToGradeWidget";
import { CourseMaterialsWidget } from "./CourseMaterialsWidget";

/**
 * Dashboard widgets exported by lms.
 * Ids are "lms.<widget>". The role layouts in
 * platform/identity/config/dashboards/*.yaml refer to them by id:
 * lms.assignments-to-grade on faculty.yaml, lms.course-materials on student.yaml
 * (and every layout extending those roles).
 * A widget imports only from this module and packages/, and fetches data
 * through this module's API client in ../api.
 */
export const widgets: DashboardWidget[] = [
  {
    id: "lms.assignments-to-grade",
    title: "Assignments to grade",
    permission: "lms:grade:manage-assigned",
    size: "2x1",
    kind: "list",
    subtitle: "Submissions and attempts waiting for you",
    component: AssignmentsToGradeWidget,
  },
  {
    id: "lms.course-materials",
    title: "Course materials",
    permission: "lms:course-space:read-own",
    size: "2x1",
    kind: "list",
    subtitle: "Recently published in your courses",
    component: CourseMaterialsWidget,
  },
];
