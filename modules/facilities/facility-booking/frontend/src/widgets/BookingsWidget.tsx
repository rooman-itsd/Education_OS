import type { WidgetProps } from "@eos/ui-kit";
import { UpcomingBookings } from "./UpcomingBookings";

/**
 * facility-booking.bookings on the coach and medical-staff dashboards: upcoming bookings on the resources the viewer
 * approves, so requests waiting for them and the week's use stay in sight (GET /bookings?scope=managed&from=now).
 * The shell renders the panel and its title (the academy's vocabulary term); this is the body.
 */
export function BookingsWidget(_props: WidgetProps) {
  return (
    <UpcomingBookings
      scope="managed"
      label="Upcoming bookings"
      emptyTitle="No upcoming bookings"
      emptyText="Bookings on the spaces and equipment you approve appear here."
    />
  );
}
