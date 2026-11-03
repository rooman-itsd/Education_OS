import { useCallback, useEffect, useState } from "react";
import { Badge, EmptyState, ErrorState, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import { listUpcomingSlots, SelectionProcessApiError, type Slot } from "../api/client";

type Failure = { title: string; detail?: string; retry: boolean };
type State = { kind: "loading" } | { kind: "error"; failure: Failure } | { kind: "ready"; slots: Slot[]; total: number };

export function describeFailure(e: unknown): Failure {
  if (!(e instanceof SelectionProcessApiError) || [404, 502, 503].includes(e.status)) {
    return { title: "Schedule data is not available yet.", retry: true };
  }
  if (e.status === 401) return { title: "Sign in again to see this.", retry: false };
  if (e.status === 403) return { title: "You do not have access to this.", retry: false };
  return { title: "Could not load upcoming schedule", detail: "Try again in a moment.", retry: true };
}

/**
 * selection-process.upcoming widget on candidate & judge dashboards.
 * Displays scheduled auditions, jury sessions, interviews, or trial rounds.
 */
export function UpcomingWidget(_props: WidgetProps) {
  const [state, setState] = useState<State>({ kind: "loading" });

  const load = useCallback((signal?: AbortSignal) => {
    setState({ kind: "loading" });
    listUpcomingSlots(6, signal)
      .then((slots) => setState({ kind: "ready", slots, total: slots.length }))
      .catch((e: unknown) => {
        if ((e as { name?: string })?.name !== "AbortError") {
          setState({ kind: "error", failure: describeFailure(e) });
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

  if (state.slots.length === 0) {
    return (
      <EmptyState title="No upcoming selection rounds">
        You have no auditions, jury rounds or selection sessions scheduled in the near future.
      </EmptyState>
    );
  }

  return (
    <List divided label="Upcoming selection events">
      {state.slots.map((slot: Slot) => {
        const timeStr = `${new Date(slot.starts_at).toLocaleDateString()} at ${new Date(slot.starts_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
        const meta = slot.location ? `${timeStr} • ${slot.location}` : timeStr;
        return (
          <ListRow
            key={slot.id}
            title={slot.title}
            meta={meta}
            tone="info"
            trailing={<Badge tone="info">Scheduled</Badge>}
          />
        );
      })}
    </List>
  );
}

