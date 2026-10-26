import { Badge, Icons, List, ListRow, type WidgetProps } from "@eos/ui-kit";
import { bySuite, getEntitlement, humanise } from "../api/client";
import { useWidgetData, WidgetStatus } from "./useWidgetData";

/**
 * tenancy.enabled-modules on the Organisation Admin dashboard: the modules the organisation can use right
 * now, grouped by suite, and how many more a higher plan would unlock (GET /organisation/entitlement). The
 * shell renders the panel and its title; this is the body.
 */
export function EnabledModules(_props: WidgetProps) {
  const load = useWidgetData((signal) => getEntitlement(signal), "the enabled modules");
  const data = load.state === "ready" ? load.data : null;
  const empty = data && data.modules.length === 0 ? { title: "No modules are on", body: "Choose an academy package or upgrade the plan to switch modules on." } : null;
  return (
    <WidgetStatus load={load} empty={empty} icon={<Icons.LayoutGrid />} lines={4}>
      {data && (
        <List divided label="Modules by suite">
          {bySuite(data.modules).map((g, i) => (
            <ListRow
              key={g.suite}
              index={i}
              icon={Icons.Layers}
              title={humanise(g.suite)}
              meta={g.modules.map(humanise).join(", ")}
              trailing={<Badge tone="success">{`${g.modules.length} on`}</Badge>}
            />
          ))}
          {data.upgradable_modules.length > 0 && (
            <ListRow
              icon={Icons.Lock}
              tone="warning"
              title={`${data.upgradable_modules.length} more on a higher plan`}
              meta={data.upgradable_modules.map((p) => humanise(p.split("/").pop() ?? p)).join(", ")}
              trailing={<Badge tone="warning">Locked</Badge>}
            />
          )}
        </List>
      )}
    </WidgetStatus>
  );
}
