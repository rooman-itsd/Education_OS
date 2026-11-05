import { EmptyState, ErrorState, Icons, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import {
  KIND_LABEL,
  dateTile,
  getUpcoming,
  placeAndTime,
  shortDate,
  type CalendarEntry,
  type Page,
} from "../api/client";
import { useLoader } from "./useLoader";

const SHOWN = 5;

/**
 * productions.upcoming on the learner, performer and management dashboards: the next productions of the
 * organisation, soonest first, so a student or a visiting manager can see what is coming
 * (GET /upcoming). Unlike the calendar it has no window and shows no cast figures.
 */
export function UpcomingWidget(_props: WidgetProps) {
  const { state, reload } = useLoader<Page<CalendarEntry>>(
    (signal) => getUpcoming({ limit: SHOWN }, signal),
    "what is coming up",
  );

  if (state.kind === "loading") return <SkeletonLines lines={3} />;
  if (state.kind === "error") {
    const { title, detail, retry } = state.failure;
    return (
      <ErrorState title={title} onRetry={retry ? reload : undefined}>
        {detail}
      </ErrorState>
    );
  }
  if (state.data.items.length === 0) {
    return (
      <EmptyState icon={<Icons.Presentation />} title="Nothing coming up">
        Performances, exhibitions and competitions appear here once they are scheduled.
      </EmptyState>
    );
  }

  return (
    <List divided label="Coming up">
      {state.data.items.map((entry, i) => (
        <ListRow
          key={entry.id}
          index={i}
          date={dateTile(entry.starts_at)}
          icon={dateTile(entry.starts_at) ? undefined : Icons.Presentation}
          title={entry.title}
          meta={[KIND_LABEL[entry.kind], placeAndTime(entry) || shortDate(entry.starts_at)]
            .filter(Boolean)
            .join(" · ")}
        />
      ))}
      {state.data.total > state.data.items.length && (
        <ListRow
          title={`${state.data.total - state.data.items.length} more`}
          tone="neutral"
          icon={Icons.CalendarRange}
        />
      )}
    </List>
  );
}
