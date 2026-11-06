import { Badge, EmptyState, Icons, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import { getOpenOpenings } from "../api/client";
import { shortDate, useLoad, WidgetError } from "../components/useLoad";

/** How many openings the dashboard card shows. */
export const OPENINGS_LIMIT = 5;

const load = (signal?: AbortSignal) => getOpenOpenings(OPENINGS_LIMIT, signal);

/**
 * field-training.placements-open on coordinator and supervisor dashboards: open openings with seats left, soonest
 * first (GET /openings?status=open&has_seats=true).
 */
export function PlacementsOpenWidget(_props: WidgetProps) {
  const [state, reload] = useLoad(load, "open placements");

  if (state.kind === "loading") return <SkeletonLines lines={3} />;
  if (state.kind === "error") return <WidgetError failure={state.failure} onRetry={reload} />;
  const { items, next_cursor } = state.data;
  if (items.length === 0) {
    return (
      <EmptyState icon={<Icons.Building />} title="No open placements with seats">
        Published openings with seats left appear here.
      </EmptyState>
    );
  }
  return (
    <>
      <List divided label="Open placements">
        {items.map((o, i) => {
          const left = Math.max(o.seats - o.seats_filled, 0);
          return (
            <ListRow
              key={o.id}
              index={i}
              date={o.starts_on}
              title={o.title}
              meta={[o.site_name, o.discipline, `until ${shortDate(o.ends_on)}`].filter(Boolean).join(" · ")}
              trailing={<Badge tone="success">{left === 1 ? "1 seat left" : `${left} seats left`}</Badge>}
            />
          );
        })}
      </List>
      {next_cursor && <p className="eos-row__meta">More openings are open than shown here.</p>}
    </>
  );
}
