import { useCallback, useEffect, useState, type ReactNode } from "react";
import { EmptyState, ErrorState, SkeletonLines } from "@eos/ui-kit";
import { describeFailure, type Failure } from "../api/client";

export type Load<T> =
  | { state: "loading" }
  | { state: "error"; failure: Failure; retry: () => void }
  | { state: "ready"; data: T };

export function useWidgetData<T>(fetcher: (signal: AbortSignal) => Promise<T>, what: string): Load<T> {
  const [attempt, setAttempt] = useState(0);
  const [load, setLoad] = useState<Load<T>>({ state: "loading" });
  const retry = useCallback(() => setAttempt((n) => n + 1), []);
  useEffect(() => {
    const ctrl = new AbortController();
    setLoad({ state: "loading" });
    fetcher(ctrl.signal)
      .then((data) => setLoad({ state: "ready", data }))
      .catch((e: unknown) => {
        if ((e as { name?: string })?.name !== "AbortError") {
          setLoad({ state: "error", failure: describeFailure(e, what), retry });
        }
      });
    return () => ctrl.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attempt]);
  return load;
}

export function WidgetStatus({
  load,
  empty,
  icon,
  lines = 3,
  children,
}: {
  load: Load<unknown>;
  empty: { title: string; body?: ReactNode } | null;
  icon?: ReactNode;
  lines?: number;
  children: ReactNode;
}) {
  if (load.state === "loading") return <SkeletonLines lines={lines} />;
  if (load.state === "error") {
    return (
      <ErrorState title={load.failure.title} onRetry={load.failure.retry ? load.retry : undefined}>
        {load.failure.detail}
      </ErrorState>
    );
  }
  if (empty) {
    return (
      <EmptyState icon={icon} title={empty.title}>
        {empty.body}
      </EmptyState>
    );
  }
  return <>{children}</>;
}

