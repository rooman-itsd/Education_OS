import { Badge, Icons, List, ListRow, type WidgetProps } from "@eos/ui-kit";
import { listNutritionPlans, type NutritionPlan } from "../api/client";
import { athleteLabel, day, daysUntil, due, isoDay, plans } from "./format";
import { useWidgetData, WidgetStatus } from "./useWidgetData";

/** A review due within this many days (or already overdue) is listed. */
export const DUE_WITHIN_DAYS = 7;
/** Plans fetched (the contract's maximum page), and rows listed before "and N more". */
export const FETCHED = 200;
export const SHOWN = 8;

const EMPTY = { title: "No reviews due", body: `Active plans whose review is overdue or due in the next ${DUE_WITHIN_DAYS} days appear here.` };

type DuePlan = NutritionPlan & { review_due_on: string };

/**
 * sports-nutrition-health.plan-reviews-due on the Nutritionist dashboard: active plans whose review is overdue or
 * due within DUE_WITHIN_DAYS days, the most overdue first. One request:
 * GET /nutrition-plans?status=active&review_due_before=<today + DUE_WITHIN_DAYS>&limit=200 (the server sorts by start
 * date; the widget sorts by review date).
 */
export function PlanReviewsDue(_props: WidgetProps) {
  const load = useWidgetData(async (signal) => {
    const page = await listNutritionPlans({ status: "active", review_due_before: isoDay(DUE_WITHIN_DAYS), limit: FETCHED }, signal);
    const rows = page.items
      .filter((p): p is DuePlan => !!p.review_due_on)
      .sort((a, b) => a.review_due_on.localeCompare(b.review_due_on));
    return { rows, total: page.total };
  });
  const data = load.state === "ready" ? load.data : null;
  const rows = data?.rows ?? [];
  const overdue = rows.filter((p) => daysUntil(p.review_due_on) < 0).length;
  const today = rows.filter((p) => daysUntil(p.review_due_on) === 0).length;
  const rest = (data?.total ?? 0) - Math.min(rows.length, SHOWN);
  return (
    <WidgetStatus load={load} empty={data && rows.length === 0 ? EMPTY : null} lines={5} icon={<Icons.CalendarRange />}>
      {data && (
        <div className="eos-snh">
          <dl className="eos-snh__summary" aria-label="Review summary">
            <div className="eos-snh__headline">
              <dt>Due</dt>
              <dd>{data.total}</dd>
            </div>
            <div data-warn={overdue > 0 || undefined}>
              <dt>Overdue</dt>
              <dd>{overdue}</dd>
            </div>
            <div>
              <dt>Due today</dt>
              <dd>{today}</dd>
            </div>
          </dl>
          <List divided label="Plan reviews due">
            {rows.slice(0, SHOWN).map((p, i) => {
              const d = due(p.review_due_on);
              return (
                <ListRow
                  key={p.id}
                  index={i}
                  icon={Icons.ClipboardList}
                  tone={d.overdue ? "danger" : d.tone === "warning" ? "warning" : "accent"}
                  title={p.title}
                  meta={`${athleteLabel(p.athlete_id)} · Review on ${day(p.review_due_on)}`}
                  trailing={<Badge tone={d.tone}>{d.label}</Badge>}
                />
              );
            })}
          </List>
          {rest > 0 && <p className="eos-snh__muted">{`and ${plans(rest)} more`}</p>}
        </div>
      )}
    </WidgetStatus>
  );
}
