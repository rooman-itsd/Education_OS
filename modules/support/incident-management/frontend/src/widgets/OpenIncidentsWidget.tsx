import { useCallback, useEffect, useState } from "react";
import { Badge, EmptyState, ErrorState, Icons, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import { getOpenCounts, IncidentManagementApiError, type OpenCounts, type OpenStatus, type Severity } from "../api/client";

type Failure = { title: string; detail?: string; retry: boolean };
type State = { kind: "loading" } | { kind: "error"; failure: Failure } | { kind: "ready"; data: OpenCounts };
type Tone = "danger" | "warning" | "info" | "neutral";

/**
 * What the error state says, as the helpdesk and amc-vendor-support widgets do. A missing or unreachable service
 * (404, 502, 503, network failure) is "not available yet", not the user's connection; retrying cannot fix 401 or 403.
 */
export function describeFailure(e: unknown): Failure {
  if (!(e instanceof IncidentManagementApiError) || [404, 502, 503].includes(e.status)) {
    return { title: "Incident data is not available yet.", retry: true };
  }
  if (e.status === 401) return { title: "Sign in again to see this.", retry: false };
  if (e.status === 403) return { title: "You do not have access to this.", retry: false };
  return { title: "Could not load open incidents", detail: "Try again in a moment.", retry: true };
}

/** Words for the severities and the tone of each row; status always comes with a word, never colour alone. */
const SEVERITY_LABEL: Record<Severity, string> = { critical: "Critical", high: "High", medium: "Medium", low: "Low" };
const SEVERITY_TONE: Record<Severity, Tone> = { critical: "danger", high: "warning", medium: "info", low: "neutral" };

/** Words for the statuses counted: "open" is reported but not yet picked up. */
const STATUS_LABEL: Record<OpenStatus, string> = {
  open: "not yet picked up",
  investigating: "investigating",
  mitigated: "mitigated",
};

/** "1 not yet picked up · 2 investigating · 0 mitigated" */
export function statusLine(byStatus: OpenCounts["by_status"]): string {
  return byStatus.map((s) => `${s.count} ${STATUS_LABEL[s.status]}`).join(" · ");
}

/**
 * incident-management.open on the Support Staff dashboard: incidents in open, investigating or mitigated, one row per
 * severity, critical first, and how many are in each of those statuses (GET /stats/open). The shell renders the
 * panel and its title; this is the body.
 */
export function OpenIncidentsWidget(_props: WidgetProps) {
  const [state, setState] = useState<State>({ kind: "loading" });

  const load = useCallback((signal?: AbortSignal) => {
    setState({ kind: "loading" });
    getOpenCounts(signal)
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
  if (state.data.total_open === 0) {
    return (
      <EmptyState icon={<Icons.ShieldCheck />} title="No open incidents">
        Reported service disruptions appear here until they are resolved.
      </EmptyState>
    );
  }

  const { total_open, by_severity, by_status } = state.data;
  return (
    <div>
      <p className="eos-row__meta">{`${total_open} open: ${statusLine(by_status)}`}</p>
      <List divided label="Open incidents by severity">
        {by_severity.map((row, i) => (
          <ListRow
            key={row.severity}
            index={i}
            icon={row.severity === "critical" ? Icons.Siren : Icons.AlertTriangle}
            tone={row.count > 0 ? SEVERITY_TONE[row.severity] : "neutral"}
            title={SEVERITY_LABEL[row.severity]}
            trailing={<Badge tone={row.count > 0 ? SEVERITY_TONE[row.severity] : "neutral"}>{`${row.count} open`}</Badge>}
          />
        ))}
      </List>
    </div>
  );
}
