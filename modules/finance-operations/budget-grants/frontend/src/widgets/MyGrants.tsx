import { Badge, Icons, List, ListRow, type WidgetProps } from "@eos/ui-kit";
import { getMyGrants, type MyGrant } from "../api/client";
import { day, daysUntil, paise, ROLE_LABEL, rupees } from "./format";
import { useWidgetData, WidgetStatus } from "./useWidgetData";

/** Reminders go out 30 days before a utilisation certificate is due (prd.md, flow 5). */
const DUE_SOON_DAYS = 30;

const EMPTY = {
  title: "No grants yet",
  body: "Grants where you are an investigator appear here once the research office records them.",
  icon: <Icons.Landmark />,
};

/** The next utilisation certificate: overdue in danger, due within 30 days in warning, otherwise nothing to flag. */
function ucState(grant: MyGrant): "overdue" | "soon" | null {
  if (!grant.next_uc_due) return null;
  const days = daysUntil(grant.next_uc_due);
  if (days < 0) return "overdue";
  return days <= DUE_SOON_DAYS ? "soon" : null;
}

/**
 * budget-grants.my-grants on the Research Scholar dashboard: each grant where the viewer is an investigator,
 * with funder, sanctioned amount, spent and balance, and the next utilisation certificate due (GET /me/grants).
 */
export function MyGrants(_props: WidgetProps) {
  const load = useWidgetData((signal) => getMyGrants(signal));
  const grants = load.state === "ready" ? load.data : null;
  return (
    <WidgetStatus load={load} empty={grants && grants.length === 0 ? EMPTY : null} lines={4}>
      {grants && (
        <div className="eos-budget">
          <List divided label="My grants">
            {grants.map((g, i) => {
              const uc = ucState(g);
              return (
                <ListRow
                  key={g.id}
                  index={i}
                  icon={uc ? Icons.FileClock : Icons.Landmark}
                  tone={uc === "overdue" ? "danger" : uc === "soon" ? "warning" : "accent"}
                  title={g.title}
                  meta={
                    <span className="eos-budget__meta">
                      <span>{`${g.funder} · ${g.code} · ${ROLE_LABEL[g.my_role] ?? g.my_role}`}</span>
                      <span>{`Sanctioned ${rupees(g.sanctioned_amount)} · Spent ${rupees(g.spent_total)}`}</span>
                      <span>{g.next_uc_due ? `Next certificate due ${day(g.next_uc_due)}` : "No certificate due"}</span>
                    </span>
                  }
                  trailing={
                    <span className="eos-budget__trailing eos-budget__trailing--stack">
                      <strong data-warn={paise(g.balance) < 0 || undefined}>{rupees(g.balance)}</strong>
                      <span className="eos-budget__muted">balance</span>
                      {uc === "overdue" && <Badge tone="danger">Certificate overdue</Badge>}
                      {uc === "soon" && <Badge tone="warning">Certificate due soon</Badge>}
                    </span>
                  }
                />
              );
            })}
          </List>
        </div>
      )}
    </WidgetStatus>
  );
}
