import type { DashboardWidget } from "@eos/ui-kit";
import { FilesPending } from "./FilesPending";
import "./widgets.css";

/**
 * Dashboard widgets exported by e-office.
 * Ids are "e-office.<widget>". The role layouts in
 * platform/identity/config/dashboards/*.yaml refer to them by id.
 * A widget imports only from this module and packages/, and fetches data
 * through this module's API client in ../api.
 *
 * Endpoints and permissions per contracts/openapi.yaml and contracts/permissions.yaml.
 */
export const widgets: DashboardWidget[] = [
  {
    id: "e-office.files-pending",
    title: "Files pending with me",
    permission: "e-office:file:use",
    kind: "panel",
    size: "2x1",
    component: FilesPending,
  },
];
