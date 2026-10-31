import { useCallback, useEffect, useState } from "react";
import { Badge, EmptyState, ErrorState, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import { listOpenProcesses, listMyApplications, SelectionProcessApiError, type Candidate, type CandidateStatus } from "../api/client";

type Failure = { title: string; detail?: string; retry: boolean };
type State = { kind: "loading" } | { kind: "error"; failure: Failure } | { kind: "ready"; candidates: Candidate[]; total: number };
type Tone = "danger" | "warning" | "info" | "success" | "neutral";

export function describeFailure(e: unknown): Failure {
  if (!(e instanceof SelectionProcessApiError) || [404, 502, 503].includes(e.status)) {
    return { title: "Application data is not available yet.", retry: true };
  }
  if (e.status === 401) return { title: "Sign in again to see this.", retry: false };
  if (e.status === 403) return { title: "You do not have access to this.", retry: false };
  return { title: "Could not load applications", detail: "Try again in a moment.", retry: true };
}

const STATUS_LABEL: Record<CandidateStatus, string> = {
  registered: "Registered",
  in_progress: "In Progress",
  selected: "Selected",
  waitlisted: "Waitlisted",
  rejected: "Not Selected",
  withdrawn: "Withdrawn",
};

const STATUS_TONE: Record<CandidateStatus, Tone> = {
  registered: "neutral",
  in_progress: "info",
  selected: "success",
  waitlisted: "warning",
  rejected: "danger",
  withdrawn: "neutral",
};

/**
 * selection-process.my-applications widget on candidate / student dashboards.
 * Displays the caller's active candidacies and current stage outcomes.
 */
export function MyApplicationsWidget(_props: WidgetProps) {
  const [state, setState] = useState<State>({ kind: "loading" });

  const load = useCallback((signal?: AbortSignal) => {
    setState({ kind: "loading" });
    // First find open processes, then list candidacies
    listOpenProcesses(5, signal)
      .then(async (procPage) => {
        const allCandidates: Candidate[] = [];
        for (const proc of procPage.items) {
          try {
            const candPage = await listMyApplications(proc.id, 5, signal);
            allCandidates.push(...candPage.items);
          } catch {
            // ignore per-process errors
          }
        }
        setState({ kind: "ready", candidates: allCandidates, total: allCandidates.length });
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
      <EmptyState title="No active applications">
        You have not registered for any auditions, jury rounds or selection processes.
      </EmptyState>
    );
  }

  return (
    <List divided label="My applications">
      {state.candidates.map((cand: Candidate) => {
        const tone: Tone = STATUS_TONE[cand.status] ?? "neutral";
        const label = STATUS_LABEL[cand.status] ?? cand.status;
        return (
          <ListRow
            key={cand.id}
            title={`Application #${cand.id.slice(0, 8)}`}
            meta={`Registered: ${new Date(cand.registered_at).toLocaleDateString()}`}
            tone={tone}
            trailing={<Badge tone={tone}>{label}</Badge>}
          />
        );
      })}
    </List>
  );
}

