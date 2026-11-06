import { useCallback, useEffect, useState } from "react";
import { Badge, EmptyState, ErrorState, Icons, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import { getDue, type DueStats, type Scope } from "../api/client";
import { describeFailure, dueLabel, filingMeta, type Failure } from "./shared";

type State = { kind: "loading" } | { kind: "error"; failure: Failure } | { kind: "ready"; data: DueStats };

/**
 * regulatory-reports.due on the Governance, Hospital Coordinator and Research Office dashboards: filings not yet
 * submitted that are overdue or due within REGULATORY_REPORTS_DUE_SOON_DAYS, with the soonest listed
 * (GET /stats/due). "Mine" (the default) counts the caller's own filings; "All" needs regulatory-reports:data:read,
 * and says "You do not have access to this." to a caller without it. The shell renders the panel and its title.
 */
export function DueWidget(_props: WidgetProps) {
  const [scope, setScope] = useState<Scope>("mine");
  const [state, setState] = useState<State>({ kind: "loading" });

  const load = useCallback((which: Scope, signal?: AbortSignal) => {
    setState({ kind: "loading" });
    getDue(which, signal)
      .then((data) => setState({ kind: "ready", data }))
      .catch((e: unknown) => {
        if ((e as { name?: string })?.name !== "AbortError") {
          setState({ kind: "error", failure: describeFailure(e, "filings due") });
        }
      });
  }, []);

  useEffect(() => {
    const ctrl = new AbortController();
    load(scope, ctrl.signal);
    return () => ctrl.abort();
  }, [load, scope]);

  const switcher = (
    <div role="group" aria-label="Whose filings" className="eos-segmented">
      {(["mine", "all"] as const).map((s) => (
        <button key={s} type="button" aria-pressed={scope === s} onClick={() => setScope(s)}>
          {s === "mine" ? "Mine" : "All"}
        </button>
      ))}
    </div>
  );

  let body;
  if (state.kind === "loading") body = <SkeletonLines lines={4} />;
  else if (state.kind === "error") {
    const { title, detail, retry } = state.failure;
    body = (
      <ErrorState title={title} onRetry={retry ? () => load(scope) : undefined}>
        {detail}
      </ErrorState>
    );
  } else if (state.data.soonest.length === 0) {
    body = (
      <EmptyState icon={<Icons.FileCheck2 />} title="Nothing due">
        {`Filings due in the next ${state.data.due_soon_days} days or overdue appear here.`}
      </EmptyState>
    );
  } else {
    const { overdue, due_soon, due_soon_days, soonest } = state.data;
    body = (
      <>
        <p className="eos-widget-summary">{`${overdue} overdue · ${due_soon} due in the next ${due_soon_days} days`}</p>
        <List divided label="Filings due">
          {soonest.map((f, i) => {
            const due = dueLabel(f);
            return (
              <ListRow
                key={f.filing_id}
                index={i}
                icon={due.tone === "danger" ? Icons.AlertTriangle : Icons.FileClock}
                tone={due.tone === "danger" ? "danger" : due.tone === "warning" ? "warning" : "info"}
                title={f.obligation_title}
                meta={filingMeta(f)}
                trailing={<Badge tone={due.tone === "danger" ? "danger" : due.tone === "warning" ? "warning" : "info"}>{due.text}</Badge>}
              />
            );
          })}
        </List>
      </>
    );
  }

  return (
    <>
      {switcher}
      {body}
    </>
  );
}
