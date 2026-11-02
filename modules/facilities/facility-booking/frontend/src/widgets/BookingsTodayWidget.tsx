import { Badge, EmptyState, ErrorState, Icons, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import { getSummary, listBookingsToday, timeWindow } from "../api/client";
import { LABEL, TONE } from "./status";
import { useWidgetData } from "./useWidgetData";

const SHOWN = 6;

/**
 * facility-booking.bookings-today on the staff and instructor dashboards: today's bookings on the resources the
 * viewer manages or approves, earliest first, with a counts line on top (GET /bookings?scope=managed&date=today and
 * GET /summary). The shell renders the panel and its title (the academy's vocabulary term); this is the body.
 */
export function BookingsTodayWidget(_props: WidgetProps) {
  const { load, reload } = useWidgetData(async (signal) => {
    const [page, summary] = await Promise.all([listBookingsToday(SHOWN, signal), getSummary(signal)]);
    const bookings = [...(page.items ?? [])].sort((a, b) => (a.start_at ?? "").localeCompare(b.start_at ?? ""));
    return { bookings, total: page.total ?? bookings.length, summary };
  }, "today's bookings");

  if (load.kind === "loading") return <SkeletonLines lines={4} />;
  if (load.kind === "error") {
    const { title, detail, retry } = load.failure;
    return (
      <ErrorState title={title} onRetry={retry ? reload : undefined}>
        {detail}
      </ErrorState>
    );
  }
  const state = load.data;
  const { summary } = state;
  const counts = [
    `${summary.bookings_today} today`,
    `${summary.pending_approval} awaiting approval`,
    `${summary.checked_in_now} in use now`,
    ...(summary.resources_out_of_service ? [`${summary.resources_out_of_service} out of service`] : []),
  ].join(" · ");

  if (state.total === 0) {
    // Nothing booked today can still leave requests to approve or resources out of service: keep those in sight.
    const attention = summary.pending_approval > 0 || summary.resources_out_of_service > 0;
    return (
      <>
        {attention && (
          <p className="eos-row__meta" aria-label="Booking counts">
            {counts}
          </p>
        )}
        <EmptyState icon={<Icons.CalendarCheck2 />} title="No bookings today">
          Bookings on the spaces and equipment you look after appear here.
        </EmptyState>
      </>
    );
  }

  return (
    <>
      <p className="eos-row__meta" aria-label="Booking counts">
        {counts}
      </p>
      <List divided label="Bookings today">
        {state.bookings.map((b, i) => {
          const tone = TONE[b.status] ?? "neutral";
          const what = [b.resource_name || "Resource", b.title].filter(Boolean).join(" · ");
          return (
            <ListRow
              key={b.id}
              index={i}
              icon={b.status === "pending" ? Icons.Clock : Icons.CalendarCheck2}
              tone={tone}
              title={timeWindow(b.start_at, b.end_at)}
              meta={what}
              trailing={<Badge tone={tone}>{LABEL[b.status] ?? String(b.status)}</Badge>}
            />
          );
        })}
        {state.total > state.bookings.length && (
          <ListRow title={`${state.total - state.bookings.length} more today`} tone="neutral" icon={Icons.CalendarRange} />
        )}
      </List>
    </>
  );
}
