import { useCallback, useEffect, useState } from "react";
import { describeFailure, type Failure } from "./shared";

export type State<T> = { kind: "loading" } | { kind: "error"; failure: Failure } | { kind: "ready"; data: T };

/** Loads once on mount (and again on retry), aborting the request when the widget goes away. */
export function useLoad<T>(fetcher: (signal?: AbortSignal) => Promise<T>, what: string) {
  const [state, setState] = useState<State<T>>({ kind: "loading" });

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

  return { state, retry: () => load() };
}
