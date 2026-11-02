import { Badge, Icons, List, ListRow, type WidgetProps } from "@eos/ui-kit";
import { getPendingLeaveRequests } from "../api/client";
import { leaveDates, leaveDays } from "./format";
import { useWidgetData, WidgetStatus } from "./useWidgetData";

/** How many of the pending requests the widget lists. */
export const SHOWN = 5;

const EMPTY = {
  title: "No leave requests pending",
  body: "Requests waiting for a decision appear here.",
  icon: <Icons.CalendarCheck2 />,
};

/**
 * hr-payroll.leave-requests on the HR Staff dashboard: how many leave requests wait for a decision, and the first
 * few in the contract's order (soonest start first) with employee, leave type, dates and days
 * (GET /leave-requests?status=pending).
 */
export function LeaveRequests(_props: WidgetProps) {
  const load = useWidgetData((signal) => getPendingLeaveRequests(signal));
  const page = load.state === "ready" ? load.data : null;
  const items = page?.items ?? [];
  const total = page ? Math.max(page.pending_total ?? 0, items.length) : 0;
  const shown = items.slice(0, SHOWN);

  return (
    <WidgetStatus load={load} empty={page && total === 0 ? EMPTY : null} lines={4}>
      {page && (
        <div className="eos-hr">
          <dl className="eos-hr__summary">
            <div>
              <dt>Pending</dt>
              <dd className="eos-hr__count">{total}</dd>
            </div>
          </dl>
          {shown.length > 0 && (
            <section aria-label="Starting soonest">
              <h3 className="eos-hr__heading">Starting soonest</h3>
              <List divided label="Pending leave requests">
                {shown.map((r, i) => (
                  <ListRow
                    key={r.id}
                    index={i}
                    icon={Icons.CalendarRange}
                    tone={r.paid === false ? "warning" : "accent"}
                    title={r.employee_name}
                    meta={
                      <span className="eos-hr__meta">
                        <span>{r.leave_type_name}</span>
                        <span>{leaveDates(r)}</span>
                      </span>
                    }
                    trailing={
                      <span className="eos-hr__trailing">
                        <strong>{leaveDays(r.days)}</strong>
                        {r.paid === false && <Badge tone="warning">Unpaid</Badge>}
                      </span>
                    }
                  />
                ))}
              </List>
            </section>
          )}
          {total > shown.length && <p className="eos-hr__muted">{`${total - shown.length} more pending`}</p>}
        </div>
      )}
    </WidgetStatus>
  );
}
