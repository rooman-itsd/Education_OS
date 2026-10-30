import type { DashboardWidget } from "@eos/ui-kit";
import { RegisteredCandidatesWidget } from "./RegisteredCandidatesWidget";

/**
 * Dashboard widgets exported by enrolment-registration.
 * Ids are "enrolment-registration.<widget>". The role layouts in
 * platform/identity/config/dashboards/*.yaml refer to them by id.
 * A widget imports only from this module and packages/, and fetches data
 * through this module's API client in ../api.
 */
export const widgets: DashboardWidget[] = [
  {
    id: "enrolment-registration.registered-candidates",
    title: "Registered candidates",
    permission: "enrolment-registration:registration:read",
    size: "1x1",
    kind: "list",
    subtitle: "This term, busiest courses first",
    component: RegisteredCandidatesWidget,
  },
];
