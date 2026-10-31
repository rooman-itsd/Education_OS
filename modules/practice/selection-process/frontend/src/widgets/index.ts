import type { DashboardWidget } from "@eos/ui-kit";
import { MyApplicationsWidget } from "./MyApplicationsWidget";
import { OpenCallsWidget } from "./OpenCallsWidget";
import { ToJudgeWidget } from "./ToJudgeWidget";
import { UpcomingWidget } from "./UpcomingWidget";

/**
 * Dashboard widgets exported by practice/selection-process.
 * Ids are referenced in platform/identity/config/dashboards/*.yaml.
 */
export const widgets: DashboardWidget[] = [
  {
    id: "selection-process.my-applications",
    title: "My Applications",
    permission: "selection-process:candidate:read",
    size: "1x1",
    kind: "list",
    subtitle: "Your applications and selection stage status",
    component: MyApplicationsWidget,
  },
  {
    id: "selection-process.open-calls",
    title: "Open Calls",
    permission: "selection-process:process:read",
    size: "1x1",
    kind: "list",
    subtitle: "Auditions, juries and open selection calls",
    component: OpenCallsWidget,
  },
  {
    id: "selection-process.to-judge",
    title: "To Judge",
    permission: "selection-process:decision:write",
    size: "1x1",
    kind: "list",
    subtitle: "Candidates awaiting panel scoring and decisions",
    component: ToJudgeWidget,
  },
  {
    id: "selection-process.upcoming",
    title: "Upcoming Selection Events",
    permission: "selection-process:candidate:read",
    size: "1x1",
    kind: "list",
    subtitle: "Scheduled auditions and jury rounds",
    component: UpcomingWidget,
  },
];
