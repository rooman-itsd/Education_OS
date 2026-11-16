import { useCallback, useEffect, useState } from "react";
import { Badge, EmptyState, ErrorState, Icons, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import { getNearingDeadline, type NearingDeadline } from "../api/client";
import { dateInIndia, describeFailure, dueLabel, statusLabel, type Failure } from "./shared";

type State = { kind: "loading" } | { kind: "error"; failure: Failure } | { kind: "ready"; data: NearingDeadline };

/**
 * rti.nearing-deadline on the Governance dashboard: open RTI requests that are overdue or due within
 * RTI_NEARING_DEADLINE_DAYS, with the soonest listed by request number (GET /stats/nearing-deadline). It shows request
 * numbers, what each is waiting for and when it is due; never an applicant's name, address, contact details or the
 * subject. The shell renders the panel and its title; this is the body.
 */
export function NearingDeadlineWidget(_props: WidgetProps) {
  const [state, setState] = useState<State>({ kind: "loading" });

  const load = useCallback((signal?: AbortSignal) => {
    setState({ kind: "loading" });
    getNearingDeadline(signal)
      .then((data) => setState({ kind: "ready", data }))
      .catch((e: unknown) => {
        if ((e as { name?: string })?.name !== "AbortError") {
          setState({ kind: "error", failure: describeFailure(e, "RTI deadlines") });
        }
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
  const { overdue, due_soon, within_days, items } = state.data;
  if (items.length === 0) {
    return (
      <EmptyState icon={<Icons.FileCheck2 />} title="No RTI deadlines close">
        {`Open requests due in the next ${within_days} days or overdue appear here.`}
      </EmptyState>
    );
  }
  return (
    <>
      <p className="eos-widget-summary">{`${overdue} overdue · ${due_soon} due in the next ${within_days} days`}</p>
      <List divided label="RTI requests nearing a deadline">
        {items.map((item, i) => {
          const due = dueLabel(item);
          const tone = due.tone === "danger" ? "danger" : due.tone === "warning" ? "warning" : "info";
          return (
            <ListRow
              key={item.request_id}
              index={i}
              icon={tone === "danger" ? Icons.AlertTriangle : Icons.FileClock}
              tone={tone}
              title={item.number}
              meta={`${statusLabel(item.status)} · ${dateInIndia(item.due_at)}`}
              trailing={<Badge tone={tone}>{due.text}</Badge>}
            />
          );
        })}
      </List>
    </>
  );
}
