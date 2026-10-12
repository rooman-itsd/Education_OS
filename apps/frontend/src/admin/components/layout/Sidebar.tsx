import React, { useEffect, useState } from 'react';
import { NavLink, useLocation } from '../../lib/router';
import {
  LayoutDashboard,
  UserCheck,
  ShieldCheck,
  LayoutGrid,
  Blocks,
  History,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  GraduationCap,
  BookOpen,
  Trophy,
  Building2,
  Wallet,
  Home,
  Scale,
  LifeBuoy,
  Landmark,
  Presentation
} from '../../lib/icons';
import { SUITES, moduleHref } from '../../data/architecture';
import { MODULE_ICONS } from '../../data/moduleIcons';
import { isLive, useEntitlementView, type EntitlementView } from '../../data/entitlement';
import { useOrganisation } from '../../lib/organisation';
import { EduMark, Wordmark } from '../ui/Wordmark';

interface SidebarProps {
  collapsed: boolean;
  onToggleCollapse: () => void;
  mobileOpen: boolean;
  onCloseMobile: () => void;
}

type Icon = React.ComponentType<{ className?: string }>;

interface NavItem {
  name: string;
  path: string;
  icon: Icon;
  badge?: string | number;
  badgeColor?: string;
  /** False until the module is built and within the organisation's entitlement. */
  live?: boolean;
  /** Icon colour class; the icon keeps it whether or not the row is active. */
  color?: string;
}

interface Suite {
  id: string;
  title: string;
  icon: Icon;
  items: NavItem[];
}

/** Suite names for the parent rows; the suite letter is prefixed from the architecture catalogue. */
const SECTION_TITLES: Record<string, string> = {
  'student-lifecycle': 'Student Lifecycle',
  academics: 'Academics',
  practice: 'Practice',
  sports: 'Sports',
  facilities: 'Facilities',
  'finance-operations': 'Finance & Operations',
  'campus-life': 'Campus Life',
  governance: 'Governance',
  support: 'Global Support'
};

const SUITE_ICONS: Record<string, Icon> = {
  'student-lifecycle': GraduationCap,
  academics: BookOpen,
  practice: Presentation,
  sports: Trophy,
  facilities: Building2,
  'finance-operations': Wallet,
  'campus-life': Home,
  governance: Scale,
  support: LifeBuoy
};

/** Short item names and order per suite (module ids from the architecture catalogue). */
const ITEM_LABELS: Record<string, [string, string][]> = {
  'student-lifecycle': [['admissions', 'Admissions'], ['student-information', 'Students'], ['enrolment-registration', 'Enrolment & Registration'], ['web-portal-cms', 'Web Portal & CMS']],
  academics: [['academic-management', 'Academic Management'], ['lms', 'Learning (LMS)'], ['examinations', 'Examination'], ['timetable-attendance', 'Attendance & Timetable']],
  sports: [['athlete-performance', 'Athletes'], ['training-video-analysis', 'Training & Video'], ['sports-nutrition-health', 'Nutrition & Health'], ['tournament-events', 'Tournaments']],
  facilities: [['sports-facilities', 'Facilities'], ['facility-booking', 'Bookings'], ['inventory-equipment', 'Inventory'], ['asset-management', 'Assets'], ['maintenance', 'Maintenance']],
  'finance-operations': [['fees-accounts', 'Fees & Payments'], ['budget-grants', 'Budget & Grants'], ['procurement', 'Procurement'], ['hr-payroll', 'HR & Payroll'], ['e-office', 'E-Office']],
  'campus-life': [['hostel', 'Hostel'], ['transport', 'Transport'], ['library', 'Library'], ['placement-career', 'Placement & Career'], ['alumni', 'Alumni']],
  governance: [['grievance', 'Grievance'], ['rti', 'RTI'], ['iqac-accreditation', 'IQAC / Accreditation'], ['regulatory-reports', 'Compliance & Reports']],
  support: [['helpdesk', 'Helpdesk'], ['sla-management', 'SLA Management'], ['knowledge-base', 'Knowledge Base'], ['incident-management', 'Incidents'], ['amc-vendor-support', 'AMC & Vendors']]
};

/** Pending-work counts as soft badges: coral is urgent, orange is pending, blue-gray is informational. */
/** Pending-work counts per module, once modules report them. None are built yet. */
const BADGES: Record<string, { value: number; color: string }> = {};

const URGENT = 'bg-[#FEF2F2] text-[#B91C1C]';

const DASHBOARD: NavItem = { name: 'Dashboard', path: '/dashboard', icon: LayoutDashboard, live: true };

