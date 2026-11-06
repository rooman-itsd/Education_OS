import { ErrorState } from "@eos/ui-kit";
import { useCallback, useEffect, useState } from "react";
import { describeFailure } from "../api/client";

export type LoadState<T> = { kind: "loading" } | { kind: "error"; error: unknown } | { kind: "ready"; data: T };

/**
 * Loads a widget's data once on mount (aborted on unmount) and again on `reload()`, the retry of the error state.
 * An aborted request leaves the state alone; any other failure shows the error state, never a crash.
 */
export function useLoad<T>(fetcher: (signal?: AbortSignal) => Promise<T>): [LoadState<T>, () => void] {
  const [state, setState] = useState<LoadState<T>>({ kind: "loading" });

  const load = useCallback(
    (signal?: AbortSignal) => {
      setState({ kind: "loading" });
      fetcher(signal)
        .then((data) => setState({ kind: "ready", data }))
        .catch((e: unknown) => {
          if ((e as { name?: string })?.name !== "AbortError") setState({ kind: "error", error: e });
        });
    },
    [fetcher],
  );

  useEffect(() => {
    const ctrl = new AbortController();
    load(ctrl.signal);
    return () => ctrl.abort();
  }, [load]);

  return [state, () => load()];
}

/** The error state for a failed load: why it failed (describeFailure), with a retry only where one can help. */
export function LoadFailure({ error, what, onRetry }: { error: unknown; what: string; onRetry: () => void }) {
  const { title, detail, retry } = describeFailure(error, what);
  return (
    <ErrorState title={title} onRetry={retry ? onRetry : undefined}>
      {detail}
    </ErrorState>
  );
}

export function shortDate(iso: string | undefined | null): string {
  if (!iso) return "";
  const d = new Date(iso.length === 10 ? `${iso}T00:00:00` : iso);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}
