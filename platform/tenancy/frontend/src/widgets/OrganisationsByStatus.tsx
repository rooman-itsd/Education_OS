import { Badge, Icons, List, ListRow, type WidgetProps } from "@eos/ui-kit";
import { countByStatus, listOrganisations, statusInfo } from "../api/client";
import { useWidgetData, WidgetStatus } from "./useWidgetData";

/**
 * tenancy.organisations-by-status on the Super Admin dashboard: how many organisations are in each status, every
 * status listed (zero included) so a missing one is never mistaken for none, from GET /admin/organisations.
 */
export function OrganisationsByStatus(_props: WidgetProps) {
  const load = useWidgetData((signal) => listOrganisations(signal), "the organisations");
  const orgs = load.state === "ready" ? load.data : null;
  const empty = orgs && orgs.length === 0 ? { title: "No organisations yet", body: "Registrations appear here once an organisation signs up." } : null;
  return (
    <WidgetStatus load={load} empty={empty} icon={<Icons.Building2 />} lines={5}>
      {orgs && (
        <>
          <p className="eos-tenancy__muted">{`${orgs.length} ${orgs.length === 1 ? "organisation" : "organisations"} in all`}</p>
          <List divided label="Organisations by status">
            {countByStatus(orgs).map(({ status, count }, i) => {
              const info = statusInfo(status);
              return (
                <ListRow
                  key={status}
                  index={i}
                  icon={Icons.Building2}
                  tone={count === 0 ? "neutral" : info.tone}
                  title={info.label}
                  trailing={<Badge tone={count === 0 ? "neutral" : info.tone}>{String(count)}</Badge>}
                />
              );
            })}
          </List>
        </>
      )}
    </WidgetStatus>
  );
}
