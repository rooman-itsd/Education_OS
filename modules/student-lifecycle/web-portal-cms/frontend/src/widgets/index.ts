import type { DashboardWidget } from "@eos/ui-kit";
import { AnnouncementsWidget } from "./AnnouncementsWidget";

/**
 * Dashboard widgets exported by web-portal-cms.
 * Ids are "web-portal-cms.<widget>". The role layouts in
 * platform/identity/config/dashboards/*.yaml refer to them by id.
 * A widget imports only from this module and packages/, and fetches data
 * through this module's API client in ../api.
 */
export const widgets: DashboardWidget[] = [
  {
    id: "web-portal-cms.announcements",
    title: "Announcements",
    permission: "web-portal-cms:announcement:read",
    size: "1x1",
    kind: "list",
    subtitle: "Current notices from your organisation",
    component: AnnouncementsWidget,
  },
];
