import { Badge, EmptyState, Icons, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import { getMyTrainees, type TraineeToAssess } from "../api/client";
import { shortDate, useLoad, WidgetError } from "../components/useLoad";

/** How many trainees the dashboard card shows. */
export const TRAINEES_LIMIT = 5;

const load = (signal?: AbortSignal) => getMyTrainees(TRAINEES_LIMIT, signal);

function action(t: TraineeToAssess) {
  if (t.final_assessment_due) return <Badge tone="warning">Final assessment due</Badge>;
  return <Badge tone="info">{t.entries_awaiting === 1 ? "1 entry to verify" : `${t.entries_awaiting} entries to verify`}</Badge>;
}

/**
 * field-training.trainees-to-assess on a supervisor's dashboard: active placements they supervise with log entries
 * awaiting verification or a final assessment due, most urgent first (GET /me/trainees).
 */
export function TraineesToAssessWidget(_props: WidgetProps) {
  const [state, reload] = useLoad(load, "your trainees");

  if (state.kind === "loading") return <SkeletonLines lines={3} />;
  if (state.kind === "error") return <WidgetError failure={state.failure} onRetry={reload} />;
  if (state.data.length === 0) {
    return (
      <EmptyState icon={<Icons.UserCheck />} title="Nothing to assess right now">
        Trainees with entries to verify or a final assessment due appear here.
      </EmptyState>
    );
  }
  return (
    <List divided label="Trainees to assess">
      {state.data.map((t, i) => {
        const p = t.placement;
        const extra = t.final_assessment_due && t.entries_awaiting > 0 ? ` · ${t.entries_awaiting} to verify` : "";
        return (
          <ListRow
            key={p.id}
            index={i}
            icon={Icons.User}
            tone={t.final_assessment_due ? "warning" : "info"}
            title={p.trainee_name ?? "Trainee"}
            meta={`${[p.opening_title, p.site_name].filter(Boolean).join(" · ")} · ends ${shortDate(p.ends_on)}${extra}`}
            trailing={action(t)}
          />
        );
      })}
    </List>
  );
}
