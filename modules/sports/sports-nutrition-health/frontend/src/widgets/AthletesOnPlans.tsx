import { Badge, Icons, List, ListRow, type WidgetProps } from "@eos/ui-kit";
import { listNutritionPlans, type NutritionPlan } from "../api/client";
import { athleteLabel, athletes, GOAL, plans } from "./format";
import { useWidgetData, WidgetStatus } from "./useWidgetData";

/** Active plans fetched (the contract's maximum page), and athletes listed before "and N more". */
export const FETCHED = 200;
export const SHOWN = 8;

const EMPTY = { title: "No athletes on a plan", body: "Athletes appear here once a nutrition plan for them is active." };

export interface AthletePlans {
  athleteId: string;
  plans: NutritionPlan[];
}

/** Active plans grouped by athlete, in the server's order (newest plan first). */
export function byAthlete(items: NutritionPlan[]): AthletePlans[] {
  const groups = new Map<string, NutritionPlan[]>();
  for (const p of items) groups.set(p.athlete_id, [...(groups.get(p.athlete_id) ?? []), p]);
  return [...groups.entries()].map(([athleteId, list]) => ({ athleteId, plans: list }));
}

/**
 * sports-nutrition-health.athletes-on-plans on the Nutritionist dashboard: the athletes with an active nutrition
 * plan, each with the plan's title and goal. One request: GET /nutrition-plans?status=active&limit=200. Athletes are
 * shown by short id: this module has no endpoint that names them.
 */
export function AthletesOnPlans(_props: WidgetProps) {
  const load = useWidgetData(async (signal) => {
    const page = await listNutritionPlans({ status: "active", limit: FETCHED }, signal);
    return { groups: byAthlete(page.items), total: page.total, loaded: page.items.length };
  });
  const data = load.state === "ready" ? load.data : null;
  const rest = (data?.groups.length ?? 0) - SHOWN;
  return (
    <WidgetStatus load={load} empty={data && data.total === 0 ? EMPTY : null} lines={5} icon={<Icons.Users />}>
      {data && (
        <div className="eos-snh">
          <dl className="eos-snh__summary" aria-label="Plan summary">
            <div className="eos-snh__headline">
              <dt>Athletes</dt>
              <dd>{data.groups.length}</dd>
            </div>
            <div>
              <dt>Active plans</dt>
              <dd>{data.total}</dd>
            </div>
          </dl>
          <List divided label="Athletes on plans">
            {data.groups.slice(0, SHOWN).map((g, i) => {
              const first = g.plans[0]!;
              return (
                <ListRow
                  key={g.athleteId}
                  index={i}
                  icon={Icons.User}
                  title={athleteLabel(g.athleteId)}
                  meta={g.plans.length === 1 ? first.title : `${first.title} · +${plans(g.plans.length - 1)} more`}
                  trailing={<Badge tone="accent">{GOAL[first.goal]}</Badge>}
                />
              );
            })}
          </List>
          {rest > 0 && <p className="eos-snh__muted">{`and ${athletes(rest)} more`}</p>}
          {data.total > data.loaded && (
            <p className="eos-snh__muted">{`Athletes counted from the first ${data.loaded} active plans.`}</p>
          )}
        </div>
      )}
    </WidgetStatus>
  );
}
