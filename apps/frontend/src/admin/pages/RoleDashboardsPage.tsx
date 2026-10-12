import React, { useMemo } from 'react';
import { Link, useSearchParams } from '../lib/router';
import { LayoutGrid, EyeOff, Hammer, PowerOff, FileCode2, CheckCircle2 } from '../lib/icons';
import { PageHeader, StatGrid } from '../components/ui/dashboard';
import { resolveWidgetIds, useRoles, widgetModuleId } from '../data/roles';
import { findModule, moduleColor } from '../data/architecture';
import { moduleAccess, useEntitlementView } from '../data/entitlement';
import { MODULE_WIDGETS, DashboardWidget, WidgetSize } from '../data/widgets';

const SPAN: Record<WidgetSize, string> = {
  '1x1': 'sm:col-span-1',
  '2x1': 'sm:col-span-2',
  '2x2': 'sm:col-span-2 sm:row-span-2'
};

type CardState =
  | { kind: 'ready'; widget: DashboardWidget }
  | { kind: 'hidden'; permission: string }
  | { kind: 'disabled'; reason: string }
  | { kind: 'not-built' };

/**
 * Admin preview of the role dashboard shell (apps/frontend/src/dashboard). Same rules:
 * widgets come only from modules in the entitlement, are hidden when the role lacks the
 * widget's permission key, and ids no module exports yet render a "Not built yet" card.
 */
