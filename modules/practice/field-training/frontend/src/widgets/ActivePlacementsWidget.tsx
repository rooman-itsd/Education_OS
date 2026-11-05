import { EmptyState, Icons, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import { getActivePlacements, type Placement } from "../api/client";
import { hours, shortDate, useLoad, WidgetError } from "../components/useLoad";

/** How many placements the dashboard card shows. */
export const ACTIVE_LIMIT = 5;

const load = (signal?: AbortSignal) => getActivePlacements(ACTIVE_LIMIT, signal);

function progress(p: Placement): string {
  return p.required_hours ? `${hours(p.verified_hours)} of ${hours(p.required_hours)} h` : `${hours(p.verified_hours)} h`;
}

/**
 * field-training.active-placements on a coordinator's dashboard: placements under way with verified hours against the
 * requirement (GET /placements?status=active).
 */
export function ActivePlacementsWidget(_props: WidgetProps) {
  const [state, reload] = useLoad(load, "active placements");

  if (state.kind === "loading") return <SkeletonLines lines={3} />;
  if (state.kind === "error") return <WidgetError failure={state.failure} onRetry={reload} />;
  const { items, next_cursor } = state.data;
  if (items.length === 0) {
    return (
      <EmptyState icon={<Icons.Briefcase />} title="No placements under way">
        Placements appear here once they start.
      </EmptyState>
    );
  }
  return (
    <>
      <List divided label="Active placements">
        {items.map((p, i) => (
          <ListRow
            key={p.id}
            index={i}
            icon={Icons.User}
            title={p.trainee_name ?? "Trainee"}
            meta={`${[p.opening_title, p.site_name].filter(Boolean).join(" · ")} · ends ${shortDate(p.ends_on)}`}
            trailing={progress(p)}
          />
        ))}
      </List>
      {next_cursor && <p className="eos-row__meta">More placements are under way than shown here.</p>}
    </>
  );
}
