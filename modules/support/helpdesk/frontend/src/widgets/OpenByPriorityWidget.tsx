import { useCallback, useEffect, useState } from "react";
import { Badge, EmptyState, ErrorState, Icons, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import { getOpenByPriority, HelpdeskApiError, type OpenByPriority, type Priority } from "../api/client";

type Failure = { title: string; detail?: string; retry: boolean };
type State = { kind: "loading" } | { kind: "error"; failure: Failure } | { kind: "ready"; data: OpenByPriority };

/**
 * What the error state says, as the examinations widgets do. A missing or unreachable service (404, 502, 503,
 * network failure) is "not available yet", not the user's connection; retrying cannot fix 401 or 403.
 */
export function describeFailure(e: unknown): Failure {
  if (!(e instanceof HelpdeskApiError) || [404, 502, 503].includes(e.status)) {
    return { title: "Helpdesk data is not available yet.", retry: true };
  }
  if (e.status === 401) return { title: "Sign in again to see this.", retry: false };
  if (e.status === 403) return { title: "You do not have access to this.", retry: false };
  return { title: "Could not load open tickets", detail: "Try again in a moment.", retry: true };
}

/** Words for the priorities, and the tone of each row; status always comes with a word, never colour alone. */
const LABEL: Record<Priority, string> = { urgent: "Urgent", high: "High", medium: "Medium", low: "Low" };
const TONE: Record<Priority, "danger" | "warning" | "info" | "neutral"> = {
  urgent: "danger",
  high: "warning",
  medium: "info",
  low: "neutral",
};

/**
 * helpdesk.open-by-priority on the Support Staff dashboard: open tickets (new, in progress, on hold) in the
 * caller's queues, one row per priority, urgent first, with how many are unassigned, assigned to the caller and
 * on hold (GET /stats/open-by-priority). The shell renders the panel and its title; this is the body.
 */
export function OpenByPriorityWidget(_props: WidgetProps) {
  const [state, setState] = useState<State>({ kind: "loading" });

  const load = useCallback((signal?: AbortSignal) => {
    setState({ kind: "loading" });
    getOpenByPriority(undefined, signal)
      .then((data) => setState({ kind: "ready", data }))
      .catch((e: unknown) => {
        if ((e as { name?: string })?.name !== "AbortError") setState({ kind: "error", failure: describeFailure(e) });
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
  if (state.data.total_open === 0) {
    return (
      <EmptyState icon={<Icons.LifeBuoy />} title="No open tickets">
        New tickets in your queues appear here.
      </EmptyState>
    );
  }

  return (
    <List divided label="Open tickets by priority">
      {state.data.rows.map((row, i) => (
        <ListRow
          key={row.priority}
          index={i}
          icon={row.priority === "urgent" ? Icons.AlertTriangle : Icons.LifeBuoy}
          tone={TONE[row.priority]}
          title={LABEL[row.priority]}
          meta={`${row.unassigned} unassigned · ${row.assigned_to_me} assigned to you · ${row.on_hold} on hold`}
          trailing={<Badge tone={row.open > 0 ? TONE[row.priority] : "neutral"}>{`${row.open} open`}</Badge>}
        />
      ))}
    </List>
  );
}
