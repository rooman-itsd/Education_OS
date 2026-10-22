import { useCallback, useEffect, useState } from "react";
import { Badge, EmptyState, ErrorState, Icons, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import { getOpenByPriority, type OpenByPriority, type Priority } from "../api/client";

type State = { kind: "loading" } | { kind: "error" } | { kind: "ready"; data: OpenByPriority };

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
        if ((e as { name?: string })?.name !== "AbortError") setState({ kind: "error" });
      });
  }, []);

  useEffect(() => {
    const ctrl = new AbortController();
    load(ctrl.signal);
    return () => ctrl.abort();
  }, [load]);

  if (state.kind === "loading") return <SkeletonLines lines={4} />;
  if (state.kind === "error") {
    return (
      <ErrorState title="Could not load open tickets" onRetry={() => load()}>
        Check your connection and try again.
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
