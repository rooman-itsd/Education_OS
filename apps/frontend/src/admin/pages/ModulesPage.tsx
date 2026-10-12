import React, { useState } from 'react';
import { Link } from '../lib/router';
import { Boxes, Search, FileCode2, Power, Hammer, Plug } from '../lib/icons';
import { PageHeader, StatGrid } from '../components/ui/dashboard';
import { SUITES, PLATFORM_SERVICES, INTEGRATIONS, ALL_MODULES, ModuleInfo, ModuleStatus, moduleColor, suiteLabel } from '../data/architecture';
import { ACCESS_LABEL, moduleAccess, useEntitlementView, type Access, type EntitlementView } from '../data/entitlement';

export const STATUS_STYLE: Record<ModuleStatus, string> = {
  planned: 'bg-[#F1F5F9] text-[#475569]',
  'in-progress': 'bg-[#F39A1926] text-[#8A4F00]',
  stable: 'bg-[#16834B26] text-[#126B3D]',
  deprecated: 'bg-[#F1F5F9] text-[#64748B]'
};

export const ACCESS_STYLE: Record<Access, string> = {
  included: 'bg-[#16834B26] text-[#126B3D]',
  upgrade: 'bg-[#F39A1926] text-[#8A4F00]',
  'not-in-profile': 'bg-[#F1F5F9] text-[#64748B]',
  platform: 'bg-[#7E22CE26] text-[#7E22CE]',
  'per-organisation': 'bg-[#F1F5F9] text-[#475569]'
};

/** The entitlement as YAML-like text: what the API computes from the profile and plan. */
function entitlementText(view: EntitlementView): string {
  if (!view.entitlement || !view.profile) {
    return "# Super admin: outside every organisation.\n# Each organisation's entitlement =\n#   academy profile modules ∩ plan (∪ overrides)\n";
  }
  const on = [...view.entitlement.modules];
  const list = (xs: string[]) => (xs.length ? xs.map((x) => `\n  - ${x}`).join('') : ' []');
  return (
    `# entitlement = profile modules ∩ plan (∪ overrides)\n` +
    `academy_type: ${view.profile.profile}\nplan: ${view.entitlement.plan}\n` +
    `modules:${list(on)}\nupgrade_to_unlock:${list(view.entitlement.upgradableModules)}\n`
  );
}

/** Registry of every module in the monorepo and what this organisation's entitlement allows. */
export const ModulesPage: React.FC = () => {
  const view = useEntitlementView();
  const [query, setQuery] = useState('');
  const q = query.trim().toLowerCase();
  const match = (m: ModuleInfo) => !q || m.name.toLowerCase().includes(q) || m.id.includes(q);

  const groups = [
    ...SUITES.map((s) => ({ key: s.id, title: suiteLabel(s), path: `modules/${s.domain}/`, modules: s.modules })),
    { key: 'platform', title: 'Shared platform services', path: 'platform/', modules: PLATFORM_SERVICES },
    { key: 'integrations', title: 'External integrations', path: 'integrations/', modules: INTEGRATIONS }
  ]
    .map((g) => ({ ...g, modules: g.modules.filter(match) }))
    .filter((g) => g.modules.length);

  const features = SUITES.flatMap((s) => s.modules);
  const included = features.filter((m) => moduleAccess(m, view) === 'included').length;
  const built = ALL_MODULES.filter((m) => m.implemented);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Module Registry"
        subtitle="Every module in the monorepo. An organisation may use the modules in its academy profile and plan (its entitlement); a super admin can add overrides."
        actions={
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-[#64748B] absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search modules"
              className="h-8 pl-8 pr-3 w-56 rounded-full bg-[#F1F5F9] text-xs text-[#12233F] placeholder:text-[#475569] focus:outline-none"
            />
          </div>
        }
      />

      <StatGrid
        stats={[
          { label: 'Feature modules', icon: Boxes, value: String(features.length), note: 'Suites A–G, Practice and Global Support' },
          view.entitlement
            ? { label: 'In entitlement', icon: Power, value: String(included), delta: `of ${view.profile?.modules.filter((p) => p.includes('/')).length ?? 0}`, deltaTone: 'muted', note: `${view.profile?.profile} · ${view.planTitle} plan` }
            : { label: 'In entitlement', icon: Power, value: '–', note: 'Decided per organisation' },
          { label: 'Backend built', icon: Hammer, value: String(built.length), note: built.map((m) => m.id).join(', ') },
          { label: 'Platform & integrations', icon: Plug, value: String(PLATFORM_SERVICES.length + INTEGRATIONS.length), note: `${PLATFORM_SERVICES.length} services · ${INTEGRATIONS.length} adapters` }
        ]}
      />

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6 items-start">
        <div className="xl:col-span-8 space-y-5">
          {groups.map((g) => (
            <section key={g.key} className="bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] overflow-hidden">
              <header className="px-4 py-3 bg-[#F6F8FB] border-b border-[#E2E8F0] flex items-center justify-between gap-2">
                <h2 className="text-[13px] font-bold uppercase tracking-wide text-[#12233F]">{g.title}</h2>
                <code className="text-[10px] text-[#64748B]">{g.path}</code>
              </header>
              <ul className="divide-y divide-[#F1F5F9]">
                {g.modules.map((m) => {
                  const access = moduleAccess(m, view);
                  return (
                    <li key={m.id} className="px-4 py-3 flex items-center gap-3 hover:bg-[#F6F8FB]">
                      <span className="w-1.5 h-8 rounded-full flex-shrink-0" style={{ background: moduleColor(m) }} />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 flex-wrap">
                          <Link to={`/modules/${m.id}`} className="text-xs font-semibold text-[#12233F] hover:text-[#7E22CE]">
                            {m.name}
                          </Link>
                          <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${STATUS_STYLE[m.status]}`}>{m.status}</span>
                          {m.implemented && <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${STATUS_STYLE.stable}`}>backend built</span>}
                        </div>
                        <p className="text-[11px] text-[#475569] truncate">{m.description}</p>
                      </div>
                      <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium whitespace-nowrap ${ACCESS_STYLE[access]}`}>{ACCESS_LABEL[access]}</span>
                    </li>
                  );
                })}
              </ul>
            </section>
          ))}
          {groups.length === 0 && <p className="text-center text-xs text-[#475569] py-8">No modules match.</p>}
        </div>

        <aside className="xl:col-span-4 xl:sticky xl:top-20 bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] p-4">
          <h3 className="text-[13px] font-bold uppercase tracking-wide text-[#12233F] mb-2 flex items-center gap-1.5">
            <FileCode2 className="w-3.5 h-3.5 text-[#7E22CE]" />
            Entitlement
          </h3>
          <pre className="text-[11px] leading-relaxed text-[#334155] bg-[#FFFFFF] rounded-lg p-3 overflow-x-auto">{entitlementText(view)}</pre>
          <p className="text-[11px] text-[#64748B] mt-2">
            Computed by platform/tenancy from platform/identity/config/profiles and platform/billing/config/plans.yaml, and
            enforced per request by the entitlement gate in apps/backend. {view.source === 'preview' && 'Preview: the reference profile on the trial plan.'}
          </p>
        </aside>
      </div>
    </div>
  );
};