export const RoleDashboardsPage: React.FC = () => {
  const [params, setParams] = useSearchParams();
  const view = useEntitlementView();
  const { ROLES, ROLE_LAYOUTS, ROLES_PROFILE_TITLE } = useRoles();
  const roleIds = Object.keys(ROLE_LAYOUTS);
  const roleId = params.get('role') && ROLE_LAYOUTS[params.get('role')!] ? params.get('role')! : 'management';
  const role = ROLES.find((r) => r.id === roleId)!;
  const layout = ROLE_LAYOUTS[roleId]!;

  const cards = useMemo(() => {
    const granted = new Set(role.permissions);
    return resolveWidgetIds(roleId).map((id): { id: string; state: CardState } => {
      const moduleId = widgetModuleId(id);
      const widget = MODULE_WIDGETS[moduleId]?.find((w) => w.id === id);
      if (!widget) return { id, state: { kind: 'not-built' } };
      const mod = findModule(moduleId);
      const access = mod ? moduleAccess(mod, view) : 'not-in-profile';
      if (access === 'upgrade') return { id, state: { kind: 'disabled', reason: "Not in this organisation's plan" } };
      if (access === 'not-in-profile') return { id, state: { kind: 'disabled', reason: 'Not in this academy profile' } };
      if (!granted.has(widget.permission)) return { id, state: { kind: 'hidden', permission: widget.permission } };
      return { id, state: { kind: 'ready', widget } };
    });
  }, [roleId, role, view]);

  const built = cards.filter((c) => c.state.kind === 'ready').length;

  // Coverage across every layout, for the summary table.
  const coverage = roleIds.map((id) => {
    const ids = resolveWidgetIds(id);
    const done = ids.filter((w) => MODULE_WIDGETS[widgetModuleId(w)]?.some((x) => x.id === w)).length;
    return { id, total: ids.length, done };
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Role Dashboards"
        subtitle={
          <>
            One dashboard page, {roleIds.length} layouts ({ROLES_PROFILE_TITLE} profile and platform roles). Each role's widgets are listed in{' '}
            <code className="text-[#6B21A8]">platform/identity/config/dashboards/&lt;role&gt;.yaml</code>.
          </>
        }
        actions={
          <label className="text-xs text-[#334155] flex items-center gap-2">
            View as
            <select
              value={roleId}
              onChange={(e) => setParams({ role: e.target.value })}
              className="h-8 px-3 rounded-md bg-[#FFFFFF] border border-[#E2E8F0] text-xs text-[#12233F] focus:outline-none focus:border-[#CBD5E1]"
            >
              {roleIds.map((id) => (
                <option key={id} value={id}>{ROLE_LAYOUTS[id]!.title}</option>
              ))}
            </select>
          </label>
        }
      />

      <StatGrid
        stats={[
          { label: 'Widgets on this dashboard', icon: LayoutGrid, value: String(cards.length), note: layout.title },
          { label: 'Live', icon: CheckCircle2, value: String(built), note: 'Built and permitted' },
          { label: 'Not built yet', icon: Hammer, value: String(cards.filter((c) => c.state.kind === 'not-built').length), deltaTone: 'alert', note: 'No module exports these widgets yet' },
          {
            label: 'Coverage, all roles',
            icon: FileCode2,
            value: `${Math.round((coverage.reduce((n, c) => n + c.done, 0) / Math.max(1, coverage.reduce((n, c) => n + c.total, 0))) * 100)}%`,
            note: `Widgets built across ${roleIds.length} layouts`
          }
        ]}
      />

      <div className="grid grid-cols-1 xl:grid-cols-12 gap-6 items-start">
        <section className="xl:col-span-8 space-y-3" aria-label={`${layout.title} dashboard`}>
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-bold text-[#12233F]">{layout.title}</h2>
            <span className="text-[11px] text-[#475569]">{built} of {cards.length} widgets live</span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-3 auto-rows-[minmax(130px,auto)]">
            {cards.map(({ id, state }) => {
              const mod = findModule(widgetModuleId(id));
              const size = state.kind === 'ready' ? state.widget.size : '1x1';
              const accent = mod ? moduleColor(mod) : '#64748B';
              return (
                <article
                  key={id}
                  className={`rounded-xl border p-4 flex flex-col gap-2 ${SPAN[size]} ${
                    state.kind === 'ready' ? 'bg-[#FFFFFF] border-[#E2E8F0]' : 'bg-[#FFFFFF] border-dashed border-[#CBD5E1]'
                  }`}
                >
                  <header className="flex items-start justify-between gap-2">
                    <h3 className="text-xs font-semibold text-[#12233F] leading-snug">
                      {state.kind === 'ready' ? state.widget.title : id}
                    </h3>
                    <span className="w-2 h-2 rounded-full mt-1 flex-shrink-0" style={{ background: accent }} />
                  </header>
                  <div className="flex-1">
                    {state.kind === 'ready' && <state.widget.component role={roleId} />}
                    {state.kind === 'not-built' && (
                      <p className="text-[11px] text-[#475569] flex items-center gap-1.5">
                        <Hammer className="w-3.5 h-3.5" /> Not built yet
                      </p>
                    )}
                    {state.kind === 'disabled' && (
                      <p className="text-[11px] text-[#8A4F00] flex items-center gap-1.5">
                        <PowerOff className="w-3.5 h-3.5" /> {state.reason}
                      </p>
                    )}
                    {state.kind === 'hidden' && (
                      <p className="text-[11px] text-[#B91C1C] flex items-center gap-1.5">
                        <EyeOff className="w-3.5 h-3.5" /> Hidden: role lacks <code>{state.permission}</code>
                      </p>
                    )}
                  </div>
                  {mod && (
                    <Link to={`/modules/${mod.id}`} className="text-[10px] font-mono text-[#64748B] hover:text-[#7E22CE] truncate">
                      {mod.id}{state.kind === 'ready' || state.kind === 'hidden' ? ` · needs ${state.kind === 'ready' ? state.widget.permission : state.permission}` : ''}
                    </Link>
                  )}
                </article>
              );
            })}
          </div>
        </section>

        <aside className="xl:col-span-4 space-y-4">
          <div className="bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] p-4">
            <h3 className="text-[13px] font-bold uppercase tracking-wide text-[#12233F] mb-2 flex items-center gap-1.5">
              <FileCode2 className="w-3.5 h-3.5 text-[#7E22CE]" />
              {layout.role}.yaml
            </h3>
            <pre className="text-[11px] leading-relaxed text-[#334155] bg-[#FFFFFF] rounded-lg p-3 overflow-x-auto">
{`role: ${layout.role}
title: "${layout.title}"${layout.extends ? `\nextends: ${layout.extends}` : ''}
widgets:
${layout.widgets.map((w) => `  - ${w}`).join('\n')}`}
            </pre>
          </div>

          <div className="bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] overflow-hidden">
            <h3 className="text-[13px] font-bold uppercase tracking-wide text-[#12233F] p-4 pb-2">Widget coverage by role</h3>
            <table className="w-full text-xs">
              <tbody className="divide-y divide-[#F1F5F9]">
                {coverage.map((c) => (
                  <tr
                    key={c.id}
                    onClick={() => setParams({ role: c.id })}
                    className={`cursor-pointer hover:bg-[#F6F8FB] ${c.id === roleId ? 'bg-[#7E22CE26]' : ''}`}
                  >
                    <td className="py-2 px-4 text-[#12233F]">{ROLE_LAYOUTS[c.id]!.title}</td>
                    <td className="py-2 px-4 text-right text-[#475569] whitespace-nowrap">{c.done} / {c.total}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </aside>
      </div>
    </div>
  );
};
