import { asset } from '../lib/assets';
import React, { useState } from 'react';
import { useParams, Link } from '../lib/router';
import { Layers, ArrowRight, FileCode2, KeyRound, LayoutGrid, Users, Power, Plus, Download, Activity, Clock, TrendingUp, CheckCircle2, ChevronDown } from '../lib/icons';
import { ThemeScope } from '../components/ui/theme';
import { themeForModule } from '../data/suiteThemes';
import { PageHeader, StatGrid, PANEL, BTN_PRIMARY, BTN_SECONDARY } from '../components/ui/dashboard';
import { CampusPhoto } from '../components/ui/CampusArt';

/** Module pages with a photo header (image in /public and its focal position). */
const MODULE_PHOTOS: Record<string, { src: string; position: string }> = {
  'student-information': { src: asset('/students.jpg'), position: '50% 72%' },
  'enrolment-registration': { src: asset('/enrolment.jpg'), position: '40% 60%' },
  'web-portal-cms': { src: asset('/web-portal.jpg'), position: '60% 55%' },
  'academic-management': { src: asset('/academics.jpg'), position: '70% 45%' },
  lms: { src: asset('/lms.jpg'), position: '55% 45%' },
  'timetable-attendance': { src: asset('/timetable.jpg'), position: '50% 40%' },
  examinations: { src: asset('/examinations.jpg'), position: '50% 12%' },
  'athlete-performance': { src: asset('/athletes.jpg'), position: '50% 42%' },
  'training-video-analysis': { src: asset('/training.jpg'), position: '50% 30%' },
  'sports-nutrition-health': { src: asset('/nutrition.jpg'), position: '50% 18%' },
  'tournament-events': { src: asset('/tournaments.jpg'), position: '50% 30%' },
  'sports-facilities': { src: asset('/facilities.jpg'), position: '50% 45%' },
  'facility-booking': { src: asset('/facility-booking.jpg'), position: '50% 40%' },
  'inventory-equipment': { src: asset('/inventory.jpg'), position: '50% 30%' },
  'asset-management': { src: asset('/assets.jpg'), position: '50% 28%' },
  maintenance: { src: asset('/maintenance.jpg'), position: '50% 30%' },
  'fees-accounts': { src: asset('/fees.jpg'), position: '50% 55%' },
  'budget-grants': { src: asset('/budget.jpg'), position: '50% 55%' },
  procurement: { src: asset('/procurement.jpg'), position: '50% 50%' },
  'hr-payroll': { src: asset('/hr-payroll.jpg'), position: '0% 50%' },
  hostel: { src: asset('/hostel.jpg'), position: '50% 25%' },
  'e-office': { src: asset('/e-office.jpg'), position: '50% 25%' },
  transport: { src: asset('/transport.jpg'), position: '50% 25%' },
  portfolio: { src: asset('/portfolio-v3.jpg'), position: '100% 50%' },
  projects: { src: asset('/projects-v2.jpg'), position: '100% 50%' },
  'selection-process': { src: asset('/selection-process.jpg'), position: '100% 50%' },
  productions: { src: asset('/productions.jpg'), position: '100% 50%' },
  'field-training': { src: asset('/field-training.jpg'), position: '100% 50%' },
  'skill-progress': { src: asset('/skill-progress.jpg'), position: '100% 50%' },
  library: { src: asset('/library.jpg'), position: '100% 50%' },
  alumni: { src: asset('/alumni.jpg'), position: '100% 50%' },
  'placement-career': { src: asset('/placement-career.jpg'), position: '100% 50%' },
  grievance: { src: asset('/grievance.jpg'), position: '100% 50%' },
  rti: { src: asset('/rti.jpg'), position: '100% 50%' },
  'iqac-accreditation': { src: asset('/iqac-accreditation.jpg'), position: '100% 50%' }
};
import { HistogramPanel, BreakdownPanel, ActionPanel, ActivityPanel } from '../components/ui/panels';
import { MODULE_DASHBOARDS, fallbackDashboard, monthlySeries } from '../data/moduleDashboards';
import { MODULE_ICONS } from '../data/moduleIcons';
import { findModule, findSuite, suiteLabel } from '../data/architecture';
import { rolesUsingModule, widgetsByModule, roleTitle } from '../data/roles';
import { ACCESS_LABEL, moduleAccess, useEntitlementView } from '../data/entitlement';
import { MANIFESTS, MODULE_PERMISSIONS, ROLE_GRANTS } from '../data/repo';
import { MODULE_WIDGETS } from '../data/widgets';

