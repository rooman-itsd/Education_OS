import { Badge, EmptyState, Icons, List, ListRow, SkeletonLines, type BadgeTone, type WidgetProps } from "@eos/ui-kit";
import { getMyPlacements, type Placement, type PlacementStatus } from "../api/client";
import { hours, shortDate, useLoad, WidgetError } from "../components/useLoad";

/** How many placements the dashboard card shows. */
export const MY_PLACEMENT_LIMIT = 3;

const STATUS: Partial<Record<PlacementStatus, { label: string; tone: BadgeTone }>> = {
  active: { label: "Active", tone: "success" },
  assigned: { label: "Upcoming", tone: "info" },
  requested: { label: "Applied", tone: "neutral" },
};

function meta(p: Placement): string {
  const parts = [p.site_name, `${shortDate(p.starts_on)} to ${shortDate(p.ends_on)}`];
  if (p.status === "active" && p.required_hours) parts.push(`${hours(p.verified_hours)} of ${hours(p.required_hours)} h verified`);
  return parts.filter(Boolean).join(" · ");
}

/**
 * field-training.my-placement on a trainee's dashboard: the current placement, then upcoming ones and applications
 * (GET /me/placements). The shell renders the panel and its title (the academy's word for a placement); this is the body.
 */
export function MyPlacementWidget(_props: WidgetProps) {
  const [state, reload] = useLoad(getMyPlacements, "your placements");

  if (state.kind === "loading") return <SkeletonLines lines={3} />;
  if (state.kind === "error") return <WidgetError failure={state.failure} onRetry={reload} />;
  const rows = state.data.slice(0, MY_PLACEMENT_LIMIT);
  if (rows.length === 0) {
    return (
      <EmptyState icon={<Icons.Briefcase />} title="No placement yet">
        When you are placed or apply for an opening, it appears here.
      </EmptyState>
    );
  }
  return (
    <List divided label="Your placements">
      {rows.map((p, i) => {
        const status = STATUS[p.status] ?? { label: p.status, tone: "neutral" as BadgeTone };
        return (
          <ListRow
            key={p.id}
            index={i}
            date={p.starts_on}
            title={p.opening_title ?? "Placement"}
            meta={meta(p)}
            tone={p.status === "active" ? "success" : "accent"}
            trailing={<Badge tone={status.tone}>{status.label}</Badge>}
          />
        );
      })}
    </List>
  );
}
