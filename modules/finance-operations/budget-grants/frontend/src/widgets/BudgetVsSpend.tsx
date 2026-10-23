import { Badge, Icons, ProgressBar, type WidgetProps } from "@eos/ui-kit";
import { getBudgetVsSpend, type BudgetVsSpendReport, type BudgetVsSpendScope } from "../api/client";
import { level, levelLabel, paise, rupees, rupeesFromPaise, usedPercent, type Level } from "./format";
import { useWidgetData, WidgetStatus } from "./useWidgetData";

/** How many budget heads the widget lists, closest to their limit first, before "and N more". */
const TOP_HEADS = 5;

const TONE: Record<Level, "neutral" | "warning" | "danger"> = { ok: "neutral", warning: "warning", danger: "danger" };

/** The research office watches grant spend (prd.md, Users); everyone else sees budgets and grants together. */
function scopeFor(role: string): BudgetVsSpendScope | undefined {
  return role === "research-office" ? "grants" : undefined;
}

/** Percent used with a warning badge from 80% and a danger badge from 100%. */
function Used({ used, allocated }: { used: number; allocated: number }) {
  const pct = usedPercent(used, allocated);
  const lvl = level(used, allocated);
  const label = levelLabel(lvl, used, allocated);
  return (
    <span className="eos-budget__trailing">
      <span>{pct === null ? "—" : `${pct}% used`}</span>
      {label && <Badge tone={TONE[lvl]}>{label}</Badge>}
    </span>
  );
}

/** Used share of a head for ordering: committed plus spent over allocated; anything spent on nothing allocated first. */
function share(used: number, allocated: number): number {
  if (allocated > 0) return used / allocated;
  return used > 0 ? Infinity : 0;
}

function isEmpty(report: BudgetVsSpendReport | null): boolean {
  if (!report) return false;
  const nothing = paise(report.allocated) === 0 && paise(report.committed) === 0 && paise(report.spent) === 0;
  return nothing && report.by_head.length === 0 && (report.grants?.active ?? 0) === 0;
}

/**
 * budget-grants.budget-vs-spend on the Finance Staff and Research Office dashboards: allocated, committed,
 * spent and available for the financial year, the share used with its 80% and 100% thresholds, the budget
 * heads closest to their limit and the grant totals (GET /reports/budget-vs-spend; scope=grants for the
 * research office).
 */
export function BudgetVsSpend({ role }: WidgetProps) {
  const scope = scopeFor(role);
  const load = useWidgetData((signal) => getBudgetVsSpend({ scope }, signal));
  const report = load.state === "ready" ? load.data : null;
  const year = report?.financial_year || "this financial year";
  const empty = isEmpty(report)
    ? scope === "grants"
      ? { title: "No grants to show", body: `Grant lines and spend appear here once grants are recorded for ${year}.`, icon: <Icons.Landmark /> }
      : { title: "No budget allocated", body: `Allocations and spend appear here once a budget is set for ${year}.` }
    : null;

  const allocated = report ? paise(report.allocated) : 0;
  const used = report ? paise(report.committed) + paise(report.spent) : 0;
  const available = allocated - used;
  const pct = usedPercent(used, allocated);
  const heads = report
    ? report.by_head
        .map((h) => ({ ...h, used: paise(h.committed) + paise(h.spent), alloc: paise(h.allocated) }))
        .sort((a, b) => share(b.used, b.alloc) - share(a.used, a.alloc))
    : [];
  const rest = heads.length - TOP_HEADS;
  const grants = report?.grants;

  return (
    <WidgetStatus load={load} empty={empty} lines={5}>
      {report && (
        <div className="eos-budget">
          <dl className="eos-budget__summary">
            <div className="eos-budget__headline">
              <dt>Allocated</dt>
              <dd>{rupees(report.allocated)}</dd>
            </div>
            <div>
              <dt>Committed</dt>
              <dd>{rupees(report.committed)}</dd>
            </div>
            <div>
              <dt>Spent</dt>
              <dd>{rupees(report.spent)}</dd>
            </div>
            <div data-warn={available < 0 || undefined}>
              <dt>Available</dt>
              <dd>{rupeesFromPaise(available)}</dd>
            </div>
          </dl>
          <div className="eos-budget__overall">
            <ProgressBar value={pct ?? (used > 0 ? 100 : 0)} label={`Committed and spent against allocated, ${year}`} />
            <Used used={used} allocated={allocated} />
          </div>
          {heads.length > 0 && (
            <section aria-label="Budget heads">
              <h3 className="eos-budget__heading">Heads closest to their limit</h3>
              <ul className="eos-budget__bars">
                {heads.slice(0, TOP_HEADS).map((h) => {
                  const hp = usedPercent(h.used, h.alloc);
                  return (
                    <li key={h.budget_head_id}>
                      <span className="eos-budget__bar-head">
                        <span>{h.name}</span>
                        <span>
                          <strong>{rupeesFromPaise(h.used)}</strong>
                          {` of ${rupees(h.allocated)}`}
                        </span>
                      </span>
                      <span className="eos-budget__bar-row" data-level={level(h.used, h.alloc)}>
                        <ProgressBar value={hp ?? (h.used > 0 ? 100 : 0)} label={`${h.name} committed and spent against allocated`} />
                        <Used used={h.used} allocated={h.alloc} />
                      </span>
                    </li>
                  );
                })}
              </ul>
              {rest > 0 && <p className="eos-budget__muted">{rest === 1 ? "and 1 more head" : `and ${rest} more heads`}</p>}
            </section>
          )}
          {grants && grants.active > 0 && (
            <section aria-label="Grants">
              <h3 className="eos-budget__heading">Grants</h3>
              <dl className="eos-budget__summary">
                <div>
                  <dt>Active grants</dt>
                  <dd>{grants.active}</dd>
                </div>
                <div>
                  <dt>Sanctioned</dt>
                  <dd>{rupees(grants.sanctioned)}</dd>
                </div>
                <div>
                  <dt>Spent</dt>
                  <dd>{rupees(grants.spent)}</dd>
                </div>
                <div>
                  <dt>Certificates due in 30 days</dt>
                  <dd>{grants.ucs_due_30_days > 0 ? <Badge tone="warning">{`${grants.ucs_due_30_days} due`}</Badge> : "None"}</dd>
                </div>
              </dl>
            </section>
          )}
          <p className="eos-budget__muted">{`Financial year ${year}`}</p>
        </div>
      )}
    </WidgetStatus>
  );
}
