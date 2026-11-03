import { useCallback, useEffect, useState } from "react";
import { Badge, EmptyState, ErrorState, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import { listOpenProcesses, SelectionProcessApiError, type Process } from "../api/client";

type Failure = { title: string; detail?: string; retry: boolean };
type State = { kind: "loading" } | { kind: "error"; failure: Failure } | { kind: "ready"; processes: Process[]; total: number };

export function describeFailure(e: unknown): Failure {
  if (!(e instanceof SelectionProcessApiError) || [404, 502, 503].includes(e.status)) {
    return { title: "Open calls are not available yet.", retry: true };
  }
  if (e.status === 401) return { title: "Sign in again to see this.", retry: false };
  if (e.status === 403) return { title: "You do not have access to this.", retry: false };
  return { title: "Could not load open calls", detail: "Try again in a moment.", retry: true };
}

/**
 * selection-process.open-calls widget on applicant & learner dashboards.
 * Displays auditions, squad trials, jury rounds open for registration.
 */
export function OpenCallsWidget(_props: WidgetProps) {
  const [state, setState] = useState<State>({ kind: "loading" });

  const load = useCallback((signal?: AbortSignal) => {
    setState({ kind: "loading" });
    listOpenProcesses(6, signal)
      .then((page) => setState({ kind: "ready", processes: page.items, total: page.total }))
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

  if (state.processes.length === 0) {
    return (
      <EmptyState title="No open calls right now">
        Check back later for new audition, casting, and selection announcements.
      </EmptyState>
    );
  }

  return (
    <List divided label="Open selection calls">
      {state.processes.map((proc: Process) => {
        const stageCount = proc.stages.length;
        const meta = `${stageCount} stage${stageCount === 1 ? "" : "s"} • ${proc.candidate_count} candidate${proc.candidate_count === 1 ? "" : "s"}`;
        return (
          <ListRow
            key={proc.id}
            title={proc.title}
            meta={meta}
            tone="info"
            trailing={<Badge tone="info">Open</Badge>}
          />
        );
      })}
    </List>
  );
}

