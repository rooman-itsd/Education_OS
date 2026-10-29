import { useCallback, useEffect, useState } from "react";
import { Badge, EmptyState, ErrorState, Icons, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import {
  describeFailure,
  getSummary,
  listBookingsToday,
  type Booking,
  type BookingStatus,
  type Failure,
  type Summary,
  timeWindow,
} from "../api/client";

type State =
  | { kind: "loading" }
  | { kind: "error"; failure: Failure }
  | { kind: "ready"; bookings: Booking[]; total: number; summary: Summary };
type Tone = "danger" | "warning" | "info" | "success" | "neutral";

/** Statuses in words, and the tone of each; status always comes with a word, never colour alone. */
const LABEL: Partial<Record<BookingStatus, string>> = {
  pending: "Awaiting approval",
  confirmed: "Confirmed",
  checked_in: "Checked in",
  completed: "Completed",
  no_show: "No-show",
};
const TONE: Partial<Record<BookingStatus, Tone>> = {
  pending: "warning",
  confirmed: "info",
  checked_in: "success",
  completed: "neutral",
  no_show: "danger",
};

const SHOWN = 6;

/**
 * facility-booking.bookings-today on the staff and instructor dashboards: today's bookings on the resources the
 * viewer manages or approves, earliest first, with a counts line on top (GET /bookings?scope=managed&date=today and
 * GET /summary). The shell renders the panel and its title (the academy's vocabulary term); this is the body.
 */
export function BookingsTodayWidget(_props: WidgetProps) {
  const [state, setState] = useState<State>({ kind: "loading" });

  const load = useCallback((signal?: AbortSignal) => {
    setState({ kind: "loading" });
    Promise.all([listBookingsToday(SHOWN, signal), getSummary(signal)])
      .then(([page, summary]) => {
        const bookings = [...(page.items ?? [])].sort((a, b) => (a.start_at ?? "").localeCompare(b.start_at ?? ""));
        setState({ kind: "ready", bookings, total: page.total ?? bookings.length, summary });
      })
      .catch((e: unknown) => {
        if ((e as { name?: string })?.name !== "AbortError") {
          setState({ kind: "error", failure: describeFailure(e, "today's bookings") });
        }
      });
  }, []);

  useEffect(() => {
    const ctrl = new AbortController();
    load(ctrl.signal);
    return () => ctrl.abort();
  }, [load]);

  if (state.kind === "loading") return <SkeletonLines lines={4} />;
  if (state.kind === "error") {
    const { title, detail, retry } = state.failure;
    return (
      <ErrorState title={title} onRetry={retry ? () => load() : undefined}>
        {detail}
      </ErrorState>
    );
  }
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