/** Folder of a module inside the monorepo. */
const repoPath = (kind: string, suiteDomain: string | undefined, id: string) =>
  kind === 'feature' ? `modules/${suiteDomain}/${id}` : kind === 'platform' ? `platform/${id}` : `integrations/${id}`;

/** Module dashboard in the main Dashboard's layout, with the module's manifest and keys in a collapsible section. */
export const ModulePage: React.FC = () => {
  const { moduleId = '' } = useParams<{ moduleId: string }>();
  const view = useEntitlementView();
  const [toast, setToast] = useState<string | null>(null);
  const mod = findModule(moduleId);

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3000);
  };

  if (!mod) {
    return (
      <div className="max-w-xl mx-auto py-16 text-center space-y-4">
        <h1 className="text-xl font-bold text-[#12233F]">Unknown module "{moduleId}"</h1>
        <Link to="/modules" className="text-xs text-[var(--accent)] hover:underline">Back to the module registry</Link>
      </div>
    );
  }

  const suite = findSuite(mod.suiteId);
  const path = repoPath(mod.kind, suite?.domain, mod.id);
  const access = moduleAccess(mod, view);
  const manifest = MANIFESTS[mod.id];
  const widgetIds = widgetsByModule(mod.id);
  const builtWidgets = new Set((MODULE_WIDGETS[mod.id] ?? []).map((w) => w.id));
  const dashboardRoles = rolesUsingModule(mod.id);
  // Keys this module defines in contracts/permissions.yaml, and the role names the repo grants each to.
  const keys = (MODULE_PERMISSIONS[mod.id] ?? []).map((d) => d.key);
  const holders = (key: string) => Object.entries(ROLE_GRANTS).filter(([, ks]) => ks.has(key)).map(([name]) => name);

  const dash = MODULE_DASHBOARDS[mod.id] ?? fallbackDashboard(mod);
  const kpiIcons = [MODULE_ICONS[mod.id] ?? Layers, Activity, Clock, TrendingUp];
  const rows = monthlySeries(mod.id, dash.chart.base, dash.chart.split ?? 0);
  const series = dash.chart.series.map((name, i) => ({ key: i === 0 ? 'a' : 'b', name }));

  return (
    <ThemeScope theme={themeForModule(mod.id)} className="space-y-8">
      {toast && (
        <div className="fixed bottom-6 right-6 z-50 flex items-center gap-2 bg-[#12233F] text-white px-4 py-3 rounded-lg shadow-lg text-xs">
          <CheckCircle2 className="w-4 h-4 text-[#4ADE80]" />
          <span>{toast}</span>
        </div>
      )}

      <PageHeader
        art={MODULE_PHOTOS[mod.id] ? <CampusPhoto {...MODULE_PHOTOS[mod.id]} fit="right" /> : undefined}
        eyebrow={
          <span className="inline-flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-white" />
            {suite ? suiteLabel(suite) : mod.kind === 'platform' ? 'Shared platform service' : 'External integration'}
          </span>
        }
        title={mod.name}
        subtitle={
          <>
            {mod.description}
            <span className="block text-xs text-[#64748B] mt-0.5">
              {mod.implemented ? 'Backend built · figures below are sample data' : 'Not built yet: sample data'} · {ACCESS_LABEL[access]}
            </span>
          </>
        }
        actions={
          <>
            <button onClick={() => showToast(`${dash.action} needs the ${mod.name} ${mod.implemented ? 'screens' : 'module'}, which ${mod.implemented ? 'are' : 'is'} not built yet`)} className={BTN_PRIMARY}>
              <Plus className="w-3.5 h-3.5" />
              {dash.action}
            </button>
            {mod.route ? (
              <Link to={mod.route} className={BTN_SECONDARY}>
                Open workflow <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            ) : (
              <button onClick={() => showToast(`Export needs the ${mod.name} ${mod.implemented ? 'screens' : 'module'}, which ${mod.implemented ? 'are' : 'is'} not built yet`)} className={BTN_SECONDARY}>
                <Download className="w-3.5 h-3.5 text-[#475569]" />
                Export
              </button>
            )}
            {/* Availability follows the entitlement (profile ∩ plan); it is not switched here. */}
            <span className={BTN_SECONDARY} title="Decided by the organisation's academy profile and plan">
              <Power className="w-3.5 h-3.5 text-[#475569]" />
              {ACCESS_LABEL[access]}
            </span>
          </>
        }
      />

      <StatGrid
        stats={dash.kpis.map((kp, i) => ({
          label: kp.label,
          icon: kpiIcons[i]!,
          value: kp.value,
          delta: kp.delta,
          deltaTone: kp.tone ?? 'up',
          note: kp.note
        }))}
      />

      <HistogramPanel
        title={dash.chart.title}
        subtitle={dash.chart.subtitle}
        data={rows}
        xKey="month"
        series={dash.chart.split ? series : series.slice(0, 1)}
        tooltipLabel={(m) => `${m} 2026`}
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <BreakdownPanel
          title={dash.breakdown.title}
          subtitle={dash.breakdown.subtitle}
          items={dash.breakdown.items.map(([label, count]) => ({ label, count }))}
          relativeToFirst={Boolean(dash.breakdown.footer)}
          unit={dash.breakdown.unit}
          footer={dash.breakdown.footer && { label: dash.breakdown.footer[0], value: dash.breakdown.footer[1] }}
        />
        <div className="lg:col-span-2">
        <ActionPanel
          items={dash.actions.map((it, i) => ({ id: `${mod.id}-a${i}`, ...it }))}
          onOpen={(it) => showToast(`${it.ref} is a sample item: the ${mod.name} module is not built yet`)}
        />
        </div>
      </div>

      <ActivityPanel
        subtitle={`${mod.name} audit trail`}
        items={dash.activity.map((it, i) => ({
          id: `${mod.id}-l${i}`,
          time: it.time,
          title: it.title,
          meta: (
            <>
              {it.who} · <span className="font-mono">{it.ref}</span>
            </>
          ),
          status: it.status ?? 'Success'
        }))}
      />

      <details className={`${PANEL} group`}>
        <summary className="list-none cursor-pointer px-5 py-4 flex items-center justify-between gap-4">
          <div>
            <h2 className="text-[13px] font-semibold text-[#12233F]">Module details</h2>
            <p className="text-xs text-[#64748B] mt-0.5">
              Manifest, permission keys and role dashboards · status {mod.status} · {keys.length} keys · {widgetIds.length} widgets ({builtWidgets.size} built) · on {dashboardRoles.length} role dashboards
            </p>
          </div>
          <ChevronDown className="w-4 h-4 text-[#64748B] transition-transform group-open:rotate-180" />
        </summary>
        <div className="px-5 pb-5 pt-1">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Manifest */}
          <section className="bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] p-4 space-y-2">
            <h2 className="text-[13px] font-bold uppercase tracking-wide text-[#12233F] flex items-center gap-1.5">
              <FileCode2 className="w-3.5 h-3.5 text-[var(--accent)]" /> {path}/module.yaml
            </h2>
            <pre className="text-[11px] leading-relaxed text-[#334155] bg-[#FFFFFF] rounded-lg p-3 overflow-x-auto">
  {`name: ${manifest?.name ?? mod.id}
  kind: ${manifest?.kind ?? mod.kind}
  domain: ${manifest?.domain ?? suite?.domain ?? mod.kind}
  tier: ${manifest?.tier ?? ''}${manifest?.field ? `
  field: ${manifest.field}` : ''}
  status: ${manifest?.status ?? mod.status}
  description: "${mod.description}"
  exposes:
    api: contracts/openapi.yaml        # /api/v1/${mod.id}
    events: contracts/events.yaml      # ${mod.id}.<entity>.<past-verb>
    permissions: contracts/permissions.yaml`}
            </pre>
            <p className="text-[11px] text-[#64748B]">
              Other modules reach this one only through these contracts and events, never by importing its code.
            </p>
          </section>

          {/* Permission keys */}
          <section className="bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] overflow-hidden">
            <h2 className="text-[13px] font-bold uppercase tracking-wide text-[#12233F] p-4 pb-2 flex items-center gap-1.5">
              <KeyRound className="w-3.5 h-3.5 text-[var(--accent)]" /> Permission keys
            </h2>
            <table className="w-full text-xs">
              <tbody className="divide-y divide-[#F1F5F9]">
                {keys.length === 0 && (
                  <tr>
                    <td className="py-2 px-4 text-[11px] text-[#475569]">
                      None defined yet in <span className="font-mono">{path}/contracts/permissions.yaml</span>.
                    </td>
                  </tr>
                )}
                {keys.map((k) => {
                  const rs = holders(k);
                  return (
                    <tr key={k}>
                      <td className="py-2 px-4 font-mono text-[11px] text-[#12233F] whitespace-nowrap">{k}</td>
                      <td className="py-2 px-4 text-[11px] text-[#475569]">
                        {rs.length ? rs.map(roleTitle).join(', ') : <span className="text-[#64748B]">Not granted to any role yet</span>}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
            <div className="p-3 border-t border-[#E2E8F0] text-right">
              <Link to="/roles" className="text-[11px] text-[var(--accent)] hover:underline">See Roles & Permissions →</Link>
            </div>
          </section>

          {/* Widgets */}
          <section className="bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] p-4 space-y-3">
            <h2 className="text-[13px] font-bold uppercase tracking-wide text-[#12233F] flex items-center gap-1.5">
              <LayoutGrid className="w-3.5 h-3.5 text-[var(--accent)]" /> Dashboard widgets
            </h2>
            {widgetIds.length ? (
              <ul className="space-y-1.5">
                {widgetIds.map((w) => (
                  <li key={w} className="flex items-center justify-between gap-2 text-[11px]">
                    <code className="text-[#334155]">{w}</code>
                    <span className={builtWidgets.has(w) ? 'text-[#126B3D]' : 'text-[#64748B]'}>
                      {builtWidgets.has(w) ? 'built' : 'not built yet'}
                    </span>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="text-[11px] text-[#475569]">No role layout references a widget from this module.</p>
            )}
            <p className="text-[11px] text-[#64748B]">Exported from {path}/frontend/src/widgets/index.ts</p>
          </section>

          {/* Roles */}
          <section className="bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] p-4 space-y-3">
            <h2 className="text-[13px] font-bold uppercase tracking-wide text-[#12233F] flex items-center gap-1.5">
              <Users className="w-3.5 h-3.5 text-[var(--accent)]" /> On these role dashboards
            </h2>
            {dashboardRoles.length ? (
              <div className="flex flex-wrap gap-1.5">
                {dashboardRoles.map((r) => (
                  <Link
                    key={r}
                    to={`/dashboards?role=${r}`}
                    className="text-[11px] px-2 py-1 rounded bg-[#F6F8FB] border border-[#E2E8F0] text-[#334155] hover:border-[#9333EA] hover:text-[#12233F]"
                  >
                    {roleTitle(r)}
                  </Link>
                ))}
              </div>
            ) : (
              <p className="text-[11px] text-[#475569]">None yet.</p>
            )}
          </section>
        </div>
        </div>
      </details>
    </ThemeScope>
  );
};
