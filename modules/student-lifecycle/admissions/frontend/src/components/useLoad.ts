import { useCallback, useEffect, useState } from "react";
import { describeFailure, isAbort, type Failure } from "../api/client";

export type Load<T> = { kind: "loading" } | { kind: "error"; failure: Failure } | { kind: "ready"; data: T };

/** Loads on mount (aborted on unmount) and again on reload(); failures become the widget's error wording. */
export function useLoad<T>(loader: (signal?: AbortSignal) => Promise<T>, what: string): [Load<T>, () => void] {
  const [state, setState] = useState<Load<T>>({ kind: "loading" });

  const load = useCallback(
    (signal?: AbortSignal) => {
      setState({ kind: "loading" });
      loader(signal)
        .then((data) => setState({ kind: "ready", data }))
        .catch((e: unknown) => {
          if (!isAbort(e)) setState({ kind: "error", failure: describeFailure(e, what) });
        });
    },
    [loader, what],
  );

  useEffect(() => {
    const ctrl = new AbortController();
    load(ctrl.signal);
    return () => ctrl.abort();
  }, [load]);

  return [state, () => load()];
}
