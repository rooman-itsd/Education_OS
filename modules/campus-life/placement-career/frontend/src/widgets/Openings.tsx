import { Badge, Icons, List, ListRow, type BadgeTone, type WidgetProps } from "@eos/ui-kit";
import { getMyOpenings, type ApplicationStatus, type MyOpening } from "../api/client";
import { day, rupees, STATUS_LABEL } from "./format";
import { useWidgetData, WidgetStatus } from "./useWidgetData";

/** How many openings the widget asks for and lists (the first page of GET /me/openings). */
export const OPENINGS_LIMIT = 5;

export const OPENINGS_EMPTY = {
  title: "No openings right now",
  body: "Job openings you can apply to appear here.",
  icon: <Icons.Briefcase />,
};

/** Badge tone of the caller's own application. */
const STATUS_TONE: Record<ApplicationStatus, BadgeTone> = {
  applied: "info",
  shortlisted: "info",
  in_process: "info",
  offered: "success",
  accepted: "success",
  declined: "neutral",
  rejected: "neutral",
  withdrawn: "neutral",
};

function OpeningRow({ opening, index }: { opening: MyOpening; index: number }) {
  const ctc = rupees(opening.ctc_per_annum);
  const status = opening.my_application?.status;
  const where = [opening.company?.name, opening.location].filter(Boolean).join(", ");
  return (
    <ListRow
      index={index}
      icon={Icons.Briefcase}
      tone={status ? "info" : "accent"}
      title={opening.title}
      meta={
        <span className="eos-placement__meta">
          {where && <span>{where}</span>}
          {ctc && <span>{`CTC ${ctc} a year`}</span>}
          {opening.drive && <span>{`Campus drive on ${day(opening.drive.scheduled_on)}`}</span>}
          <span>{`Apply by ${day(opening.applications_close_on)}`}</span>
        </span>
      }
      trailing={status && <Badge tone={STATUS_TONE[status] ?? "neutral"}>{STATUS_LABEL[status] ?? status}</Badge>}
    />
  );
}

/**
 * placement-career.openings on the learner dashboards: job openings the student can still apply to, soonest closing
 * first, with company, CTC, campus drive date, the last day to apply and the student's own application status
 * (GET /me/openings, first page).
 */
export function Openings(_props: WidgetProps) {
  const load = useWidgetData((signal) => getMyOpenings(OPENINGS_LIMIT, signal));
  const page = load.state === "ready" ? load.data : null;
  const items = page?.items ?? [];
  const more = Boolean(page?.next_cursor);

  return (
    <WidgetStatus load={load} empty={page && items.length === 0 ? OPENINGS_EMPTY : null} lines={4}>
      {page && (
        <section className="eos-placement" aria-label="Openings closing soonest">
          <List divided label="Job openings">
            {items.map((o, i) => (
              <OpeningRow key={o.id} opening={o} index={i} />
            ))}
          </List>
          {more && <p className="eos-placement__muted">{`Showing the ${items.length} closing soonest; more are open.`}</p>}
        </section>
      )}
    </WidgetStatus>
  );
}
