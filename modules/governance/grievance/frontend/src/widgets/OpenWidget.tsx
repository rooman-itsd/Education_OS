import { Badge, EmptyState, ErrorState, Icons, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import { getOpenByTrack } from "../api/client";
import { openLabel, overdueLabel, TRACK_LABEL } from "./shared";
import { useLoad } from "./useLoad";

/**
 * grievance.open on the Management dashboard: open cases per track, with how many are overdue (GET /stats/open).
 * Counts only: management never sees case content. The shell renders the panel and its title.
 */
export function OpenWidget(_props: WidgetProps) {
  const { state, retry } = useLoad(getOpenByTrack, "open grievances");

  if (state.kind === "loading") return <SkeletonLines lines={3} />;
  if (state.kind === "error") {
    const { title, detail, retry: canRetry } = state.failure;
    return (
      <ErrorState title={title} onRetry={canRetry ? retry : undefined}>
        {detail}
      </ErrorState>
    );
  }

  const { total_open, overdue, tracks } = state.data;
  if (total_open === 0) {
    return (
      <EmptyState icon={<Icons.ShieldAlert />} title="No open cases">
        Open grievances, ragging and sexual harassment complaints appear here as counts.
      </EmptyState>
    );
  }
  return (
    <>
      <p className="eos-widget-summary">{`${openLabel(total_open)} · ${overdueLabel(overdue)}`}</p>
      <List divided label="Open cases by track">
        {tracks.map((t, i) => (
          <ListRow
            key={t.track}
            index={i}
            icon={t.overdue > 0 ? Icons.AlertTriangle : Icons.ShieldAlert}
            tone={t.overdue > 0 ? "danger" : t.open > 0 ? "info" : "neutral"}
            title={TRACK_LABEL[t.track] ?? t.track}
            meta={overdueLabel(t.overdue)}
            trailing={<Badge tone={t.overdue > 0 ? "danger" : "neutral"}>{`${t.open} open`}</Badge>}
          />
        ))}
      </List>
    </>
  );
}