const ADMIN_ITEMS: NavItem[] = [
  { name: 'Users', path: '/users', icon: UserCheck, live: true },
  { name: 'Roles & Permissions', path: '/roles', icon: ShieldCheck, live: true },
  { name: 'Role Dashboards', path: '/dashboards', icon: LayoutGrid, live: true },
  { name: 'Module Registry', path: '/modules', icon: Blocks, live: true },
  { name: 'Audit Log', path: '/audit-logs', icon: History, live: true }
];

const buildSuites = (view: EntitlementView): Suite[] =>
  SUITES.map((suite) => {
    const labels = ITEM_LABELS[suite.id] ?? suite.modules.map((m) => [m.id, m.name] as [string, string]);
    return {
      id: suite.id,
      title: `${suite.letter && suite.letter !== '•' ? `${suite.letter} · ` : ''}${SECTION_TITLES[suite.id] ?? suite.name}`,
      icon: SUITE_ICONS[suite.id] ?? Blocks,
      items: labels.flatMap(([id, name]) => {
        const m = suite.modules.find((x) => x.id === id);
        if (!m) return [];
        return [{ name, path: moduleHref(m), icon: MODULE_ICONS[m.id] ?? Blocks, badge: BADGES[m.id]?.value, badgeColor: BADGES[m.id]?.color, live: isLive(m, view) }];
      })
    };
  });

/** Urgent (red) items in a suite, shown on its row while folded. */
const urgentCount = (suite: Suite) =>
  suite.items.reduce((n, i) => n + (i.badgeColor === URGENT ? Number(i.badge) || 0 : 0), 0);

const isActivePath = (pathname: string, path: string) =>
  pathname === path || (path !== '/dashboard' && path !== '/modules' && pathname.startsWith(`${path}/`));

/**
 * The top-level row a route belongs to, which carries the active highlight:
 * the suite whose module the route opens, otherwise the Dashboard or Administration
 * row itself. Module pages outside the suites (platform services, integrations)
 * belong to Module Registry.
 */
const activeKeyForPath = (suites: Suite[], pathname: string): string | undefined => {
  const suite = suites.find((s) => s.items.some((i) => isActivePath(pathname, i.path)));
  if (suite) return suite.id;
  const top = [DASHBOARD, ...ADMIN_ITEMS].find((i) => isActivePath(pathname, i.path));
  if (top) return top.path;
  return pathname.startsWith('/modules/') ? '/modules' : undefined;
};

/**
 * Navigation colour system. Each row gets CSS variables:
 *   --c  accent (icon, chevron, active indicator)
 *   --t  light tint (hover and active background)
 *   --ic resting icon colour (defaults to --c; slate for Dashboard/Administration)
 *   --h  hover background (defaults to --t)
 *   --at active text colour
 * Text stays dark navy; colour only marks the icon, arrow, hover tint and the active header.
 */
interface NavColor {
  c: string;
  t: string;
  ic?: string;
  h?: string;
  at?: string;
}

/** Suite accents: one distinct colour per Education OS section. */
const SUITE_COLORS: Record<string, NavColor> = {
  'student-lifecycle': { c: '#3B82F6', t: '#EFF6FF', at: '#1D4ED8' },
  academics: { c: '#7C3AED', t: '#F5F3FF', at: '#6D28D9' },
  sports: { c: '#059669', t: '#ECFDF5', at: '#047857' },
  facilities: { c: '#D97706', t: '#FFFBEB', at: '#B45309' },
  'finance-operations': { c: '#0F9F8A', t: '#F0FDFA', at: '#0F766E' },
  'campus-life': { c: '#E45A8A', t: '#FFF1F5', at: '#BE185D' },
  governance: { c: '#C026D3', t: '#FDF4FF', at: '#A21CAF' },
  support: { c: '#64748B', t: '#F1F5F9', at: '#334155' }
};

/** Dashboard and the Administration (system-control) area: neutral slate at rest, indigo when active. */
const SYSTEM_COLOR: NavColor = { c: '#4338CA', t: '#EEF2FF', ic: '#A9B3D6', h: '#F1F5F9', at: '#4338CA' };

const colorVars = (col: NavColor) =>
  ({
    '--c': col.c,
    '--t': col.t,
    '--ic': col.ic ?? col.c,
    '--h': col.h ?? col.t,
    '--at': col.at ?? '#12233F'
  }) as React.CSSProperties;

/** Shared row styling: hover takes the row's tint; the active row keeps the tint, accent text and a 3px indicator. */
const rowClass = (active: boolean) =>
  `group relative w-full flex items-center gap-2.5 px-2.5 h-[34px] rounded-lg text-left text-[13px] transition-colors duration-200 ${
    active ? 'bg-[var(--t)] text-[var(--at)] font-semibold' : 'text-[#12233F] font-medium hover:bg-[var(--h)]'
  }`;

