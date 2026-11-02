import { useCallback, useEffect, useState } from "react";
import { Badge, EmptyState, ErrorState, Icons, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import {
  AmcVendorSupportApiError,
  getContractsExpiring,
  type ExpiringContract,
  type ExpiringContracts,
} from "../api/client";

type Failure = { title: string; detail?: string; retry: boolean };
type State = { kind: "loading" } | { kind: "error"; failure: Failure } | { kind: "ready"; data: ExpiringContracts };
type Tone = "danger" | "warning" | "info";

/**
 * What the error state says, as the helpdesk and examinations widgets do. A missing or unreachable service (404,
 * 502, 503, network failure) is "not available yet", not the user's connection; retrying cannot fix 401 or 403.
 */
export function describeFailure(e: unknown): Failure {
  if (!(e instanceof AmcVendorSupportApiError) || [404, 502, 503].includes(e.status)) {
    return { title: "AMC data is not available yet.", retry: true };
  }
  if (e.status === 401) return { title: "Sign in again to see this.", retry: false };
  if (e.status === 403) return { title: "You do not have access to this.", retry: false };
  return { title: "Could not load expiring contracts", detail: "Try again in a moment.", retry: true };
}

/** Words for how soon a contract ends; status always comes with a word, never colour alone. */
export function dueLabel(daysLeft: number): { text: string; tone: Tone } {
  if (daysLeft < 0) {
    const ago = -daysLeft;
    return { text: `Expired ${ago} ${ago === 1 ? "day" : "days"} ago`, tone: "danger" };
  }
  if (daysLeft === 0) return { text: "Ends today", tone: "danger" };
  return { text: `${daysLeft} ${daysLeft === 1 ? "day" : "days"} left`, tone: daysLeft <= 30 ? "warning" : "info" };
}

function meta(c: ExpiringContract): string {
  return c.renewal_draft_exists ? `${c.number} · renewal drafted` : `${c.number} · ends ${c.end_date}`;
}

/**
 * amc-vendor-support.contracts-expiring on the Support Staff dashboard: active AMC contracts ending within the
 * window (AMC_VENDOR_SUPPORT_EXPIRY_WINDOW_DAYS) and those already past their end date, soonest first, with whether a
 * renewal is drafted (GET /stats/contracts-expiring). The shell renders the panel and its title; this is the body.
 */
export function ContractsExpiringWidget(_props: WidgetProps) {
  const [state, setState] = useState<State>({ kind: "loading" });

  const load = useCallback((signal?: AbortSignal) => {
    setState({ kind: "loading" });
    getContractsExpiring(undefined, signal)
      .then((data) => setState({ kind: "ready", data }))
      .catch((e: unknown) => {
        if ((e as { name?: string })?.name !== "AbortError") setState({ kind: "error", failure: describeFailure(e) });
      });
  }, []);

  useEffect(() => {
    const ctrl = new AbortController();
    load(ctrl.signal);
    return () => ctrl.abort();
  }, [load]);

  if (state.kind === "loading") return <SkeletonLines lines={4} />;
  if (state.kind === "error") {
    const { title, detail, retry } = state.failure;
    return (
      <ErrorState title={title} onRetry={retry ? () => load() : undefined}>
        {detail}
      </ErrorState>
    );
  }
  if (state.data.items.length === 0) {
    return (
      <EmptyState icon={<Icons.FileText />} title="No contracts expiring">
        {`Contracts ending in the next ${state.data.within_days} days appear here.`}
      </EmptyState>
    );
  }

  return (
    <List divided label="Contracts expiring">
      {state.data.items.map((c, i) => {
        const due = dueLabel(c.days_left);
        return (
          <ListRow
            key={c.contract_id}
            index={i}
            icon={c.days_left < 0 ? Icons.AlertTriangle : Icons.Clock}
            tone={due.tone}
            title={c.title}
            meta={meta(c)}
            trailing={<Badge tone={due.tone}>{due.text}</Badge>}
          />
        );
      })}
    </List>
  );
}
