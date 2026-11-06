import { Badge, EmptyState, ErrorState, Icons, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import { getOpenByCommittee } from "../api/client";
import { KIND_LABEL, openLabel, overdueLabel, statusSummary } from "./shared";
import { useLoad } from "./useLoad";

/**
 * grievance.open-by-committee on the Governance dashboard: open cases per committee with their statuses and how many
 * are overdue (GET /stats/open-by-committee). Counts only: the coordinator never sees case content. The shell renders
 * the panel and its title.
 */
export function OpenByCommitteeWidget(_props: WidgetProps) {
  const { state, retry } = useLoad(getOpenByCommittee, "open grievances");

  if (state.kind === "loading") return <SkeletonLines lines={4} />;
  if (state.kind === "error") {
    const { title, detail, retry: canRetry } = state.failure;
    return (
      <ErrorState title={title} onRetry={canRetry ? retry : undefined}>
        {detail}
      </ErrorState>
    );
  }

  const { total_open, committees } = state.data;
  if (committees.length === 0) {
    return (
      <EmptyState icon={<Icons.Scale />} title="No committees yet">
        Committees you set up appear here with their open cases.
      </EmptyState>
    );
  }
  const overdue = committees.reduce((sum, c) => sum + c.overdue, 0);
  return (
    <>
      <p className="eos-widget-summary">{`${openLabel(total_open)} · ${overdueLabel(overdue)}`}</p>
      <List divided label="Open cases by committee">
        {committees.map((c, i) => (
          <ListRow
            key={c.committee_id}
            index={i}
            icon={c.overdue > 0 ? Icons.AlertTriangle : Icons.Scale}
            tone={c.overdue > 0 ? "danger" : c.open > 0 ? "info" : "neutral"}
            title={c.name}
            meta={c.open === 0 ? KIND_LABEL[c.kind] : `${KIND_LABEL[c.kind]} · ${statusSummary(c.by_status)}`}
            trailing={
              <Badge tone={c.overdue > 0 ? "danger" : "neutral"}>{`${c.open} open · ${overdueLabel(c.overdue)}`}</Badge>
            }
          />
        ))}
      </List>
    </>
  );
}
