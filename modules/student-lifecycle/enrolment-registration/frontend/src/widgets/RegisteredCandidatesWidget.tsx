import { useCallback, useEffect, useState } from "react";
import { Badge, EmptyState, ErrorState, Icons, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import { describeFailure, getRegisteredCandidates, isAbort, type Failure, type RegisteredCandidatesReport } from "../api/client";

const SHOWN = 5;

type State = { kind: "loading" } | { kind: "error"; failure: Failure } | { kind: "ready"; report: RegisteredCandidatesReport };

const count = (n: number) => n.toLocaleString("en-IN");

/** "CS101 · Programming I", or the offering's short id while academic-management's events have not arrived. */
function offeringLabel(o: RegisteredCandidatesReport["offerings"][number]): string {
  if (o.course_code && o.course_title) return `${o.course_code} · ${o.course_title}`;
  return o.course_code ?? o.course_title ?? `Course offering ${o.course_offering_id.slice(0, 8)}`;
}

/**
 * enrolment-registration.registered-candidates on the Examination Staff dashboard: how many students are registered
 * this term, how many of them for supplementary or backlog papers, and the busiest course offerings
 * (GET /reports/registered-candidates). The shell renders the panel and its title; this is the body.
 */
export function RegisteredCandidatesWidget(_props: WidgetProps) {
  const [state, setState] = useState<State>({ kind: "loading" });

  const load = useCallback((signal?: AbortSignal) => {
    setState({ kind: "loading" });
    getRegisteredCandidates(SHOWN, signal)
      .then((report) => setState({ kind: "ready", report }))
      .catch((e: unknown) => {
        if (!isAbort(e)) setState({ kind: "error", failure: describeFailure(e, "registered candidates") });
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
  const { report } = state;
  if (report.total === 0) {
    return (
      <EmptyState icon={<Icons.Users />} title="No registered candidates yet">
        Registrations the academic office confirms appear here.
      </EmptyState>
    );
  }
  const extras = [
    report.by_type.supplementary ? `${count(report.by_type.supplementary)} supplementary` : null,
    report.by_type.backlog ? `${count(report.by_type.backlog)} backlog` : null,
  ].filter(Boolean);
  return (
    <>
      <p className="eos-row__meta" aria-label="Registered candidates summary">
        <strong>{count(report.total)} registered</strong> · {report.term_name ?? "all terms"}
        {extras.length > 0 && ` · ${extras.join(" · ")}`}
      </p>
      <List divided label="Busiest course offerings">
        {report.offerings.map((o, i) => (
          <ListRow
            key={o.course_offering_id}
            index={i}
            icon={Icons.GraduationCap}
            tone="accent"
            title={offeringLabel(o)}
            trailing={<Badge tone="info">{count(o.registered)} registered</Badge>}
          />
        ))}
      </List>
    </>
  );
}
