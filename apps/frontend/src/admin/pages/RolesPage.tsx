import React, { useMemo, useState } from 'react';
import { Link } from '../lib/router';
import {
  Shield,
  Check,
  X,
  ArrowRight,
  CheckCircle2,
  Search,
  ChevronDown,
  ChevronRight,
  LayoutGrid,
  KeyRound,
  Users
} from '../lib/icons';
import { SUITES, PLATFORM_SERVICES, INTEGRATIONS, ModuleInfo, suiteLabel } from '../data/architecture';
import { MODULE_PERMISSIONS } from '../data/repo';
import { RoleDef, DataScope, resolveWidgetIds, useRoles } from '../data/roles';
import { PageHeader, StatGrid } from '../components/ui/dashboard';

interface ModuleGroup {
  id: string;
  label: string;
  color: string;
  modules: ModuleInfo[];
}

const GROUPS: ModuleGroup[] = [
  ...SUITES.map((s) => ({ id: s.id, label: suiteLabel(s), color: s.color, modules: s.modules })),
  { id: 'platform', label: 'Platform services', color: '#9333EA', modules: PLATFORM_SERVICES },
  { id: 'integrations', label: 'Integrations', color: '#16834B', modules: INTEGRATIONS }
];

/** Keys a module defines in its contracts/permissions.yaml. */
const keysOf = (m: ModuleInfo) => (MODULE_PERMISSIONS[m.id] ?? []).map((d) => d.key);

const SCOPES: { id: DataScope; hint: string }[] = [
  { id: 'Institution', hint: 'Entire organisation' },
  { id: 'Department', hint: 'Own department' },
  { id: 'Assigned Records', hint: 'Assigned classes / athletes' },
  { id: 'Self', hint: 'Own records only' }
];


