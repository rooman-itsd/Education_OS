import type { DashboardWidget } from "@eos/ui-kit";
import { BookingsTodayWidget } from "./BookingsTodayWidget";
import { BookingsWidget } from "./BookingsWidget";
import { MyBookingsWidget } from "./MyBookingsWidget";
import "./widgets.css";

/**
 * Dashboard widgets exported by facility-booking.
 * Ids are "facility-booking.<widget>". The role layouts in
 * platform/identity/config/dashboards/*.yaml refer to them by id.
 * A widget imports only from this module and packages/, and fetches data
 * through this module's generated API client in ../api.
 */
export const widgets: DashboardWidget[] = [
  {
    id: "facility-booking.bookings",
    title: "Upcoming bookings",
    permission: "facility-booking:booking:read",
    size: "1x1",
    kind: "list",
    subtitle: "Spaces and equipment you approve",
    component: BookingsWidget,
  },
  {
    id: "facility-booking.bookings-today",
    title: "Bookings today",
    permission: "facility-booking:booking:read",
    size: "1x1",
    kind: "list",
    subtitle: "Spaces and equipment you look after",
    component: BookingsTodayWidget,
  },
  {
    id: "facility-booking.my-bookings",
    title: "My bookings",
    permission: "facility-booking:booking:read",
    size: "1x1",
    kind: "list",
    subtitle: "Your upcoming bookings",
    component: MyBookingsWidget,
  },
];
