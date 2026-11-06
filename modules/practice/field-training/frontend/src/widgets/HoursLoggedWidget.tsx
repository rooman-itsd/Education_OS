import { EmptyState, Icons, ProgressBar, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import { getMyHours } from "../api/client";
import { hours, useLoad, WidgetError } from "../components/useLoad";

/**
 * field-training.hours-logged on a trainee's dashboard: verified hours against the requirement of the active or most
 * recent placement, and what still waits for the supervisor (GET /me/hours). Only verified hours count.
 */
export function HoursLoggedWidget(_props: WidgetProps) {
  const [state, reload] = useLoad(getMyHours, "your hours");

  if (state.kind === "loading") return <SkeletonLines lines={3} />;
  if (state.kind === "error") return <WidgetError failure={state.failure} onRetry={reload} />;
  const h = state.data;
  if (h.placement_id === null) {
    return (
      <EmptyState icon={<Icons.Clock />} title="No hours to show yet">
        Hours you log during a placement appear here once it starts.
      </EmptyState>
    );
  }
  const pct = h.required_hours > 0 ? (h.verified_hours / h.required_hours) * 100 : 0;
  const last14 = h.by_date.reduce((sum, d) => sum + d.verified_hours + d.pending_hours, 0);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <div>
        <b style={{ fontSize: "1.5rem" }}>{hours(h.verified_hours)}</b>
        {h.required_hours > 0 ? ` of ${hours(h.required_hours)} hours verified` : " hours verified"}
      </div>
      {h.required_hours > 0 && <ProgressBar value={pct} label="Verified hours against the requirement" />}
      <ul aria-label="Hours by status" style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 4 }}>
        <li>Awaiting verification: {hours(h.pending_hours)} h</li>
        {h.returned_hours > 0 && <li>Returned for correction: {hours(h.returned_hours)} h</li>}
        <li>Logged in the last 14 days: {hours(last14)} h</li>
      </ul>
    </div>
  );
}
