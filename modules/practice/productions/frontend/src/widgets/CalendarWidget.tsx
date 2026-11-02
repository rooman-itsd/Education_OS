import { Badge, EmptyState, ErrorState, Icons, List, ListRow, SkeletonLines, type WidgetProps } from "@eos/ui-kit";
import {
  KIND_LABEL,
  dateTile,
  getCalendar,
  placeAndTime,
  shortDate,
  type CalendarEntry,
  type Page,
} from "../api/client";
import { useLoader } from "./useLoader";

const SHOWN = 6;

/**
 * productions.calendar on the coordinating dashboards (production manager, stage manager, exhibition manager,
 * the research and placement offices): what is on over the next weeks, soonest first, with where it is and how
 * many of the cast have confirmed (GET /calendar). The shell renders the panel and its title; this is the body.
 */
export function CalendarWidget(_props: WidgetProps) {
  const { state, reload } = useLoader<Page<CalendarEntry>>(
    (signal) => getCalendar({ limit: SHOWN }, signal),
    "the calendar",
  );

  if (state.kind === "loading") return <SkeletonLines lines={4} />;
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
      <EmptyState icon={<Icons.CalendarRange />} title="Nothing scheduled">
        Productions appear here once they have their dates.
      </EmptyState>
    );
  }

  return (
    <List divided label="What is on">
      {state.data.items.map((entry, i) => (
        <ListRow
          key={entry.id}
          index={i}
          date={dateTile(entry.starts_at)}
          icon={dateTile(entry.starts_at) ? undefined : Icons.CalendarRange}
          title={entry.title}
          meta={placeAndTime(entry) || shortDate(entry.starts_at)}
          trailing={
            <Badge tone={entry.cast_confirmed > 0 ? "success" : "neutral"}>
              {entry.cast_confirmed === 0
                ? KIND_LABEL[entry.kind]
                : `${entry.cast_confirmed} confirmed`}
            </Badge>
          }
        />
      ))}
      {state.data.total > state.data.items.length && (
        <ListRow
          title={`${state.data.total - state.data.items.length} more in this window`}
          tone="neutral"
          icon={Icons.CalendarCheck2}
        />
      )}
    </List>
  );
}
