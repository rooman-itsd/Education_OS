import { useCallback, useEffect, useState } from "react";
import { Badge, EmptyState, ErrorState, Icons, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import { getActionItemStats, type ActionItemStats } from "../api/client";
import { describeFailure, dueLabel, statusLabel, type Failure } from "./shared";

type State = { kind: "loading" } | { kind: "error"; failure: Failure } | { kind: "ready"; data: ActionItemStats };

/**
 * iqac-accreditation.action-items on the Governance dashboard: quality action items that are open, in progress,
 * overdue or due within IQAC_ACCREDITATION_DUE_SOON_DAYS, with the soonest listed (GET /stats/action-items). The
 * counts cover the whole organisation, not only the viewer's items. The shell renders the panel and its title.
 */
export function ActionItemsWidget(_props: WidgetProps) {
  const [state, setState] = useState<State>({ kind: "loading" });

  const load = useCallback((signal?: AbortSignal) => {
    setState({ kind: "loading" });
    getActionItemStats(signal)
      .then((data) => setState({ kind: "ready", data }))
      .catch((e: unknown) => {
        if ((e as { name?: string })?.name !== "AbortError") {
          setState({ kind: "error", failure: describeFailure(e, "action items") });
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

  const { open, in_progress, overdue, due_soon, due_soon_days, soonest } = state.data;
  if (soonest.length === 0) {
    return (
      <EmptyState icon={<Icons.ClipboardList />} title="No open action items">
        Quality action items that are open or in progress appear here.
      </EmptyState>
    );
  }
  return (
    <>
      <p className="eos-widget-summary">{`${open} open · ${in_progress} in progress · ${overdue} overdue`}</p>
      <p className="eos-widget-summary">{`${due_soon} due in the next ${due_soon_days} days`}</p>
      <List divided label="Action items">
        {soonest.map((item, i) => {
          const due = dueLabel(item);
          const tone = due.tone === "danger" ? "danger" : due.tone === "warning" ? "warning" : "info";
          return (
            <ListRow
              key={item.id}
              index={i}
              icon={tone === "danger" ? Icons.AlertTriangle : Icons.Clock}
              tone={tone}
              title={item.title}
              meta={statusLabel(item.status)}
              trailing={<Badge tone={tone}>{due.text}</Badge>}
            />
          );
        })}
      </List>
    </>
  );
}
