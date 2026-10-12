import React from 'react';
import { Link } from '../lib/router';
import { Shield, KeyRound, Building2, Check, X, LayoutGrid, Blocks } from '../lib/icons';
import { PageHeader, StatGrid, PANEL, PanelHeader } from '../components/ui/dashboard';
import { useAuth } from '../lib/auth';
import { useEntitlementView, moduleAccess, ACCESS_LABEL, type Access } from '../data/entitlement';
import { LAYOUTS, MODULE_PERMISSIONS, academyLabel, permissionsFor } from '../data/repo';
import { roleTitle, resolveWidgetIds } from '../data/roles';
import { SUITES, suiteLabel } from '../data/architecture';
import { MODULE_WIDGETS } from '../data/widgets';
import { ENDPOINTS, allows, requirementLabel } from '../data/apiAccess';
import { ACCESS_STYLE } from './ModulesPage';

const KEY_DESCRIPTIONS = new Map(Object.values(MODULE_PERMISSIONS).flatMap((defs) => defs.map((d) => [d.key, d.description ?? ''] as const)));

const METHOD_STYLE: Record<string, string> = {
  GET: 'bg-[#EEEEFD] text-[#4338CA]',
  POST: 'bg-[#E7F4EC] text-[#126B3D]',
  PUT: 'bg-[#FEF3E2] text-[#8A4F00]',
  PATCH: 'bg-[#FEF3E2] text-[#8A4F00]',
  DELETE: 'bg-[#FEF2F2] text-[#B91C1C]'
};

/**
 * The signed-in admin's role and what it allows: permission keys (granted by role in
 * contracts/permissions.yaml), the API actions those keys unlock (read from the platform routers),
 * the organisation's module access (its entitlement) and the role's dashboard layout.
 */
