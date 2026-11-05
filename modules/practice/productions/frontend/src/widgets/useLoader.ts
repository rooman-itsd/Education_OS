import { useCallback, useEffect, useState } from "react";
import { describeFailure, type Failure } from "../api/client";

export type LoaderState<T> = { kind: "loading" } | { kind: "error"; failure: Failure } | { kind: "ready"; data: T };

/**
 * The four productions widgets all do the same thing: fetch once on mount, abort on unmount, keep an error
 * the viewer can retry. This holds that once instead of four times. `what` names the data in the error
 * message ("the calendar", "your parts").
 */
export function useLoader<T>(fetcher: (signal: AbortSignal) => Promise<T>, what: string, deps: unknown[] = []) {
  const [state, setState] = useState<LoaderState<T>>({ kind: "loading" });

  // The fetcher is a fresh closure on every render, so the caller's own deps decide when to reload.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  const run = useCallback((signal?: AbortSignal) => {
    setState({ kind: "loading" });
    fetcher(signal as AbortSignal)
      .then((data) => setState({ kind: "ready", data }))
      .catch((e: unknown) => {
        if ((e as { name?: string })?.name !== "AbortError") setState({ kind: "error", failure: describeFailure(e, what) });
      });
  }, deps);

  useEffect(() => {
    const ctrl = new AbortController();
    run(ctrl.signal);
    return () => ctrl.abort();
  }, [run]);

  return { state, reload: () => run() };
}
