import { useCallback, useEffect, useState } from "react";
import { Badge, EmptyState, ErrorState, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import { listReviewsPending, PortfolioApiError, type Item } from "../api/client";

type Failure = { title: string; detail?: string; retry: boolean };
type State = { kind: "loading" } | { kind: "error"; failure: Failure } | { kind: "ready"; items: Item[]; total: number };

export function describeFailure(e: unknown): Failure {
  if (!(e instanceof PortfolioApiError) || [404, 502, 503].includes(e.status)) {
    return { title: "Portfolio review data is not available yet.", retry: true };
  }
  if (e.status === 401) return { title: "Sign in again to see this.", retry: false };
  if (e.status === 403) return { title: "You do not have access to this.", retry: false };
  return { title: "Could not load pending reviews", detail: "Try again in a moment.", retry: true };
}

/**
 * portfolio.reviews-pending widget on mentor and instructor dashboards (studio-instructor, design-mentor, etc.).
 * Displays submitted and under-review items assigned to the instructor.
 */
export function ReviewsPendingWidget(_props: WidgetProps) {
  const [state, setState] = useState<State>({ kind: "loading" });

  const load = useCallback((signal?: AbortSignal) => {
    setState({ kind: "loading" });
    listReviewsPending(6, signal)
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
      <EmptyState title="No reviews pending">
        You have no portfolio items awaiting your review.
      </EmptyState>
    );
  }

  return (
    <List divided label="Pending reviews">
      {state.items.map((item: Item) => {
        const isSubmitted = item.status === "submitted";
        const tone = isSubmitted ? "info" : "warning";
        const label = isSubmitted ? "Awaiting Review" : "In Review";
        return (
          <ListRow
            key={item.id}
            title={item.title}
            meta={`Submitted ${item.submitted_at ? new Date(item.submitted_at).toLocaleDateString() : "recently"}`}
            tone={tone}
            trailing={<Badge tone={tone}>{label}</Badge>}
          />
        );
      })}
    </List>
  );
}
