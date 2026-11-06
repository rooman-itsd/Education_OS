import type { DashboardWidget } from "@eos/ui-kit";
import { CalendarWidget } from "./CalendarWidget";
import { InPreparationWidget } from "./InPreparationWidget";
import { MyRolesWidget } from "./MyRolesWidget";
import { UpcomingWidget } from "./UpcomingWidget";

/**
 * Dashboard widgets exported by productions.
 * Ids are "productions.<widget>". The role layouts in
 * platform/identity/config/dashboards/*.yaml refer to them by id.
 * A widget imports only from this module and packages/, and fetches data
 * through this module's generated API client in ../api.
 */
export const widgets: DashboardWidget[] = [
  {
    id: "productions.calendar",
    title: "Production calendar",
    permission: "productions:production:read",
    size: "2x1",
    kind: "list",
    subtitle: "Scheduled over the coming weeks",
    component: CalendarWidget,
  },
  {
    id: "productions.in-preparation",
    title: "In preparation",
    permission: "productions:task:read",
    size: "1x1",
    kind: "list",
    subtitle: "What is still outstanding",
    component: InPreparationWidget,
  },
  {
    id: "productions.my-roles",
    title: "My parts",
    permission: "productions:role:read-own",
    size: "1x1",
    kind: "list",
    subtitle: "Parts and crew jobs you hold",
    component: MyRolesWidget,
  },
  {
    id: "productions.upcoming",
    title: "Upcoming productions",
    permission: "productions:production:read",
    size: "1x1",
    kind: "list",
    subtitle: "The next performances and events",
    component: UpcomingWidget,
  },
];
