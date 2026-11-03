import { useCallback, useEffect, useState } from "react";
import { Badge, EmptyState, ErrorState, Icons, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import { AcademicManagementApiError, getFacultyLoad, type FacultyLoadReport } from "../api/client";

type Load = { kind: "loading" } | { kind: "error"; retry: boolean } | { kind: "ready"; report: FacultyLoadReport | null };

/** Retrying cannot fix a missing session (401) or a missing permission (403). */
function failed(e: unknown): { kind: "error"; retry: boolean } {
  const status = e instanceof AcademicManagementApiError ? e.status : 0;
  return { kind: "error", retry: status !== 401 && status !== 403 };
}

const aborted = (e: unknown) => (e as { name?: string })?.name === "AbortError";

/** Up to one decimal, no trailing ".0": 12 and 7.5, not 12.0. */
const hours = (n: number) => `${Number.isInteger(n) ? n : n.toFixed(1)} h`;

/**
 * academic-management.faculty-load on the Department Admin dashboard: each faculty member's weekly contact hours in
 * the active term against the configured maximum (GET /faculty-load), over-load first. The shell renders the panel
 * and its title; this is the body.
 */
export function FacultyLoad(_props: WidgetProps) {
  const [state, setState] = useState<Load>({ kind: "loading" });

  const load = useCallback((signal?: AbortSignal) => {
    setState({ kind: "loading" });
    getFacultyLoad(signal)
      .then((report) => setState({ kind: "ready", report }))
      .catch((e: unknown) => {
        if (!aborted(e)) setState(failed(e));
      });
  }, []);

  useEffect(() => {
    const ctrl = new AbortController();
    load(ctrl.signal);
    return () => ctrl.abort();
  }, [load]);

  if (state.kind === "loading") return <SkeletonLines lines={4} />;
  if (state.kind === "error") {
    return (
      <ErrorState title="Could not load faculty load" onRetry={state.retry ? () => load() : undefined}>
        {state.retry ? "Check your connection and try again." : "You do not have access to faculty load."}
      </ErrorState>
    );
  }
  const report = state.report;
  if (report === null) {
    return (
      <EmptyState icon={<Icons.Clock />} title="No active term">
        Faculty load appears here once a term is active.
      </EmptyState>
    );
  }
  if (report.items.length === 0) {
    return (
      <EmptyState icon={<Icons.Users />} title={`No teaching assigned in ${report.academic_period_name}`}>
        Faculty appear here once they are assigned to an offering.
      </EmptyState>
    );
  }
  const max = report.max_weekly_contact_hours;
  return (
    <>
      <p className="eos-widget__status">
        {`${report.academic_period_name} · ${report.over_load_count} of ${report.faculty_count} over the ${hours(max)} weekly maximum`}
      </p>
      <List divided label={`Faculty load, ${report.academic_period_name}`}>
        {report.items.map((f, i) => (
          <ListRow
            key={f.faculty_id}
            index={i}
            title={f.faculty_name}
            meta={`${f.offerings_count} ${f.offerings_count === 1 ? "offering" : "offerings"}`}
            trailing={<Badge tone={f.over_load ? "danger" : "success"}>{`${hours(f.contact_hours)}${f.over_load ? " · over" : ""}`}</Badge>}
          />
        ))}
      </List>
    </>
  );
}
