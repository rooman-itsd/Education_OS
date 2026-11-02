import type { DashboardWidget } from "@eos/ui-kit";
import { TournamentCalendar } from "./TournamentCalendar";
import { UpcomingTournaments } from "./UpcomingTournaments";
import "./widgets.css";

/**
 * Dashboard widgets exported by tournament-events.
 * Ids are "tournament-events.<widget>". The role layouts in
 * platform/identity/config/dashboards/*.yaml refer to them by id.
 * A widget imports only from this module and packages/, and fetches data
 * through this module's API client in ../api.
 *
 * Endpoints and permissions per contracts/openapi.yaml and contracts/permissions.yaml: the athlete layout holds
 * tournament-events-athlete and the coach layout tournament-events-coach, both of which grant tournament:read.
 */
export const widgets: DashboardWidget[] = [
  {
    id: "tournament-events.upcoming",
    title: "Upcoming tournaments",
    permission: "tournament-events:tournament:read",
    kind: "list",
    size: "2x1",
    subtitle: "Your entries and next fixtures",
    component: UpcomingTournaments,
  },
  {
    id: "tournament-events.calendar",
    title: "Tournament calendar",
    permission: "tournament-events:tournament:read",
    kind: "list",
    size: "2x1",
    subtitle: "Next four weeks",
    component: TournamentCalendar,
  },
];
