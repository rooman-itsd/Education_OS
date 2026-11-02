import { EmptyState, ErrorState, Icons, SkeletonLines } from "@eos/ui-kit";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { canRetry, errorMessage } from "../api/client";

export type Load<T> =
  | { state: "loading" }
  | { state: "error"; message: string; retry?: () => void }
  | { state: "ready"; data: T };

/**
 * Runs a fetch for a widget, runs it again on retry, and cancels it if the widget unmounts first.
 * An error offers retry only when trying again could help (see canRetry).
 */
export function useWidgetData<T>(fetcher: (signal: AbortSignal) => Promise<T>): Load<T> {
  const [attempt, setAttempt] = useState(0);
  const [load, setLoad] = useState<Load<T>>({ state: "loading" });
  const retry = useCallback(() => setAttempt((n) => n + 1), []);
  useEffect(() => {
    const ctrl = new AbortController();
    setLoad({ state: "loading" });
    fetcher(ctrl.signal).then(
      (data) => {
        if (!ctrl.signal.aborted) setLoad({ state: "ready", data });
      },
      (e: unknown) => {
        if (ctrl.signal.aborted) return;
        setLoad({ state: "error", message: errorMessage(e), retry: canRetry(e) ? retry : undefined });
      },
    );
    return () => ctrl.abort();
    // The fetcher is an inline arrow in each widget; refetch only on retry.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attempt]);
  return load;
}

/** What the empty state says: a title and, optionally, a line on what to expect. */
export interface Empty {
  title: string;
  body?: ReactNode;
}

/**
 * The loading, error and empty states inside the card. The dashboard shell owns the card itself
 * (WidgetFrame from @eos/ui-kit); these use the kit's SkeletonLines, ErrorState and EmptyState.
 */
export function WidgetStatus({
  load,
  empty,
  lines = 3,
  icon = <Icons.Trophy />,
  children,
}: {
  load: Load<unknown>;
  empty: Empty | null;
  lines?: number;
  icon?: ReactNode;
  children: ReactNode;
}) {
  if (load.state === "loading") return <SkeletonLines lines={lines} />;
  if (load.state === "error") return <ErrorState title={load.message} onRetry={load.retry} />;
  if (empty) {
    return (
      <EmptyState icon={icon} title={empty.title}>
        {empty.body}
      </EmptyState>
    );
  }
  return <>{children}</>;
}
