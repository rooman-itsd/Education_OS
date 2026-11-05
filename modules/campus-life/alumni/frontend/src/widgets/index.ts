import type { DashboardWidget } from "@eos/ui-kit";
import { Mentoring } from "./Mentoring";
import "./widgets.css";

/**
 * Dashboard widgets exported by alumni.
 * Ids are "alumni.<widget>". The role layouts in
 * platform/identity/config/dashboards/*.yaml refer to them by id.
 * A widget imports only from this module and packages/, and fetches data
 * through this module's API client in ../api.
 *
 * Endpoint and permission per contracts/openapi.yaml and contracts/permissions.yaml (issue #337). The
 * management-student layout holds the module role alumni-mentee, which grants alumni:self:read.
 */
export const widgets: DashboardWidget[] = [
  {
    id: "alumni.mentoring",
    title: "My mentor",
    permission: "alumni:self:read",
    kind: "panel",
    size: "1x1",
    component: Mentoring,
  },
];
