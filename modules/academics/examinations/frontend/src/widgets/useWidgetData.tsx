import { useEffect, useState, type ReactNode } from "react";
import { ExaminationsApiError } from "../api/client";

export type Load<T> = { state: "loading" } | { state: "error"; message: string } | { state: "ready"; data: T };

/** Runs a fetch for a widget and cancels it if the widget unmounts first. */
export function useWidgetData<T>(fetcher: (signal: AbortSignal) => Promise<T>): Load<T> {
  const [load, setLoad] = useState<Load<T>>({ state: "loading" });
  useEffect(() => {
    const ctrl = new AbortController();
    fetcher(ctrl.signal).then(
      (data) => setLoad({ state: "ready", data }),
      (e: unknown) => {
        if (ctrl.signal.aborted) return;
        setLoad({ state: "error", message: errorMessage(e) });
      },
    );
    return () => ctrl.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return load;
}

export function errorMessage(e: unknown): string {
  if (e instanceof ExaminationsApiError) {
    if (e.status === 0 || e.status === 404 || e.status === 502 || e.status === 503)
      return "Examinations data is not available yet.";
    if (e.status === 401) return "Sign in again to see this.";
    if (e.status === 403) return "You do not have access to this.";
    return e.message || "Could not load.";
  }
  return "Could not load.";
}

/**
 * The loading, empty and error states inside the card. The dashboard shell owns the card itself
 * (WidgetFrame from @eos/ui-kit), so these use the same classes as its states.
 */
export function WidgetStatus({ load, empty, children }: { load: Load<unknown>; empty: string | null; children: ReactNode }) {
  if (load.state === "loading")
    return (
      <p className="eos-widget__status" aria-busy="true">
        Loading…
      </p>
    );
  if (load.state === "error")
    return (
      <p className="eos-widget__status eos-widget__status--error" role="alert">
        {load.message}
      </p>
    );
  if (empty) return <p className="eos-widget__status">{empty}</p>;
  return <>{children}</>;
}