export const RolesPage: React.FC = () => {
  const { ROLES, ROLE_LAYOUTS, ROLES_SOURCE } = useRoles();
  const [roles, setRoles] = useState<RoleDef[]>(() => ROLES.map((r) => ({ ...r, permissions: [...r.permissions] })));
  const [selectedRoleId, setSelectedRoleId] = useState<string>('department-admin');
  const [query, setQuery] = useState('');
  const [grantedOnly, setGrantedOnly] = useState(false);
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const [toastMsg, setToastMsg] = useState<string | null>(null);

  const selectedRole = roles.find((r) => r.id === selectedRoleId) ?? roles[0]!;
  const granted = useMemo(() => new Set(selectedRole.permissions), [selectedRole]);
  const layout = ROLE_LAYOUTS[selectedRole.id];

  const showNotification = (msg: string) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 3000);
  };

  const updateSelected = (fn: (r: RoleDef) => RoleDef) =>
    setRoles((prev) => prev.map((r) => (r.id === selectedRoleId ? fn(r) : r)));

  const handleDataScopeChange = (scope: DataScope) => {
    updateSelected((r) => ({ ...r, dataScope: scope }));
    showNotification(`Sample setting: "${scope}" is shown for ${selectedRole.title} but is not stored or enforced`);
  };

  const q = query.trim().toLowerCase();
  const visibleGroups = GROUPS.map((g) => ({
    ...g,
    modules: g.modules.filter((m) => {
      if (q && !m.name.toLowerCase().includes(q) && !m.id.includes(q)) return false;
      if (grantedOnly && !keysOf(m).some((k) => granted.has(k))) return false;
      return true;
    })
  })).filter((g) => g.modules.length > 0);

  return (
    <div className="space-y-6">
      {toastMsg && (
        <div className="fixed bottom-6 right-6 z-50 flex items-center gap-2 bg-[#12233F] text-white px-4 py-3 rounded-lg shadow-xl border border-[#12233F] text-xs">
          <CheckCircle2 className="w-4 h-4 text-[#126B3D]" />
          <span>{toastMsg}</span>
        </div>
      )}

      <PageHeader
        title="Roles & Permissions"
        subtitle={
          <>
            Roles from the academy profile plus the platform roles. Modules check permission keys{' '}
            <code className="text-[#6B21A8]">&lt;module&gt;:&lt;resource&gt;:&lt;action&gt;</code>, granted to roles in each
            module's contracts/permissions.yaml.
          </>
        }
      />

      <StatGrid
        stats={[
          { label: 'Roles', icon: Shield, value: String(roles.length), note: `${roles.filter((r) => !r.system).length} from the profile + org-admin, super-admin` },
          { label: 'Assigned users', icon: Users, value: roles.reduce((n, r) => n + r.userCount, 0).toLocaleString('en-IN'), note: 'Across all roles' },
          { label: 'Keys for this role', icon: KeyRound, value: String(selectedRole.permissions.length), note: selectedRole.title },
          { label: 'Dashboard layouts', icon: LayoutGrid, value: String(Object.keys(ROLE_LAYOUTS).length), note: 'platform/identity/config/dashboards' }
        ]}
      />

      {/* How access is decided */}
      <div className="bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] p-4 shadow-2xs">
        <div className="text-[11px] font-bold uppercase tracking-wider text-[#475569] mb-3 flex items-center gap-1.5">
          <Shield className="w-3.5 h-3.5 text-[#7E22CE]" />
          <span>How access is decided (platform/identity)</span>
        </div>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-2">
          {[
            { step: '1. User', sub: 'Email and password (platform/identity)' },
            { step: '2. Role', sub: 'From the academy profile, or a platform role' },
            { step: '3. Permission keys', sub: 'Modules check keys, never roles' },
            { step: '4. Organisation', sub: 'Row-level security on organisation_id' },
            { step: '5. Entitlement', sub: 'Module must be in profile and plan' }
          ].map((item, idx) => (
            <div key={item.step} className="flex items-center justify-between p-2.5 rounded-lg bg-[#F6F8FB] border border-[#E2E8F0]">
              <div className="min-w-0">
                <div className="text-xs font-bold text-[#7E22CE]">{item.step}</div>
                <div className="text-[10px] text-[#475569] truncate">{item.sub}</div>
              </div>
              {idx < 4 && <ArrowRight className="hidden md:block w-3.5 h-3.5 text-[#64748B] flex-shrink-0" />}
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Role list */}
        <div className="lg:col-span-4 bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] p-4 shadow-2xs space-y-3 lg:sticky lg:top-20">
          <div className="flex items-center justify-between pb-2 border-b border-[#E2E8F0]">
            <h2 className="text-[13px] font-bold uppercase tracking-wide text-[#12233F]">Roles ({roles.length})</h2>
            <span className="text-[11px] text-[#64748B] truncate" title={ROLES_SOURCE}>{ROLES_SOURCE.replace('platform/identity/config/', '')}</span>
          </div>

          <div className="space-y-1 max-h-[60vh] overflow-y-auto pr-1">
            {roles.map((role) => {
              const isSelected = role.id === selectedRoleId;
              return (
                <button
                  key={role.id}
                  onClick={() => setSelectedRoleId(role.id)}
                  className={`w-full text-left px-3 py-2.5 rounded-lg transition-all border ${
                    isSelected
                      ? 'bg-[#7E22CE26] border-[#9333EA] shadow-xs'
                      : 'border-transparent hover:bg-[#F6F8FB]'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className={`text-xs font-bold truncate ${isSelected ? 'text-[#7E22CE]' : 'text-[#12233F]'}`}>
                      {role.title}
                    </span>
                    {role.system && (
                      <span className="text-[9px] font-semibold uppercase px-1.5 py-0.5 rounded bg-[#F39A1926] text-[#8A4F00] flex-shrink-0">
                        system
                      </span>
                    )}
                  </div>
                  <div className="mt-1 flex items-center gap-2 text-[10px] text-[#475569]">
                    <span className="font-mono text-[#64748B]">{role.id}</span>
                    <span>•</span>
                    <span>{role.userCount.toLocaleString('en-IN')} users</span>
                    <span>•</span>
                    <span>{role.permissions.length} keys</span>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Selected role */}
        <div className="lg:col-span-8 space-y-6">
          <div className="bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] p-5 shadow-2xs space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3 pb-3 border-b border-[#E2E8F0]">
              <div>
                <div className="flex items-center gap-2 flex-wrap">
                  <h2 className="text-lg font-bold text-[#12233F]">{selectedRole.title}</h2>
                  <span className="text-xs font-mono px-2 py-0.5 rounded bg-[#F1F5F9] text-[#475569]">{selectedRole.id}</span>
                </div>
                <p className="text-xs text-[#475569] mt-1 max-w-2xl">{selectedRole.description}</p>
              </div>
              <span className="text-xs font-medium px-2.5 py-1 rounded bg-[#16834B26] text-[#126B3D] self-start whitespace-nowrap">
                {selectedRole.userCount.toLocaleString('en-IN')} users
              </span>
            </div>

            {/* Data scope */}
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-xs font-bold uppercase tracking-wider text-[#12233F]">Data scope</label>
                <span className="text-[11px] text-[#475569]">Sample setting, not in the repo yet; row-level security is per organisation</span>
              </div>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {SCOPES.map(({ id, hint }) => {
                  const active = selectedRole.dataScope === id;
                  return (
                    <button
                      key={id}
                      onClick={() => handleDataScopeChange(id)}
                      className={`p-2.5 rounded-lg border text-left transition-all ${
                        active
                          ? 'border-[#9333EA] bg-[#7E22CE26] text-[#7E22CE] font-bold shadow-2xs'
                          : 'border-[#E2E8F0] hover:bg-[#F6F8FB] text-[#475569]'
                      }`}
                    >
                      <div className="text-xs flex items-center justify-between">
                        <span>{id}</span>
                        {active && <Check className="w-3.5 h-3.5" />}
                      </div>
                      <span className="text-[10px] font-normal block mt-0.5 text-[#475569]">{hint}</span>
                    </button>
                  );
                })}
              </div>
            </div>

            {/* Dashboard layout */}
            <div className="pt-3 border-t border-[#E2E8F0]">
              <div className="flex items-center justify-between mb-2">
                <label className="text-xs font-bold uppercase tracking-wider text-[#12233F] flex items-center gap-1.5">
                  <LayoutGrid className="w-3.5 h-3.5 text-[#7E22CE]" />
                  Dashboard layout
                </label>
                {layout && (
                  <Link to={`/dashboards?role=${selectedRole.id}`} className="text-[11px] text-[#7E22CE] hover:underline">
                    Preview dashboard →
                  </Link>
                )}
              </div>
              {layout ? (
                <>
                  <p className="text-[11px] text-[#64748B] mb-2 font-mono">
                    platform/identity/config/dashboards/{layout.role}.yaml
                    {layout.extends && <span className="text-[#475569]"> · extends {layout.extends}</span>}
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {resolveWidgetIds(selectedRole.id).map((w) => (
                      <span key={w} className="text-[10px] font-mono px-2 py-1 rounded bg-[#F6F8FB] border border-[#E2E8F0] text-[#334155]">
                        {w}
                      </span>
                    ))}
                  </div>
                </>
              ) : (
                <p className="text-[11px] text-[#475569]">No dashboard layout. System roles use the admin console.</p>
              )}
            </div>
          </div>

          {/* Permission matrix */}
          <div className="bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] shadow-2xs overflow-hidden">
            <div className="p-4 border-b border-[#E2E8F0] bg-[#F6F8FB] flex flex-col md:flex-row md:items-center justify-between gap-3">
              <div>
                <h3 className="text-[13px] font-bold uppercase tracking-wide text-[#12233F] flex items-center gap-1.5">
                  <KeyRound className="w-3.5 h-3.5 text-[#7E22CE]" />
                  Permission keys · {selectedRole.title}
                </h3>
                <p className="text-[11px] text-[#475569]">
                  Each chip is a key a module defines in its contracts/permissions.yaml. Grants are made there, by role name.
                </p>
              </div>
              <div className="flex items-center gap-2 flex-wrap">
                <div className="relative">
                  <Search className="w-3.5 h-3.5 text-[#64748B] absolute left-2.5 top-1/2 -translate-y-1/2" />
                  <input
                    value={query}
                    onChange={(e) => setQuery(e.target.value)}
                    placeholder="Filter modules"
                    className="pl-8 pr-3 py-1.5 w-40 rounded-lg bg-[#FFFFFF] border border-[#E2E8F0] text-xs text-[#12233F] placeholder:text-[#64748B] focus:outline-none focus:border-[#9333EA]"
                  />
                </div>
                <label className="inline-flex items-center gap-1.5 text-[11px] text-[#334155] cursor-pointer">
                  <input type="checkbox" checked={grantedOnly} onChange={(e) => setGrantedOnly(e.target.checked)} className="accent-[#7E22CE]" />
                  Granted only
                </label>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-[#F1F5F9] border-b border-[#E2E8F0] text-[#475569] font-semibold">
                    <th className="py-2.5 px-4 min-w-[220px]">Module</th>
                    <th className="py-2.5 px-3 uppercase tracking-wider text-[11px]">Permission keys</th>
                  </tr>
                </thead>
                {visibleGroups.map((group) => {
                  const isCollapsed = collapsed[group.id];
                  const groupGrants = group.modules.reduce((n, m) => n + keysOf(m).filter((k) => granted.has(k)).length, 0);
                  return (
                    <tbody key={group.id} className="divide-y divide-[#F1F5F9]">
                      <tr className="bg-[#FFFFFF]">
                        <td colSpan={2} className="py-2 px-4">
                          <button
                            onClick={() => setCollapsed((c) => ({ ...c, [group.id]: !c[group.id] }))}
                            className="flex items-center gap-2 text-[11px] font-bold uppercase tracking-wider text-[#334155] w-full"
                          >
                            {isCollapsed ? <ChevronRight className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                            <span className="w-2 h-2 rounded-full" style={{ background: group.color }} />
                            <span>{group.label}</span>
                            <span className="ml-auto font-medium normal-case tracking-normal text-[#64748B]">
                              {groupGrants} granted
                            </span>
                          </button>
                        </td>
                      </tr>
                      {!isCollapsed &&
                        group.modules.map((m) => (
                          <tr key={m.id} className="hover:bg-[#F6F8FB] transition-colors">
                            <td className="py-2 px-4">
                              <Link to={`/modules/${m.id}`} className="font-semibold text-[#12233F] hover:text-[#7E22CE]">
                                {m.name}
                              </Link>
                              <div className="text-[10px] font-mono text-[#64748B]">{m.id}</div>
                            </td>
                            <td className="py-2 px-3">
                              {keysOf(m).length === 0 ? (
                                <span className="text-[11px] text-[#64748B]">None defined yet</span>
                              ) : (
                                <div className="flex flex-wrap gap-1.5">
                                  {keysOf(m).map((key) => {
                                    const isGranted = granted.has(key);
                                    return (
                                      <span
                                        key={key}
                                        className={`inline-flex items-center gap-1 px-2 py-1 rounded-md font-mono text-[10px] ${
                                          isGranted ? 'bg-[#16834B26] text-[#126B3D] shadow-2xs' : 'bg-[#F1F5F9] text-[#64748B]'
                                        }`}
                                        title={`${key}: ${isGranted ? 'granted' : 'not granted'} to ${selectedRole.id}`}
                                      >
                                        {isGranted ? <Check className="w-3.5 h-3.5 stroke-[2.5]" /> : <X className="w-3.5 h-3.5 stroke-[2]" />}
                                        {key}
                                      </span>
                                    );
                                  })}
                                </div>
                              )}
                            </td>
                          </tr>
                        ))}
                    </tbody>
                  );
                })}
              </table>
              {visibleGroups.length === 0 && (
                <p className="p-6 text-center text-xs text-[#475569]">No modules match.</p>
              )}
            </div>

            <div className="p-3 bg-[#F6F8FB] border-t border-[#E2E8F0] flex items-center justify-between text-[11px] text-[#475569]">
              <span className="flex items-center gap-1.5">
                <span className="w-2.5 h-2.5 rounded bg-[#16834B26] border border-[#16834B]/30" />
                <span>Granted</span>
                <span className="w-2.5 h-2.5 rounded bg-[#F1F5F9] border border-[#CBD5E1] ml-2" />
                <span>Not granted</span>
              </span>
              <span>{selectedRole.permissions.length} keys granted</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
