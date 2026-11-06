import { useCallback, useEffect, useState } from "react";
import { ErrorState } from "@eos/ui-kit";
import { describeFailure, type Failure } from "../api/client";

export type LoadState<T> = { kind: "loading" } | { kind: "error"; failure: Failure } | { kind: "ready"; data: T };

/**
 * Loads one resource for a widget: loading, then ready or error, with `reload` for the retry button. `what` names the
 * data in the error title ("Could not load <what>"). The request is aborted when the widget unmounts; an aborted
 * request is not shown as an error. `fetcher` must be stable (a module-level function).
 */
export function useLoad<T>(fetcher: (signal?: AbortSignal) => Promise<T>, what: string): [LoadState<T>, () => void] {
  const [state, setState] = useState<LoadState<T>>({ kind: "loading" });

  const load = useCallback(
    (signal?: AbortSignal) => {
      setState({ kind: "loading" });
      fetcher(signal)
        .then((data) => setState({ kind: "ready", data }))
        .catch((e: unknown) => {
          if ((e as { name?: string })?.name !== "AbortError") setState({ kind: "error", failure: describeFailure(e, what) });
        });
    },
    [fetcher, what],
  );

  useEffect(() => {
    const ctrl = new AbortController();
    load(ctrl.signal);
    return () => ctrl.abort();
  }, [load]);

  return [state, () => load()];
}

/** A widget's error state: why it failed, and a retry only where retrying can help (not on 401 or 403). */
export function WidgetError({ failure, onRetry }: { failure: Failure; onRetry: () => void }) {
  return (
    <ErrorState title={failure.title} onRetry={failure.retry ? onRetry : undefined}>
      {failure.detail}
    </ErrorState>
  );
}

/** "2 Nov" from an ISO date, in the reader's locale; empty for a malformed date. */
export function shortDate(iso: string): string {
  const d = new Date(`${iso.slice(0, 10)}T00:00:00`);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleDateString(undefined, { day: "numeric", month: "short" });
}

/** Hours without trailing zeros: 6, 6.5, 6.25. */
export function hours(value: number | undefined): string {
  return `${Math.round((value ?? 0) * 100) / 100}`;
}
