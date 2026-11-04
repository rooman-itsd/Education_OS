import type { WidgetProps } from "@eos/ui-kit";
import { UpcomingBookings } from "./UpcomingBookings";

/**
 * facility-booking.my-bookings on the learner and performer dashboards: the viewer's own upcoming bookings, booked by
 * or for them, with pending ones shown as awaiting approval (GET /bookings?scope=mine&from=now).
 * The shell renders the panel and its title (the academy's vocabulary term); this is the body.
 */
export function MyBookingsWidget(_props: WidgetProps) {
  return (
    <UpcomingBookings
      scope="mine"
      label="My bookings"
      emptyTitle="No upcoming bookings"
      emptyText="Spaces and equipment you book appear here."
    />
  );
}
