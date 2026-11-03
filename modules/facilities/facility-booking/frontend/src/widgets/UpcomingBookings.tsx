import { Badge, EmptyState, ErrorState, Icons, List, ListRow, SkeletonLines } from "@eos/ui-kit";
import { dayLabel, listUpcomingBookings, timeWindow } from "../api/client";
import { BookingActions } from "./BookingActions";
import { LABEL, TONE } from "./status";
import { useWidgetData } from "./useWidgetData";

export const SHOWN = 6;

export interface UpcomingBookingsProps {
  scope: "mine" | "managed";
  /** The list's accessible name, e.g. "My bookings". */
  label: string;
  emptyTitle: string;
  emptyText: string;
}

/**
 * The body of the my-bookings and bookings widgets: bookings not yet over, earliest first, each with its day, time
 * window, resource and status in words (GET /bookings?scope=<scope>&from=now). One already under way shows as checked
 * in or with its start before now; the day comes first, so a list spanning days reads in order.
 *
 * A row offers "Check in" and "Cancel" only when the booking's `can` lists check_in or cancel; the widget has no
 * permission logic of its own. On the managed list (scope=managed) a cancel asks for a reason, which the contract
 * requires of facility-booking:booking:manage; on the viewer's own list it asks to confirm. After an action succeeds
 * the list loads again.
 */
export function UpcomingBookings({ scope, label, emptyTitle, emptyText }: UpcomingBookingsProps) {
  const { load, reload } = useWidgetData(async (signal) => {
    const page = await listUpcomingBookings(scope, SHOWN, signal);
    const bookings = [...(page.items ?? [])].sort((a, b) => (a.start_at ?? "").localeCompare(b.start_at ?? ""));
    return { bookings, total: page.total ?? bookings.length };
  }, "upcoming bookings");

  if (load.kind === "loading") return <SkeletonLines lines={4} />;
  if (load.kind === "error") {
    const { title, detail, retry } = load.failure;
    return (
      <ErrorState title={title} onRetry={retry ? reload : undefined}>
        {detail}
      </ErrorState>
    );
  }
  const { bookings, total } = load.data;
  if (total === 0) {
    return (
      <EmptyState icon={<Icons.CalendarCheck2 />} title={emptyTitle}>
        {emptyText}
      </EmptyState>
    );
  }

  return (
    <List divided label={label}>
      {bookings.map((b, i) => {
        const tone = TONE[b.status] ?? "neutral";
        const what = [b.resource_name || "Resource", b.title].filter(Boolean).join(" · ");
        // The window is read against the booking's own day, so only an end on a later day carries a date.
        const start = new Date(b.start_at);
        const window = timeWindow(b.start_at, b.end_at, Number.isNaN(start.getTime()) ? new Date() : start);
        const when = `${dayLabel(b.start_at)} · ${window}`;
        return (
          <ListRow
            key={b.id}
            index={i}
            icon={b.status === "pending" ? Icons.Clock : Icons.CalendarCheck2}
            tone={tone}
            title={when}
            meta={
              <span className="eos-fb__meta">
                <span>{what}</span>
                <BookingActions booking={b} subject={`${what}, ${when}`} requireReason={scope === "managed"} onDone={reload} />
              </span>
            }
            trailing={<Badge tone={tone}>{LABEL[b.status] ?? String(b.status)}</Badge>}
          />
        );
      })}
      {total > bookings.length && (
        <ListRow title={`${total - bookings.length} more upcoming`} tone="neutral" icon={Icons.CalendarRange} />
      )}
    </List>
  );
}
