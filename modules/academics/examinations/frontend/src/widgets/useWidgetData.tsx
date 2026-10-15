import { ErrorState, SkeletonLines } from "@eos/ui-kit";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { ExaminationsApiError } from "../api/client";

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
      (data) => setLoad({ state: "ready", data }),
      (e: unknown) => {
        if (ctrl.signal.aborted) return;
        setLoad({ state: "error", message: errorMessage(e), retry: canRetry(e) ? retry : undefined });
      },
    );
    return () => ctrl.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [attempt]);
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

/** Retrying cannot fix a missing or expired session (401) or a missing permission (403). */
export function canRetry(e: unknown): boolean {
  return !(e instanceof ExaminationsApiError && (e.status === 401 || e.status === 403));
}

/**
 * The loading, empty and error states inside the card. The dashboard shell owns the card itself
 * (WidgetFrame from @eos/ui-kit); loading and error use the kit's SkeletonLines and ErrorState.
 */
export function WidgetStatus({ load, empty, children }: { load: Load<unknown>; empty: string | null; children: ReactNode }) {
  if (load.state === "loading") return <SkeletonLines />;
  if (load.state === "error") return <ErrorState title={load.message} onRetry={load.retry} />;
  if (empty) return <p className="eos-widget__status">{empty}</p>;
  return <>{children}</>;
}
