import { Icons, List, ListRow, type WidgetProps } from "@eos/ui-kit";
import type { ComponentType } from "react";
import { getJoiningsAndExits, type JoiningsAndExitsReport, type PersonEntry } from "../api/client";
import { dateRange, day } from "./format";
import { useWidgetData, WidgetStatus } from "./useWidgetData";

/** How many names each list shows (the report sends up to ten). */
export const SHOWN = 5;

const EMPTY = {
  title: "No joinings or exits this month",
  body: "People who join or leave, and those serving notice, appear here.",
  icon: <Icons.Users />,
};

function isEmpty(report: JoiningsAndExitsReport | null): boolean {
  if (!report) return false;
  return (
    (report.joined ?? 0) === 0 &&
    (report.exited ?? 0) === 0 &&
    (report.recent_joinings ?? []).length === 0 &&
    (report.recent_exits ?? []).length === 0 &&
    (report.upcoming_exits ?? []).length === 0
  );
}

/** One list of people: name, designation and department under it, the date on the right. */
function People({ label, people, icon, tone, datePrefix }: { label: string; people: PersonEntry[]; icon: ComponentType<{ className?: string }>; tone: "success" | "neutral" | "warning"; datePrefix: string }) {
  if (people.length === 0) return null;
  return (
    <section aria-label={label}>
      <h3 className="eos-hr__heading">{label}</h3>
      <List divided label={label}>
        {people.slice(0, SHOWN).map((p, i) => (
          <ListRow
            key={`${p.employee_id}-${p.date}`}
            index={i}
            icon={icon}
            tone={tone}
            title={p.name}
            meta={[p.designation, p.department_name].filter(Boolean).join(" · ") || undefined}
            trailing={<span className="eos-hr__date">{`${datePrefix} ${day(p.date)}`}</span>}
          />
        ))}
      </List>
    </section>
  );
}

/**
 * hr-payroll.joinings-and-exits on the HR Staff dashboard: joinings and exits from the first of this month to today
 * (the report's default range), headcount, the latest names, and those on notice by last working day
 * (GET /reports/joinings-and-exits).
 */
export function JoiningsAndExits(_props: WidgetProps) {
  const load = useWidgetData((signal) => getJoiningsAndExits(signal));
  const report = load.state === "ready" ? load.data : null;

  return (
    <WidgetStatus load={load} empty={isEmpty(report) ? EMPTY : null} lines={5}>
      {report && (
        <div className="eos-hr">
          <p className="eos-hr__muted">{dateRange(report.from, report.to)}</p>
          <dl className="eos-hr__summary">
            <div>
              <dt>Joined</dt>
              <dd className="eos-hr__count">{report.joined ?? 0}</dd>
            </div>
            <div>
              <dt>Exited</dt>
              <dd className="eos-hr__count">{report.exited ?? 0}</dd>
            </div>
            <div>
              <dt>Headcount</dt>
              <dd className="eos-hr__count">{report.headcount ?? 0}</dd>
            </div>
          </dl>
          <People label="Recent joinings" people={report.recent_joinings ?? []} icon={Icons.UserPlus} tone="success" datePrefix="Joined" />
          <People label="Recent exits" people={report.recent_exits ?? []} icon={Icons.UserX} tone="neutral" datePrefix="Left" />
          <People label="Serving notice" people={report.upcoming_exits ?? []} icon={Icons.Clock} tone="warning" datePrefix="Last day" />
        </div>
      )}
    </WidgetStatus>
  );
}
