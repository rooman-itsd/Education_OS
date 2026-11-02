import { useCallback, useEffect, useRef, useState } from "react";
import { describeFailure, type Failure } from "../api/client";

export type Load<T> = { kind: "loading" } | { kind: "error"; failure: Failure } | { kind: "ready"; data: T };

/**
 * Runs a widget's fetch, runs it again on reload, and cancels it if the widget unmounts first, as the other modules'
 * widgets do: reload only bumps an attempt counter, so the effect owns the AbortController of every request.
 * A reload after an error shows the loading state again; one while data is shown (a refresh after a row action)
 * keeps the rows in place until the new data arrives.
 */
export function useWidgetData<T>(fetcher: (signal: AbortSignal) => Promise<T>, what: string): { load: Load<T>; reload: () => void } {
  const [attempt, setAttempt] = useState(0);
  const [load, setLoad] = useState<Load<T>>({ kind: "loading" });
  const reload = useCallback(() => setAttempt((n) => n + 1), []);
  // The fetcher is an inline arrow in each widget; the latest one runs, and only a reload starts a new request.
  const latest = useRef(fetcher);
  latest.current = fetcher;

  useEffect(() => {
    const ctrl = new AbortController();
    setLoad((l) => (l.kind === "ready" ? l : { kind: "loading" }));
    latest.current(ctrl.signal).then(
      (data) => {
        if (!ctrl.signal.aborted) setLoad({ kind: "ready", data });
      },
      (e: unknown) => {
        if (!ctrl.signal.aborted) setLoad({ kind: "error", failure: describeFailure(e, what) });
      },
    );
    return () => ctrl.abort();
  }, [attempt, what]);

  return { load, reload };
}
