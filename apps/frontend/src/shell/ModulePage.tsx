import { Badge, Button, EmptyState, Icons, PageHero, Panel, PanelBody, ThemeScope, themeForSuite } from "@eos/ui-kit";
import { moduleLabel, SUITES } from "./navigation";
import type { Entitlement } from "../tenant/entitlements";

/**
 * A module's page in the role app. Until a module ships its own pages (frontend/src/pages), this
 * shows the module's standing in the organisation's plan, in the suite's colours.
 */
export function ModulePage({ domain, id, entitlement, canUpgrade, onUpgrade }: { domain: string; id: string; entitlement?: Entitlement; canUpgrade: boolean; onUpgrade: () => void }) {
  const suite = SUITES.find((s) => s.id === domain);
  const path = `${domain}/${id}`;
  const included = !entitlement || entitlement.modules.has(path);
  return (
    <ThemeScope theme={themeForSuite(domain)} className="eos-dashboard">
      <PageHero eyebrow={suite?.label ?? domain} title={moduleLabel(id)} subtitle={included ? "Included in your plan" : "Not in your plan"} actions={included ? undefined : canUpgrade ? <Button variant="primary" onClick={onUpgrade}>Upgrade plan</Button> : undefined} />
      <Panel lift={false}>
        <PanelBody>
          {included ? (
            <EmptyState icon={<Icons.Blocks />} title="This module's pages are not built yet">
              Its dashboard widgets appear on your home page as the team ships them. <Badge tone="accent">{path}</Badge>
            </EmptyState>
          ) : (
            <EmptyState icon={<Icons.Lock />} title="Upgrade to unlock">
              Your academy profile offers this module, but your current plan does not include it.
            </EmptyState>
          )}
        </PanelBody>
      </Panel>
    </ThemeScope>
  );
}
