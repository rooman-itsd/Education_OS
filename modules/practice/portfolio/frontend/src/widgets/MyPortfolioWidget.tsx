import { useCallback, useEffect, useState } from "react";
import { Badge, EmptyState, ErrorState, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import { listMyItems, PortfolioApiError, type Item, type ItemStatus } from "../api/client";

type Failure = { title: string; detail?: string; retry: boolean };
type State = { kind: "loading" } | { kind: "error"; failure: Failure } | { kind: "ready"; items: Item[]; total: number };
type Tone = "danger" | "warning" | "info" | "success" | "neutral";

export function describeFailure(e: unknown): Failure {
  if (!(e instanceof PortfolioApiError) || [404, 502, 503].includes(e.status)) {
    return { title: "Portfolio data is not available yet.", retry: true };
  }
  if (e.status === 401) return { title: "Sign in again to see this.", retry: false };
  if (e.status === 403) return { title: "You do not have access to this.", retry: false };
  return { title: "Could not load portfolio items", detail: "Try again in a moment.", retry: true };
}

const STATUS_LABEL: Record<ItemStatus, string> = {
  draft: "Draft",
  submitted: "Submitted",
  under_review: "Under Review",
  approved: "Approved",
  changes_requested: "Changes Requested",
  withdrawn: "Withdrawn",
};

const STATUS_TONE: Record<ItemStatus, Tone> = {
  draft: "neutral",
  submitted: "info",
  under_review: "warning",
  approved: "success",
  changes_requested: "danger",
  withdrawn: "neutral",
};

/**
 * portfolio.my-portfolio widget on creative learner dashboards (actor, artist, designer, filmmaker, etc.).
 * Shows the learner's recent works, statuses, and review decisions.
 */
export function MyPortfolioWidget(_props: WidgetProps) {
  const [state, setState] = useState<State>({ kind: "loading" });

  const load = useCallback((signal?: AbortSignal) => {
    setState({ kind: "loading" });
    listMyItems(6, signal)
      .then((page) => setState({ kind: "ready", items: page.items, total: page.total }))
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

  if (state.items.length === 0) {
    return (
      <EmptyState title="No portfolio items yet">
        Build and submit your creative works for mentor review.
      </EmptyState>
    );
  }

  return (
    <List divided label="My portfolio items">
      {state.items.map((item: Item) => {
        const tone: Tone = STATUS_TONE[item.status] ?? "neutral";
        const label = STATUS_LABEL[item.status] ?? item.status;
        return (
          <ListRow
            key={item.id}
            title={item.title}
            meta={item.description || "No description"}
            tone={tone}
            trailing={<Badge tone={tone}>{label}</Badge>}
          />
        );
      })}
    </List>
  );
}
