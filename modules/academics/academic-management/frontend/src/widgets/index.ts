import type { DashboardWidget } from "@eos/ui-kit";
import { CourseRoster } from "./CourseRoster";

/**
 * Dashboard widgets exported by academic-management.
 * Ids are "academic-management.<widget>". The role layouts in
 * platform/identity/config/dashboards/*.yaml refer to them by id.
 * A widget imports only from this module and packages/, and fetches data
 * through this module's API client in ../api.
 *
 * academic-management.faculty-load (Department Admin dashboard) is built by that dashboard's owner;
 * this module serves its endpoint, GET /faculty-load.
 */
export const widgets: DashboardWidget[] = [
  {
    id: "academic-management.course-roster",
    title: "Course roster",
    permission: "academic-management:roster:read",
    size: "2x1",
    kind: "list",
    subtitle: "Your courses this term",
    component: CourseRoster,
  },
];
