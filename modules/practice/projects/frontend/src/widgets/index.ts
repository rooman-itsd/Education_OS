import type { DashboardWidget } from "@eos/ui-kit";
import { ActiveProjectsWidget } from "./ActiveProjectsWidget";
import { MilestonesDueWidget } from "./MilestonesDueWidget";
import { MyProjectsWidget } from "./MyProjectsWidget";
import { ToReviewWidget } from "./ToReviewWidget";

/**
 * Dashboard widgets exported by projects.
 * Ids are "projects.<widget>". The role layouts in
 * platform/identity/config/dashboards/*.yaml refer to them by id.
 * A widget imports only from this module and packages/, and fetches data
 * through this module's generated API client in ../api.
 *
 * Each declares the one key the shell checks. projects.active is backed by GET /projects?status=active, which takes
 * projects:project:read or projects:guidance:read; the widget declares projects:guidance:read, so it shows on the
 * dashboard of every role holding projects-guide and lists the projects that person guides.
 */
export const widgets: DashboardWidget[] = [
  {
    id: "projects.my-projects",
    title: "My projects",
    permission: "projects:self:read",
    size: "2x1",
    kind: "list",
    subtitle: "Progress and the next milestone",
    component: MyProjectsWidget,
  },
  {
    id: "projects.milestones-due",
    title: "Milestones due",
    permission: "projects:self:read",
    size: "1x1",
    kind: "list",
    subtitle: "Next two weeks and overdue",
    component: MilestonesDueWidget,
  },
  {
    id: "projects.to-review",
    title: "To review",
    permission: "projects:guidance:read",
    size: "2x1",
    kind: "list",
    subtitle: "Submissions from the teams you guide",
    component: ToReviewWidget,
  },
  {
    id: "projects.active",
    title: "Active projects",
    permission: "projects:guidance:read",
    size: "2x1",
    kind: "list",
    subtitle: "Ending soonest first",
    component: ActiveProjectsWidget,
  },
];