export const AccessPage: React.FC = () => {
  const { session } = useAuth();
  const view = useEntitlementView();

  const sample = !session;
  const me = session?.me ?? {
    name: 'Administrator',
    email: 'admin@example.org',
    roles: ['org-admin'],
    is_super_admin: false,
    permissions: permissionsFor(['org-admin']),
    organisation_id: 'preview'
  };
  const roleId = me.is_super_admin ? 'super-admin' : me.roles[0] ?? 'org-admin';
  const caller = { permissions: me.permissions, organisationId: me.organisation_id };
  const scope = me.is_super_admin
    ? 'Platform-wide: every organisation, plan and subscription. Outside every organisation.'
    : `One organisation: ${session?.organisation?.name ?? 'the demo organisation'}${view.profile ? ` (${academyLabel(view.profile)})` : ''}.`;

  const endpoints = ENDPOINTS.filter((e) => e.requires.kind !== 'public');
  const allowed = endpoints.filter((e) => allows(e, caller));
  const services = [...new Set(endpoints.map((e) => e.service))];

  // Keys the platform defines but this role does not hold.
  const allKeys = [...new Set(Object.values(MODULE_PERMISSIONS).flatMap((d) => d.map((x) => x.key)))]
    .filter((k) => k.startsWith('platform:') || k.startsWith('tenancy:') || k.startsWith('billing:'))
    .sort();
  const held = new Set(me.permissions);

  // Module access per suite (organisation admins: the entitlement).
  const access: Access[] = ['included', 'upgrade', 'not-in-profile'];
  const suiteRows = SUITES.map((s) => ({
    suite: s,
    counts: access.map((a) => s.modules.filter((m) => moduleAccess(m, view) === a).length)
  }));

  const layout = LAYOUTS[roleId];
  const widgets = layout ? resolveWidgetIds(roleId) : [];
  const built = new Set(Object.values(MODULE_WIDGETS).flat().map((w) => w.id));

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={
          <span className="inline-flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-white" />
            {me.name || me.email}
          </span>
        }
        title="Role & Access"
        subtitle={
          <>
            {roleTitle(roleId)} · {scope}
            {sample && <span className="block text-xs mt-0.5">Preview: sample organisation admin, no API connected</span>}
          </>
        }
      />

      <StatGrid
        stats={[
          { label: 'Role', icon: Shield, value: me.is_super_admin ? 'Super Admin' : roleTitle(roleId), note: roleId },
          { label: 'Scope', icon: Building2, value: me.is_super_admin ? 'Platform' : 'Organisation', note: me.is_super_admin ? 'All organisations' : session?.organisation?.name ?? 'Demo' },
          { label: 'Permission keys', icon: KeyRound, value: String(me.permissions.length), note: `of ${allKeys.length} platform keys` },
          { label: 'API actions allowed', icon: Blocks, value: String(allowed.length), delta: `of ${endpoints.length}`, deltaTone: 'muted', note: 'identity, tenancy, billing' }
        ]}
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <section className={PANEL}>
          <PanelHeader title="Permission keys" subtitle="Granted to your role in contracts/permissions.yaml" />
          <ul className="divide-y divide-[#F1F5F9] border-t border-[#F1F5F9]">
            {allKeys.map((k) => {
              const has = held.has(k);
              return (
                <li key={k} className="px-5 py-2.5 flex items-start gap-3 text-[11px]">
                  <span
                    className={`mt-0.5 w-5 h-5 rounded-md flex items-center justify-center flex-shrink-0 ${has ? 'bg-[#16834B26] text-[#126B3D]' : 'bg-[#F1F5F9] text-[#64748B]'}`}
                    aria-label={has ? 'granted' : 'not granted'}
                  >
                    {has ? <Check className="w-3.5 h-3.5" /> : <X className="w-3.5 h-3.5" />}
                  </span>
                  <div className="min-w-0">
                    <code className={has ? 'text-[#12233F]' : 'text-[#64748B]'}>{k}</code>
                    <p className="text-[#64748B]">{KEY_DESCRIPTIONS.get(k)}</p>
                  </div>
                </li>
              );
            })}
          </ul>
        </section>

        <section className={PANEL}>
          <PanelHeader
            title="Module access"
            subtitle={view.entitlement ? `${view.profile ? academyLabel(view.profile) : ''} · ${view.planTitle} plan` : 'Decided per organisation by profile and plan'}
            action={
              <Link to="/modules" className="text-xs font-medium text-[var(--accent)] hover:underline pt-0.5">
                Module Registry
              </Link>
            }
          />
          {view.entitlement ? (
            <table className="w-full text-xs border-t border-[#F1F5F9]">
              <thead>
                <tr className="text-[#475569]">
                  <th className="py-2 px-5 text-left font-semibold">Suite</th>
                  {access.map((a) => (
                    <th key={a} className="py-2 px-2 text-center font-semibold">
                      <span className={`inline-flex text-[10px] px-1.5 py-0.5 rounded font-medium whitespace-nowrap ${ACCESS_STYLE[a]}`}>{ACCESS_LABEL[a]}</span>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-[#F1F5F9]">
                {suiteRows.map(({ suite, counts }) => (
                  <tr key={suite.id}>
                    <td className="py-2 px-5 text-[#12233F]">{suiteLabel(suite)}</td>
                    {counts.map((n, i) => (
                      <td key={i} className={`py-2 px-2 text-center tabular-nums ${n ? 'text-[#12233F] font-semibold' : 'text-[#94A3B8]'}`}>{n}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="px-5 py-4 text-xs text-[#475569] border-t border-[#F1F5F9]">
              A super admin is outside every organisation. Each organisation's modules are its academy profile ∩ plan, plus any
              overrides you grant with <code>platform:entitlements:manage</code>.
            </p>
          )}
        </section>
      </div>

      <section className={PANEL}>
        <PanelHeader title="API actions" subtitle="Every platform endpoint and whether your role may call it, read from the backend routers" />
        <div className="divide-y divide-[#F1F5F9] border-t border-[#F1F5F9]">
          {services.map((svc) => (
            <div key={svc} className="px-5 py-3 space-y-1.5">
              <div className="text-[11px] font-bold uppercase tracking-wider text-[#475569]">{svc}</div>
              {endpoints
                .filter((e) => e.service === svc)
                .map((e) => {
                  const ok = allows(e, caller);
                  return (
                    <div key={e.method + e.path} className="flex items-center gap-3 text-[11px]">
                      <span className={`w-12 text-center text-[10px] font-semibold px-1.5 py-0.5 rounded ${METHOD_STYLE[e.method] ?? ''}`}>{e.method}</span>
                      <code className={`truncate ${ok ? 'text-[#12233F]' : 'text-[#94A3B8]'}`}>{e.path}</code>
                      <span className="hidden md:block flex-1 truncate text-[#64748B]">{e.summary}</span>
                      <code className="hidden sm:block text-[10px] text-[#64748B] whitespace-nowrap">{requirementLabel(e.requires)}</code>
                      <span
                        className={`text-[10px] font-medium px-2 py-0.5 rounded-full whitespace-nowrap ${ok ? 'bg-[#16834B26] text-[#126B3D]' : 'bg-[#F1F5F9] text-[#64748B]'}`}
                      >
                        {ok ? 'Allowed' : 'Not allowed'}
                      </span>
                    </div>
                  );
                })}
            </div>
          ))}
        </div>
      </section>

      <section className={PANEL}>
        <PanelHeader
          title="Your dashboard layout"
          subtitle={layout ? `platform/identity/config/dashboards/${roleId}.yaml` : 'No layout for this role'}
          action={
            layout && (
              <Link to={`/dashboards?role=${roleId}`} className="text-xs font-medium text-[var(--accent)] hover:underline pt-0.5">
                Preview
              </Link>
            )
          }
        />
        <div className="px-5 pb-4 flex flex-wrap gap-1.5">
          {widgets.map((w) => (
            <span key={w} className="inline-flex items-center gap-1.5 text-[10px] font-mono px-2 py-1 rounded bg-[#F6F8FB] border border-[#E2E8F0] text-[#334155]">
              <LayoutGrid className="w-3 h-3 text-[#64748B]" />
              {w}
              <span className={built.has(w) ? 'text-[#126B3D]' : 'text-[#94A3B8]'}>{built.has(w) ? 'built' : 'widget not built yet'}</span>
            </span>
          ))}
        </div>
      </section>
    </div>
  );
};
