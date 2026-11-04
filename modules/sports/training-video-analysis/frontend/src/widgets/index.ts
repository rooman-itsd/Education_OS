import type { DashboardWidget } from "@eos/ui-kit";
import { ReviewsPending } from "./ReviewsPending";
import { SessionPlan, TrainingSchedule } from "./UpcomingSessions";
import "./widgets.css";

/**
 * Dashboard widgets exported by training-video-analysis.
 * Ids are "training-video-analysis.<widget>". The role layouts in
 * platform/identity/config/dashboards/*.yaml refer to them by id.
 * A widget imports only from this module and packages/, and fetches data
 * through this module's API client in ../api.
 *
 * Endpoints and permissions per contracts/openapi.yaml and contracts/permissions.yaml. The coach holds
 * training-video-analysis-coach through module_roles in coach.yaml.
 */
export const widgets: DashboardWidget[] = [
  {
    id: "training-video-analysis.reviews-pending",
    title: "Videos to review",
    permission: "training-video-analysis:video:read",
    kind: "list",
    size: "2x1",
    subtitle: "Recent videos with no annotation yet",
    component: ReviewsPending,
  },
  {
    id: "training-video-analysis.session-plan",
    title: "Session plan",
    permission: "training-video-analysis:session:read",
    kind: "list",
    size: "2x1",
    subtitle: "Your coming training sessions",
    component: SessionPlan,
  },
  {
    id: "training-video-analysis.training-schedule",
    title: "Training schedule",
    permission: "training-video-analysis:session:read",
    kind: "list",
    size: "1x1",
    subtitle: "Your coming training sessions",
    component: TrainingSchedule,
  },
];
