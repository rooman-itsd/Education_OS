import { Badge, Icons, List, ListRow, type WidgetProps } from "@eos/ui-kit";
import { listNutritionPlans } from "../api/client";
import { day, due, GOAL, targets } from "./format";
import { useWidgetData, WidgetStatus } from "./useWidgetData";

/** Active plans fetched; an athlete normally has one. */
export const SHOWN = 5;

const EMPTY = { title: "No active nutrition plan", body: "Your nutrition plan appears here once your nutritionist makes it active." };

/**
 * sports-nutrition-health.nutrition-plan on the Athlete dashboard: the signed-in athlete's active plan(s), their daily
 * targets and period, and when the next review is due. One request: GET /nutrition-plans?status=active, which the
 * service narrows to the caller's own plans for an athlete.
 */
export function NutritionPlan(_props: WidgetProps) {
  const load = useWidgetData((signal) => listNutritionPlans({ status: "active", limit: SHOWN }, signal));
  const data = load.state === "ready" ? load.data : null;
  const plans = data?.items ?? [];
  const next = plans
    .map((p) => p.review_due_on)
    .filter((d): d is string => !!d)
    .sort()[0];
  const nextDue = next ? due(next) : null;
  return (
    <WidgetStatus load={load} empty={data && plans.length === 0 ? EMPTY : null} lines={4} icon={<Icons.Apple />}>
      {data && (
        <section className="eos-snh" aria-label="Your nutrition plan">
          <dl className="eos-snh__summary" aria-label="Next review">
            <div className="eos-snh__headline" data-warn={nextDue?.overdue || undefined}>
              <dt>Next review</dt>
              <dd>{next ? day(next) : "Not set"}</dd>
            </div>
            {nextDue && (
              <div>
                <dt>Status</dt>
                <dd>
                  <Badge tone={nextDue.tone}>{nextDue.label}</Badge>
                </dd>
              </div>
            )}
          </dl>
          <List divided label="Your active plans">
            {plans.map((p, i) => {
              const goals = targets(p);
              const meals = p.meals?.length ?? 0;
              return (
                <ListRow
                  key={p.id}
                  index={i}
                  icon={Icons.Apple}
                  title={p.title}
                  meta={[
                    goals || "No daily targets set",
                    p.end_date ? `${day(p.start_date)} to ${day(p.end_date)}` : `From ${day(p.start_date)}`,
                    meals > 0 ? (meals === 1 ? "1 meal" : `${meals} meals`) : "",
                  ]
                    .filter(Boolean)
                    .join(" · ")}
                  trailing={<Badge tone="accent">{GOAL[p.goal]}</Badge>}
                />
              );
            })}
          </List>
          {data.total > plans.length && <p className="eos-snh__muted">{`and ${data.total - plans.length} more`}</p>}
        </section>
      )}
    </WidgetStatus>
  );
}
