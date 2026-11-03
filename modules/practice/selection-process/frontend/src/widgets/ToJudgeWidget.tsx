import { useCallback, useEffect, useState } from "react";
import { Badge, EmptyState, ErrorState, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import { listOpenProcesses, listToJudge, SelectionProcessApiError, type Candidate } from "../api/client";

type Failure = { title: string; detail?: string; retry: boolean };
type State = { kind: "loading" } | { kind: "error"; failure: Failure } | { kind: "ready"; candidates: Candidate[]; total: number };

export function describeFailure(e: unknown): Failure {
  if (!(e instanceof SelectionProcessApiError) || [404, 502, 503].includes(e.status)) {
    return { title: "Judging tasks are not available yet.", retry: true };
  }
  if (e.status === 401) return { title: "Sign in again to see this.", retry: false };
  if (e.status === 403) return { title: "You do not have access to this.", retry: false };
  return { title: "Could not load judging tasks", detail: "Try again in a moment.", retry: true };
}

/**
 * selection-process.to-judge widget on panelist / judge dashboards.
 * Displays candidates awaiting scoring or decisions on panels the caller serves on.
 */
export function ToJudgeWidget(_props: WidgetProps) {
  const [state, setState] = useState<State>({ kind: "loading" });

  const load = useCallback((signal?: AbortSignal) => {
    setState({ kind: "loading" });
    listOpenProcesses(5, signal)
      .then(async (procPage) => {
        const toJudgeList: Candidate[] = [];
        for (const proc of procPage.items) {
          try {
            const page = await listToJudge(proc.id, 5, signal);
            toJudgeList.push(...page.items);
          } catch {
            // panelist might not be assigned to this process
          }
        }
        setState({ kind: "ready", candidates: toJudgeList, total: toJudgeList.length });
      })
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

  if (state.candidates.length === 0) {
    return (
      <EmptyState title="No candidates awaiting review">
        All candidate rounds assigned to your panels are up to date.
      </EmptyState>
    );
  }

  return (
    <List divided label="Candidates to judge">
      {state.candidates.map((cand: Candidate) => (
        <ListRow
          key={cand.id}
          title={`Candidate #${cand.person_id.slice(0, 8)}`}
          meta={`Stage: ${cand.current_stage_id ? cand.current_stage_id.slice(0, 8) : "Pending"}`}
          tone="warning"
          trailing={<Badge tone="warning">Pending Decision</Badge>}
        />
      ))}
    </List>
  );
}

