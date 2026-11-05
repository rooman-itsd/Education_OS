import { Icons, List, ListRow, type WidgetProps } from "@eos/ui-kit";
import { getOpeningsSummary, type OpeningsSummaryReport } from "../api/client";
import { count, day, total } from "./format";
import { useWidgetData, WidgetStatus } from "./useWidgetData";

/** How many of the openings closing soonest the widget asks for and lists. */
export const CLOSING_LIMIT = 5;

export const SUMMARY_EMPTY = {
  title: "No openings yet",
  body: "Job openings and applications appear here once openings are posted.",
  icon: <Icons.Briefcase />,
};

function isEmpty(r: OpeningsSummaryReport | null): boolean {
  if (!r) return false;
  return total(r.openings) === 0 && total(r.applications) === 0 && (r.students_placed ?? 0) === 0 && (r.closing_soon ?? []).length === 0;
}

function Figure({ label, value }: { label: string; value: number }) {
  return (
    <div>
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

/**
 * placement-career.openings-summary on the placement staff dashboards (placement-officer, industry-coordinator,
 * practicum-coordinator, industry-liaison): open openings, applications, students placed, offers awaiting an answer
 * and drafts, and the open openings closing soonest with their application counts (GET /reports/openings-summary).
 */
export function OpeningsSummary(_props: WidgetProps) {
  const load = useWidgetData((signal) => getOpeningsSummary(CLOSING_LIMIT, signal));
  const report = load.state === "ready" ? load.data : null;
  const open = report?.openings?.open ?? 0;
  const drafts = report?.openings?.draft ?? 0;
  const offered = report?.applications?.offered ?? 0;
  const closing = report?.closing_soon ?? [];
  const moreOpen = open - closing.length;

  return (
    <WidgetStatus load={load} empty={isEmpty(report) ? SUMMARY_EMPTY : null} lines={5}>
      {report && (
        <div className="eos-placement">
          <dl className="eos-placement__summary">
            <Figure label="Open openings" value={open} />
            <Figure label="Applications" value={total(report.applications)} />
            <Figure label="Students placed" value={report.students_placed ?? 0} />
          </dl>
          {(offered > 0 || drafts > 0) && (
            <p className="eos-placement__muted">
              {[offered > 0 && `${count(offered, "offer", "offers")} awaiting an answer`, drafts > 0 && `${count(drafts, "draft opening", "draft openings")} not published`]
                .filter(Boolean)
                .join(" · ")}
            </p>
          )}
          {closing.length > 0 && (
            <section aria-label="Openings closing soonest">
              <h3 className="eos-placement__heading">Closing soonest</h3>
              <List divided label="Openings closing soonest">
                {closing.map((o, i) => (
                  <ListRow
                    key={o.id}
                    index={i}
                    icon={Icons.Briefcase}
                    title={o.title}
                    meta={
                      <span className="eos-placement__meta">
                        <span>{o.company_name}</span>
                        <span>{`Closes ${day(o.applications_close_on)}`}</span>
                      </span>
                    }
                    trailing={<strong>{count(o.applications_count ?? 0, "application", "applications")}</strong>}
                  />
                ))}
              </List>
              {moreOpen > 0 && <p className="eos-placement__muted">{`${count(moreOpen, "more open opening", "more open openings")}`}</p>}
            </section>
          )}
        </div>
      )}
    </WidgetStatus>
  );
}
