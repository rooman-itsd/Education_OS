import { useCallback, useEffect, useState } from "react";
import { Badge, EmptyState, ErrorState, Icons, List, ListRow, Segmented, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import { SlaManagementApiError, getBreaches, type BreachScope, type BreachSummary, type OverdueClock } from "../api/client";

type Failure = { title: string; detail?: string; retry: boolean };
type State = { kind: "loading" } | { kind: "error"; failure: Failure } | { kind: "ready"; data: BreachSummary };

/**
 * What the error state says, as the helpdesk and amc-vendor-support widgets do. A missing or unreachable service
 * (404, 502, 503, network failure) is "not available yet", not the user's connection; retrying cannot fix 401 or 403.
 */
export function describeFailure(e: unknown): Failure {
  if (!(e instanceof SlaManagementApiError) || [404, 502, 503].includes(e.status)) {
    return { title: "SLA data is not available yet.", retry: true };
  }
  if (e.status === 401) return { title: "Sign in again to see this.", retry: false };
  if (e.status === 403) return { title: "You do not have access to this.", retry: false };
  return { title: "Could not load SLA breaches", detail: "Try again in a moment.", retry: true };
}

/** Business time past the due time in words; status always comes with a word, never colour alone. */
export function overdueLabel(minutes: number | undefined): string {
  if (!minutes || minutes < 1) return "Breached";
  if (minutes < 60) return `${minutes} min over`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest ? `${hours} h ${rest} min over` : `${hours} h over`;
}

const KIND: Record<OverdueClock["kind"], string> = { response: "First response", resolution: "Resolution" };
const PRIORITY: Record<OverdueClock["priority"], string> = { low: "Low", medium: "Medium", high: "High", urgent: "Urgent" };

function due(at: string): string {
  const d = new Date(at);
  return Number.isNaN(d.getTime()) ? at : d.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

/**
 * sla-management.breaches on the Support Staff dashboard: running clocks that are breached or at risk, breaches in
 * the last 24 hours, and the most overdue clocks with ticket number, kind, priority and due time
 * (GET /stats/breaches). "My tickets" (scope=mine) is the default; "All tickets" shows every clock. The shell renders
 * the panel and its title; this is the body.
 */
export function BreachesWidget(_props: WidgetProps) {
  const [scope, setScope] = useState<BreachScope>("mine");
  const [state, setState] = useState<State>({ kind: "loading" });

  const load = useCallback(
    (signal?: AbortSignal) => {
      setState({ kind: "loading" });
      getBreaches(scope, undefined, signal)
        .then((data) => setState({ kind: "ready", data }))
        .catch((e: unknown) => {
          if ((e as { name?: string })?.name !== "AbortError") setState({ kind: "error", failure: describeFailure(e) });
        });
    },
    [scope],
  );

  useEffect(() => {
    const ctrl = new AbortController();
    load(ctrl.signal);
    return () => ctrl.abort();
  }, [load]);

  const switcher = (
    <Segmented<BreachScope>
      label="Whose tickets"
      value={scope}
      onChange={setScope}
      options={[
        ["mine", "My tickets"],
        ["all", "All tickets"],
      ]}
    />
  );

  if (state.kind === "loading") return <SkeletonLines lines={4} />;
  if (state.kind === "error") {
    const { title, detail, retry } = state.failure;
    return (
      <ErrorState title={title} onRetry={retry ? () => load() : undefined}>
        {detail}
      </ErrorState>
    );
  }

  const { breached_open, at_risk, breached_last_24h, most_overdue } = state.data;
  const counts = (
    <p aria-label="SLA counts" style={{ display: "flex", gap: 8, flexWrap: "wrap", margin: "8px 0" }}>
      <Badge tone={breached_open ? "danger" : "neutral"}>{`${breached_open} breached`}</Badge>
      <Badge tone={at_risk ? "warning" : "neutral"}>{`${at_risk} at risk`}</Badge>
      <Badge tone="info">{`${breached_last_24h} in the last 24 h`}</Badge>
    </p>
  );

  if (breached_open === 0 && at_risk === 0 && most_overdue.length === 0) {
    return (
      <>
        {switcher}
        {counts}
        <EmptyState icon={<Icons.ShieldCheck />} title="Nothing breached or at risk">
          {scope === "mine" ? "Your tickets are within their SLA targets." : "Every ticket is within its SLA targets."}
        </EmptyState>
      </>
    );
  }

  return (
    <>
      {switcher}
      {counts}
      {most_overdue.length > 0 && (
        <List divided label="Most overdue">
          {most_overdue.map((c, i) => (
            <ListRow
              key={c.clock_id}
              index={i}
              icon={Icons.AlertTriangle}
              tone="danger"
              title={`${c.ticket_number} · ${KIND[c.kind]}`}
              meta={`${PRIORITY[c.priority]} priority · due ${due(c.due_at)}`}
              trailing={<Badge tone="danger">{overdueLabel(c.overdue_business_minutes)}</Badge>}
            />
          ))}
        </List>
      )}
    </>
  );
}