const iconColor = (active: boolean) =>
  active ? 'text-[var(--c)]' : 'text-[var(--ic)] group-hover:text-[var(--c)] group-hover:brightness-90';

const Indicator: React.FC = () => <span aria-hidden className="eos-bar-in absolute left-0 top-1.5 bottom-1.5 w-[3px] rounded-r-full bg-[var(--c)]" />;

/** Icon motion: a small nudge and scale on hover, a gentle pop when active. */
const iconMotion = (active: boolean) =>
  `transition-transform duration-200 group-hover:scale-105 ${active ? 'eos-pop' : ''}`;

const GroupLabel: React.FC<{ children: React.ReactNode; collapsed: boolean }> = ({ children, collapsed }) =>
  collapsed ? (
    <div className="mx-3 my-3 border-t border-[#EEF2F6]" />
  ) : (
    <div className="px-3 pt-5 pb-1.5 text-[11px] font-semibold uppercase tracking-[0.08em] text-[#94A3B8]">{children}</div>
  );

export const Sidebar: React.FC<SidebarProps> = ({ collapsed, onToggleCollapse, mobileOpen, onCloseMobile }) => {
  const location = useLocation();
  const view = useEntitlementView();
  const org = useOrganisation();
  const suites = buildSuites(view);

  // The highlighted row is the parent of the current route. Its suite opens itself;
  // every other suite stays folded until clicked.
  const activeKey = activeKeyForPath(suites, location.pathname);
  const [open, setOpen] = useState<Record<string, boolean>>(() => (activeKey ? { [activeKey]: true } : {}));
  useEffect(() => {
    if (activeKey) setOpen((o) => (o[activeKey] ? o : { ...o, [activeKey]: true }));
  }, [activeKey]);

  const topLink = (item: NavItem) => {
    const active = activeKey === item.path;
    const Icon = item.icon;
    return (
      <NavLink
        key={item.path}
        to={item.path}
        onClick={onCloseMobile}
        title={collapsed ? item.name : undefined}
        aria-current={active ? 'page' : undefined}
        style={colorVars(SYSTEM_COLOR)}
        className={`${rowClass(active)} ${collapsed ? 'justify-center px-0' : ''}`}
      >
        {active && <Indicator />}
        <Icon className={`w-[18px] h-[18px] flex-shrink-0 ${iconMotion(active)} ${iconColor(active)}`} />
        {!collapsed && <span className="truncate flex-1">{item.name}</span>}
      </NavLink>
    );
  };

  return (
    <>
      {/* Mobile backdrop */}
      {mobileOpen && <div className="fixed inset-0 bg-black/30 backdrop-blur-xs z-40 lg:hidden" onClick={onCloseMobile} />}

      <aside
        className={`fixed top-0 bottom-0 left-0 z-50 flex flex-col eos-sidebar-bg text-[#12233F] border-r border-[#ECE6F7] transition-all duration-300 ease-in-out
          ${collapsed ? 'w-[72px]' : 'w-[260px]'}
          ${mobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
        `}
      >
        {/* Product name card: near-white with faint blue and green hints from the wordmark */}
        <div
          className={`mx-3 mt-3 mb-2 flex items-center rounded-xl border border-[#E6ECF5] bg-[linear-gradient(135deg,#F2F7FF_0%,#FFFFFF_55%,#F1FAF4_100%)] ${
            collapsed ? 'flex-col gap-2 px-1.5 py-2.5' : 'justify-between gap-2 px-2.5 py-2.5'
          }`}
        >
          <div className="group min-w-0 flex items-center gap-2" title="Education OS">
            <span className="transition-transform duration-300 group-hover:-translate-y-0.5 group-hover:scale-105">
              <EduMark size={38} />
            </span>
            {!collapsed && (
              <h1>
                <Wordmark className="text-[17px]" />
              </h1>
            )}
          </div>
          <button
            onClick={onToggleCollapse}
            className="hidden lg:flex items-center justify-center w-7 h-7 rounded-md text-[#475569] hover:text-[#12233F] hover:bg-white/70 transition-colors flex-shrink-0"
            title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 pb-4 eos-on-dark" aria-label="Main">
          <div className="pt-1">{topLink(DASHBOARD)}</div>

          <GroupLabel collapsed={collapsed}>Education OS</GroupLabel>
          <div className="space-y-0.5">
            {suites.map((suite, si) => {
              const active = activeKey === suite.id;
              const isOpen = Boolean(open[suite.id]) && !collapsed;
              const SuiteIcon = suite.icon;
              const urgent = urgentCount(suite);
              const col = SUITE_COLORS[suite.id] ?? SYSTEM_COLOR;
              return (
                <div key={suite.id} className="eos-nav-in" style={{ ...colorVars(col), animationDelay: `${60 + si * 40}ms` }}>
                  <button
                    onClick={() => {
                      if (collapsed) onToggleCollapse();
                      setOpen((o) => ({ ...o, [suite.id]: collapsed ? true : !o[suite.id] }));
                    }}
                    aria-expanded={isOpen}
                    aria-current={active ? 'location' : undefined}
                    title={collapsed ? suite.title : undefined}
                    className={`${rowClass(active)} ${collapsed ? 'justify-center px-0' : ''}`}
                  >
                    {active && <Indicator />}
                    <SuiteIcon className={`w-[18px] h-[18px] flex-shrink-0 ${iconMotion(active)} ${iconColor(active)}`} />
                    {!collapsed && (
                      <>
                        <span className="truncate flex-1">{suite.title}</span>
                        {!isOpen && urgent > 0 && (
                          <span title={`${urgent} urgent`} aria-label={`${urgent} urgent`} className="relative flex w-1.5 h-1.5 flex-shrink-0">
                            <span className="absolute inline-flex h-full w-full rounded-full bg-[#DC2626] opacity-60 animate-ping" />
                            <span className="relative inline-flex w-1.5 h-1.5 rounded-full bg-[#DC2626]" />
                          </span>
                        )}
                        <ChevronDown
                          className={`w-4 h-4 flex-shrink-0 transition-transform duration-300 text-[var(--c)] ${active ? 'opacity-100' : 'opacity-50 group-hover:opacity-90'} ${isOpen ? '' : '-rotate-90'}`}
                        />
                      </>
                    )}
                  </button>

                  <div
                    className={`grid transition-[grid-template-rows,opacity] duration-300 ease-out ${isOpen ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0'}`}
                    {...(isOpen ? {} : { inert: '' })}
                  >
                    <div className="overflow-hidden">
                    <div className="ml-[19px] pl-3 border-l border-[#E2E8F0] py-1 space-y-0.5">
                      {suite.items.map((item) => {
                        // The suite header carries the active highlight; the current child only gets darker text and a tiny dot.
                        const here = isActivePath(location.pathname, item.path);
                        return (
                        <NavLink
                          key={item.path}
                          to={item.path}
                          onClick={onCloseMobile}
                          className={`relative flex items-center gap-2 px-2.5 h-8 rounded-md text-[13px] hover:text-[#12233F] hover:bg-[#F8FAFC] hover:translate-x-1 transition-all duration-200 ${
                            here ? 'text-[#0B1730]' : 'text-[#475569]'
                          }`}
                        >
                          {here && <span aria-hidden className="absolute left-[3px] top-1/2 -translate-y-1/2 w-1 h-1 rounded-full bg-[var(--c)]" />}
                          <span className="truncate flex-1">{item.name}</span>
                          {item.badge !== undefined && (
                            <span className={`text-[10px] font-semibold min-w-[20px] text-center px-1.5 py-0.5 rounded-md flex-shrink-0 ${item.badgeColor ?? 'bg-[#F3E8FF] text-[#7E22CE]'}`}>
                              {item.badge}
                            </span>
                          )}
                        </NavLink>
                        );
                      })}
                    </div>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          <GroupLabel collapsed={collapsed}>Administration</GroupLabel>
          <div className="space-y-0.5 eos-nav-in" style={{ animationDelay: '420ms' }}>{ADMIN_ITEMS.map(topLink)}</div>
        </nav>

        {/* Institutional footer */}
        <div className="px-4 py-3 border-t border-[#E2E8F0] eos-on-dark">
          {!collapsed ? (
            <div className="flex items-center gap-2.5">
              <span className="flex-shrink-0 w-8 h-8 rounded-lg bg-[#EEF2FF] text-[#3730A3] flex items-center justify-center">
                <Landmark className="w-4 h-4" />
              </span>
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-[12px] font-semibold text-[#12233F] truncate">{org.name}</p>
                  {org.connected ? (
                    <span className="inline-flex items-center gap-1.5 text-[10.5px] font-medium text-[#126B3D] whitespace-nowrap">
                      <span className="w-1.5 h-1.5 rounded-full bg-[#16834B] animate-pulse" />
                      Connected
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1.5 text-[10.5px] font-medium text-[#64748B] whitespace-nowrap">
                      <span className="w-1.5 h-1.5 rounded-full bg-[#94A3B8]" />
                      Preview
                    </span>
                  )}
                </div>
                <p className="text-[11px] text-[#64748B] truncate">{org.detail}</p>
              </div>
            </div>
          ) : (
            <div className="flex justify-center" title={org.connected ? 'Connected to the API' : 'Preview'}>
              <span className={`w-2 h-2 rounded-full ${org.connected ? 'bg-[#16834B] animate-pulse' : 'bg-[#94A3B8]'}`} />
            </div>
          )}
        </div>
      </aside>
    </>
  );
};
