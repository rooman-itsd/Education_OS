import { useCallback, useEffect, useState } from "react";
import { describeFailure, type Failure } from "../api/client";

export type WidgetState<T> = { kind: "loading" } | { kind: "error"; failure: Failure } | { kind: "ready"; data: T };

/** Loads a widget's data once, cancels it on unmount, and offers `reload` for the error state's retry. */
export function useWidgetData<T>(fetcher: (signal?: AbortSignal) => Promise<T>, what: string) {
  const [state, setState] = useState<WidgetState<T>>({ kind: "loading" });

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

  return { state, reload: () => load() };
}
