import { Badge, EmptyState, Icons, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import { getMyReviews } from "../api/client";
import { LoadFailure, useLoad } from "./useLoad";

/** How many items the dashboard card shows. */
export const REVIEW_LIMIT = 5;

const fetchReviews = (signal?: AbortSignal) => getMyReviews(REVIEW_LIMIT, signal);

function waiting(days: number | undefined): string {
  if (!days) return "Today";
  return days === 1 ? "1 day" : `${days} days`;
}

/**
 * projects.to-review on a guide's dashboard: submitted milestones and final submissions of the projects the caller
 * guides, oldest first (GET /me/reviews). The shell renders the panel and its title; this is the body.
 */
export function ToReviewWidget(_props: WidgetProps) {
  const [state, reload] = useLoad(fetchReviews);

  if (state.kind === "loading") return <SkeletonLines lines={3} />;
  if (state.kind === "error") return <LoadFailure error={state.error} what="work to review" onRetry={reload} />;
  if (state.data.length === 0) {
    return (
      <EmptyState icon={<Icons.FileCheck2 />} title="Nothing waiting for your review">
        Submissions from the teams you guide appear here.
      </EmptyState>
    );
  }

  return (
    <List divided label="Work to review">
      {state.data.map((r, i) => {
        const days = r.waiting_days ?? 0;
        return (
          <ListRow
            key={r.submission.id}
            index={i}
            icon={r.kind === "final" ? Icons.BadgeCheck : Icons.FileText}
            tone={days >= 7 ? "warning" : "accent"}
            title={r.kind === "final" ? "Final submission" : (r.milestone_title ?? "Milestone")}
            meta={
              <>
                {r.project_title} · version {r.submission.version}
              </>
            }
            trailing={<Badge tone={days >= 7 ? "warning" : "neutral"}>{waiting(days)}</Badge>}
          />
        );
      })}
    </List>
  );
}
