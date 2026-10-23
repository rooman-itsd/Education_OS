import { ProgressBar, type WidgetProps } from "@eos/ui-kit";
import { getEntitlement, listUsers } from "../api/client";
import { useWidgetData, WidgetStatus } from "./useWidgetData";

/** Share of a limit used, 0..100; a zero or missing limit is "no limit". */
export function share(used: number, limit: number | undefined): number | null {
  if (!limit || limit <= 0) return null;
  return Math.min(100, Math.round((used / limit) * 100));
}

/**
 * billing.usage-vs-limits on the Organisation Admin dashboard: users against the plan's user limit and
 * modules switched on against what the academy profile offers (GET /tenancy/organisation/entitlement and
 * GET /identity/users). The shell renders the panel and its title; this is the body.
 */
export function UsageVsLimits(_props: WidgetProps) {
  const load = useWidgetData(
    async (signal) => {
      const [entitlement, users] = await Promise.all([getEntitlement(signal), listUsers(signal)]);
      return { entitlement, users };
    },
    "usage",
  );
  const data = load.state === "ready" ? load.data : null;
  return (
    <WidgetStatus load={load} empty={null} lines={4}>
      {data && (
        <ul className="eos-billing__usage">
          <Row label="Users" used={data.users.filter((u) => u.status === "active").length} limit={data.entitlement.limits.users} unit="users" />
          <Row
            label="Modules on"
            used={data.entitlement.modules.length}
            limit={data.entitlement.modules.length + data.entitlement.upgradable_modules.length}
            unit="modules"
            note={data.entitlement.upgradable_modules.length > 0 ? `${data.entitlement.upgradable_modules.length} more on a higher plan` : undefined}
          />
          <Row label="Students" used={0} limit={data.entitlement.limits.students} unit="students" note="counted once student records ship" />
        </ul>
      )}
    </WidgetStatus>
  );
}

function Row({ label, used, limit, unit, note }: { label: string; used: number; limit: number | undefined; unit: string; note?: string }) {
  const pct = share(used, limit);
  const full = pct !== null && pct >= 100;
  return (
    <li className="eos-billing__usage-row" data-full={full || undefined}>
      <div className="eos-billing__usage-text">
        <span>{label}</span>
        <strong>{limit ? `${used.toLocaleString("en-IN")} of ${limit.toLocaleString("en-IN")} ${unit}` : `${used.toLocaleString("en-IN")} ${unit}`}</strong>
      </div>
      {pct !== null && <ProgressBar value={pct} label={`${label} used`} />}
      {(note || full) && <span className="eos-billing__muted">{full ? "At the plan limit" : note}</span>}
    </li>
  );
}
