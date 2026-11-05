import { Icons, List, ListRow, type WidgetProps } from "@eos/ui-kit";
import { getDrivesUpcoming, type UpcomingDrive } from "../api/client";
import { count, day, total } from "./format";
import { useWidgetData, WidgetStatus } from "./useWidgetData";

/** How many upcoming drives the widget asks for and lists. */
export const DRIVES_LIMIT = 5;

export const DRIVES_EMPTY = {
  title: "No drives scheduled",
  body: "Scheduled campus drives appear here.",
  icon: <Icons.CalendarRange />,
};

function DriveRow({ drive, index }: { drive: UpcomingDrive; index: number }) {
  const where = [drive.company?.name, drive.venue].filter(Boolean).join(", ");
  return (
    <ListRow
      index={index}
      date={drive.scheduled_on}
      title={drive.title}
      meta={
        <span className="eos-placement__meta">
          {where && <span>{where}</span>}
          <span>{day(drive.scheduled_on)}</span>
          {drive.registration_closes_on && <span>{`Registration closes ${day(drive.registration_closes_on)}`}</span>}
        </span>
      }
      trailing={
        <span className="eos-placement__trailing">
          <strong>{count(drive.openings_count ?? 0, "opening", "openings")}</strong>
          <span>{count(total(drive.applications), "application", "applications")}</span>
        </span>
      }
    />
  );
}

/**
 * placement-career.drives on the Placement Officer dashboard: how many campus drives are scheduled in the next 30 days,
 * and the soonest ones with company, venue, registration closing date, openings and applications
 * (GET /reports/drives-upcoming).
 */
export function Drives(_props: WidgetProps) {
  const load = useWidgetData((signal) => getDrivesUpcoming(DRIVES_LIMIT, signal));
  const report = load.state === "ready" ? load.data : null;
  const drives = report?.drives ?? [];
  const next30 = report?.next_30_days ?? 0;
  // The drives are the soonest first, so when more than the listed ones fall in the next 30 days, every listed one does.
  const more = next30 - drives.length;

  return (
    <WidgetStatus load={load} empty={report && drives.length === 0 && next30 === 0 ? DRIVES_EMPTY : null} lines={4}>
      {report && (
        <div className="eos-placement">
          <dl className="eos-placement__summary">
            <div>
              <dt>Next 30 days</dt>
              <dd>{next30}</dd>
            </div>
          </dl>
          {drives.length > 0 && (
            <section aria-label="Drives coming up">
              <h3 className="eos-placement__heading">Coming up</h3>
              <List divided label="Upcoming drives">
                {drives.map((d, i) => (
                  <DriveRow key={d.id} drive={d} index={i} />
                ))}
              </List>
              {more > 0 && <p className="eos-placement__muted">{`${count(more, "more drive", "more drives")} in the next 30 days`}</p>}
            </section>
          )}
        </div>
      )}
    </WidgetStatus>
  );
}
