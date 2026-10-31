import { useCallback, useEffect, useState } from "react";
import { Badge, EmptyState, ErrorState, Icons, List, ListRow, SkeletonLines } from "@eos/ui-kit";
import { dayLabel, describeFailure, listUpcomingBookings, type Booking, type Failure, timeWindow } from "../api/client";
import { LABEL, TONE } from "./status";

type State = { kind: "loading" } | { kind: "error"; failure: Failure } | { kind: "ready"; bookings: Booking[]; total: number };

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
 */
export function UpcomingBookings({ scope, label, emptyTitle, emptyText }: UpcomingBookingsProps) {
  const [state, setState] = useState<State>({ kind: "loading" });

  const load = useCallback(
    (signal?: AbortSignal) => {
      setState({ kind: "loading" });
      listUpcomingBookings(scope, SHOWN, signal)
        .then((page) => {
          const bookings = [...(page.items ?? [])].sort((a, b) => (a.start_at ?? "").localeCompare(b.start_at ?? ""));
          setState({ kind: "ready", bookings, total: page.total ?? bookings.length });
        })
        .catch((e: unknown) => {
          if ((e as { name?: string })?.name !== "AbortError") {
            setState({ kind: "error", failure: describeFailure(e, "upcoming bookings") });
          }
        });
    },
    [scope],
  );

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
  if (state.total === 0) {
    return (
      <EmptyState icon={<Icons.CalendarCheck2 />} title={emptyTitle}>
        {emptyText}
      </EmptyState>
    );
  }

  return (
    <List divided label={label}>
      {state.bookings.map((b, i) => {
        const tone = TONE[b.status] ?? "neutral";
        const what = [b.resource_name || "Resource", b.title].filter(Boolean).join(" · ");
        // The window is read against the booking's own day, so only an end on a later day carries a date.
        const start = new Date(b.start_at);
        const window = timeWindow(b.start_at, b.end_at, Number.isNaN(start.getTime()) ? new Date() : start);
        return (
          <ListRow
            key={b.id}
            index={i}
            icon={b.status === "pending" ? Icons.Clock : Icons.CalendarCheck2}
            tone={tone}
            title={`${dayLabel(b.start_at)} · ${window}`}
            meta={what}
            trailing={<Badge tone={tone}>{LABEL[b.status] ?? String(b.status)}</Badge>}
          />
        );
      })}
      {state.total > state.bookings.length && (
        <ListRow title={`${state.total - state.bookings.length} more upcoming`} tone="neutral" icon={Icons.CalendarRange} />
      )}
    </List>
  );
}
