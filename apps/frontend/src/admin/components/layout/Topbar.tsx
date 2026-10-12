import React, { useState, useRef, useEffect } from 'react';
import { useLocation, useNavigate, Link } from '../../lib/router';
import {
  Menu,
  Search,
  Bell,
  HelpCircle,
  ChevronDown,
  User as UserIcon,
  Shield,
  KeyRound,
  LogOut,
  CheckCircle2,
  AlertTriangle,
  Clock,
  X,
  Building
} from '../../lib/icons';
import { MOCK_ALERTS } from '../../data/mockData';
import { useAuth } from '../../lib/auth';
import { useLocalProfile } from '../../lib/profileStore';
import { ALL_MODULES, findModule, findSuite, moduleHref } from '../../data/architecture';

interface TopbarProps {
  onToggleMobileMenu: () => void;
}

const SEARCH_PAGES = [
  { label: 'Dashboard', hint: 'dashboard', to: '/dashboard', tag: 'NAV' },
  { label: 'Users & Access', hint: 'users', to: '/users', tag: 'NAV' },
  { label: 'Roles & Permissions', hint: 'roles permissions keys', to: '/roles', tag: 'NAV' },
  { label: 'Role Dashboards', hint: 'dashboards layouts widgets', to: '/dashboards', tag: 'NAV' },
  { label: 'Module Registry', hint: 'modules entitlement', to: '/modules', tag: 'NAV' },
  { label: 'Audit Log', hint: 'audit events', to: '/audit-logs', tag: 'NAV' },
  { label: 'My Profile', hint: 'profile account security', to: '/profile', tag: 'NAV' },
  { label: 'Role & Access', hint: 'role access permissions api', to: '/access', tag: 'NAV' }
];

export const Topbar: React.FC<TopbarProps> = ({ onToggleMobileMenu }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const { session, signOut } = useAuth();
  // The signed-in admin; preview keeps the design's placeholder.
  const me = session?.me;
  // Display name and photo from My Profile (saved on this device), else the account name.
  const [localProfile] = useLocalProfile(me?.id ?? 'preview');
  const fullName = [localProfile.firstName, localProfile.lastName].filter(Boolean).join(' ');
  const userName = localProfile.displayName || fullName || me?.name || me?.email || 'Administrator';
  const userRole = me ? (me.is_super_admin ? 'Super Admin' : 'Organisation Admin') : 'Preview';
  const initials = userName.split(/[\s@.]+/).filter(Boolean).slice(0, 2).map((w) => w[0]!.toUpperCase()).join('') || 'AD';

  const [searchQuery, setSearchQuery] = useState('');
  const [showSearchModal, setShowSearchModal] = useState(false);
  const [showNotifications, setShowNotifications] = useState(false);
  const [showProfileMenu, setShowProfileMenu] = useState(false);
  const [showHelpModal, setShowHelpModal] = useState(false);

  const q = searchQuery.trim().toLowerCase();
  const searchResults = [
    ...SEARCH_PAGES,
    ...ALL_MODULES.map((m) => ({ label: m.name, hint: m.id, to: moduleHref(m), tag: m.kind === 'feature' ? 'MOD' : m.kind === 'platform' ? 'SVC' : 'INT' }))
  ]
    .filter((r) => !q || r.label.toLowerCase().includes(q) || r.hint.includes(q))
    .slice(0, 8);
  const openResult = (to: string) => {
    setShowSearchModal(false);
    setSearchQuery('');
    navigate(to);
  };

  const notificationRef = useRef<HTMLDivElement>(null);
  const profileRef = useRef<HTMLDivElement>(null);

  // Close dropdowns on outside click
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (notificationRef.current && !notificationRef.current.contains(event.target as Node)) {
        setShowNotifications(false);
      }
      if (profileRef.current && !profileRef.current.contains(event.target as Node)) {
        setShowProfileMenu(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Quick keyboard shortcut for search
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setShowSearchModal((prev) => !prev);
      }
      if (e.key === 'Escape') {
        setShowSearchModal(false);
        setShowHelpModal(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Dynamic breadcrumb generation
  const getBreadcrumbs = () => {
    const path = location.pathname;
    if (path === '/dashboard') return [{ label: 'Education OS', to: '/dashboard' }, { label: 'Dashboard' }];
    if (path === '/users') return [{ label: 'Administration' }, { label: 'Users & Access' }];
    if (path === '/roles') return [{ label: 'Administration' }, { label: 'Roles & Permissions' }];
    if (path === '/admissions') return [{ label: 'Student Lifecycle', to: '/modules/admissions' }, { label: 'Admissions Workflow' }];
    if (path === '/audit-logs') return [{ label: 'Administration' }, { label: 'Audit Log' }];
    if (path === '/profile') return [{ label: 'Account' }, { label: 'My Profile' }];
    if (path === '/access') return [{ label: 'Account' }, { label: 'Role & Access' }];
    if (path === '/dashboards') return [{ label: 'Administration' }, { label: 'Role Dashboards' }];
    if (path === '/modules') return [{ label: 'Administration' }, { label: 'Module Registry' }];
    if (path.startsWith('/modules/')) {
      const mod = findModule(path.replace('/modules/', ''));
      return [
        { label: (mod && findSuite(mod.suiteId)?.name) ?? 'Module Registry', to: '/modules' },
        { label: mod?.name ?? 'Unknown module' }
      ];
    }
    return [{ label: 'Education OS', to: '/dashboard' }];
  };

  const breadcrumbs = getBreadcrumbs();

  return (
    <>
      <header className="sticky top-0 z-30 h-16 bg-white/80 backdrop-blur-xl border-b border-[#E2E8F0] flex items-center justify-between px-4 sm:px-6">
        {/* Left: Mobile Toggle & Breadcrumbs */}
        <div className="flex items-center gap-3 sm:gap-4 min-w-0">
          <button
            onClick={onToggleMobileMenu}
            className="lg:hidden p-2 rounded-md text-[#475569] hover:text-[#12233F] hover:bg-[#F1F5F9]"
            aria-label="Open navigation menu"
          >
            <Menu className="w-5 h-5" />
          </button>

          <nav className="flex items-center gap-1.5 text-xs text-[#475569] truncate">
            {breadcrumbs.map((crumb, idx) => (
              <React.Fragment key={idx}>
                {idx > 0 && <span className="text-[#64748B]">/</span>}
                {crumb.to && idx < breadcrumbs.length - 1 ? (
                  <Link to={crumb.to} className="hover:text-[#7E22CE] transition-colors truncate">
                    {crumb.label}
                  </Link>
                ) : (
                  <span className="font-semibold text-[#12233F] truncate">{crumb.label}</span>
                )}
              </React.Fragment>
            ))}
          </nav>
        </div>

        {/* Center: Global Search Bar */}
        <div className="hidden md:flex items-center flex-1 max-w-md mx-6">
          <button
            onClick={() => setShowSearchModal(true)}
            className="w-full flex items-center justify-between px-4 py-2 rounded-xl bg-white border border-[#E2E8F0] hover:border-[#CBD5E1] text-xs text-[#475569] shadow-[0_4px_14px_-10px_rgba(60,80,140,0.4)] transition-colors focus:outline-none"
          >
            <div className="flex items-center gap-2 truncate">
              <Search className="w-3.5 h-3.5 text-[#475569]" />
              <span className="truncate">Search pages and modules...</span>
            </div>
            <kbd className="hidden sm:inline-flex items-center gap-0.5 text-[10px] uppercase font-mono px-1.5 py-0.5 rounded-full bg-[#F6F8FB] text-[#475569]">
              Ctrl K
            </kbd>
          </button>
        </div>

        {/* Right: Actions, Notifications, Help, Profile */}
        <div className="flex items-center gap-2 sm:gap-3">
          {/* Mobile search trigger */}
          <button
            onClick={() => setShowSearchModal(true)}
            className="md:hidden p-2 rounded-md text-[#475569] hover:text-[#12233F] hover:bg-[#F1F5F9]"
            aria-label="Search"
          >
            <Search className="w-4 h-4" />
          </button>

          {/* Help Button */}
          <button
            onClick={() => setShowHelpModal(true)}
            className="p-2 rounded-md text-[#475569] hover:text-[#12233F] hover:bg-[#F1F5F9] transition-colors"
            title="Institutional Help & Knowledge Base"
          >
            <HelpCircle className="w-4.5 h-4.5" />
          </button>

          {/* Notifications Dropdown */}
          <div className="relative" ref={notificationRef}>
            <button
              onClick={() => setShowNotifications(!showNotifications)}
              className="relative p-2 rounded-md text-[#475569] hover:text-[#12233F] hover:bg-[#F1F5F9] transition-colors"
              title="Notifications"
            >
              <Bell className="w-4.5 h-4.5" />
              <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-[#DC2626] ring-2 ring-[#F6F8FB] animate-pulse" />
            </button>

            {showNotifications && (
              <div className="absolute right-0 mt-2 w-80 sm:w-96 rounded-xl bg-[#FFFFFF] border border-[#E2E8F0] shadow-xl py-2 z-50">
                <div className="flex items-center justify-between px-4 py-2 border-b border-[#E2E8F0]">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-xs text-[#12233F]">Notifications</span>
                    <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-[#EBDCFE] text-[#6B21A8]">
                      {MOCK_ALERTS.length} sample
                    </span>
                  </div>
                  <button
                    onClick={() => setShowNotifications(false)}
                    className="text-[11px] text-[#7E22CE] hover:underline font-medium"
                  >
                    Close
                  </button>
                </div>

                <div className="max-h-80 overflow-y-auto divide-y divide-[#F1F5F9]">
                  {MOCK_ALERTS.map((alert) => (
                    <div key={alert.id} className="p-3 hover:bg-[#F6F8FB] transition-colors flex items-start gap-3">
                      <div className="mt-0.5">
                        {alert.severity === 'critical' ? (
                          <span className="flex items-center justify-center w-6 h-6 rounded-full bg-[#DC262626] text-[#B91C1C]">
                            <AlertTriangle className="w-3.5 h-3.5" />
                          </span>
                        ) : alert.severity === 'warning' ? (
                          <span className="flex items-center justify-center w-6 h-6 rounded-full bg-[#FEF3E2] text-[#8A4F00]">
                            <Clock className="w-3.5 h-3.5" />
                          </span>
                        ) : (
                          <span className="flex items-center justify-center w-6 h-6 rounded-full bg-[#16834B26] text-[#126B3D]">
                            <CheckCircle2 className="w-3.5 h-3.5" />
                          </span>
                        )}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-xs font-semibold text-[#12233F] truncate">{alert.title}</p>
                        <p className="text-[11px] text-[#475569] line-clamp-2 mt-0.5">{alert.subtitle}</p>
                        <span className="text-[10px] text-[#64748B] mt-1 block">{alert.timestamp}</span>
                      </div>
                    </div>
                  ))}
                </div>

                <div className="px-4 py-2 border-t border-[#E2E8F0] bg-[#F6F8FB] text-center text-[11px] text-[#475569]">
                  Sample notices: platform/notification is not built yet.
                </div>
              </div>
            )}
          </div>

          {/* Profile Menu Dropdown */}
          <div className="relative pl-1 border-l border-[#E2E8F0]" ref={profileRef}>
            <button
              onClick={() => setShowProfileMenu(!showProfileMenu)}
              className="flex items-center gap-2.5 p-1.5 rounded-lg hover:bg-[#F1F5F9] transition-colors text-left"
            >
              <div className="hidden sm:block text-right">
                <div className="text-xs font-semibold text-[#12233F] leading-tight">{userName}</div>
                <div className="text-[11px] text-[#475569] leading-tight">{userRole}</div>
              </div>
              <div className="w-8 h-8 rounded-full bg-[#D03F1B] text-white flex items-center justify-center font-semibold text-xs overflow-hidden">
                {localProfile.photo ? <img src={localProfile.photo} alt="" className="w-full h-full" style={{ objectFit: 'cover' }} /> : initials}
              </div>
              <ChevronDown className="w-3.5 h-3.5 text-[#475569]" />
            </button>

            {showProfileMenu && (
              <div className="absolute right-0 mt-2 w-56 rounded-xl bg-[#FFFFFF] border border-[#E2E8F0] shadow-xl py-1.5 z-50">
                <div className="px-3.5 py-2.5 border-b border-[#E2E8F0] bg-[#F6F8FB]">
                  <p className="text-xs font-semibold text-[#12233F]">{userName}</p>
                  <p className="text-[11px] text-[#475569] truncate">{me?.email ?? 'admin@example.org'}</p>
                  <div className="mt-1.5 inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[10px] font-medium bg-[#EBDCFE] text-[#6B21A8]">
                    <Shield className="w-3 h-3" />
                    {me?.is_super_admin ? 'Super admin · platform' : me ? 'Organisation admin' : 'Preview'}
                  </div>
                </div>

                <div className="py-1">
                  <button
                    onClick={() => { setShowProfileMenu(false); navigate('/profile'); }}
                    className="w-full flex items-center gap-2.5 px-3.5 py-2 text-xs text-[#12233F] hover:bg-[#F1F5F9] transition-colors"
                  >
                    <UserIcon className="w-3.5 h-3.5 text-[#475569]" />
                    <span>Profile</span>
                  </button>
                  <button
                    onClick={() => { setShowProfileMenu(false); navigate('/access'); }}
                    className="w-full flex items-center gap-2.5 px-3.5 py-2 text-xs text-[#12233F] hover:bg-[#F1F5F9] transition-colors"
                  >
                    <Shield className="w-3.5 h-3.5 text-[#475569]" />
                    <span>Role & Access</span>
                  </button>
                  <button
                    onClick={() => { setShowProfileMenu(false); navigate('/profile'); }}
                    className="w-full flex items-center gap-2.5 px-3.5 py-2 text-xs text-[#12233F] hover:bg-[#F1F5F9] transition-colors"
                  >
                    <KeyRound className="w-3.5 h-3.5 text-[#475569]" />
                    <span>Security & Audit</span>
                  </button>
                </div>

                <div className="border-t border-[#E2E8F0] pt-1">
                  <button
                    onClick={() => { setShowProfileMenu(false); signOut(); navigate('/login', { replace: true }); }}
                    className="w-full flex items-center gap-2.5 px-3.5 py-2 text-xs text-[#B91C1C] hover:bg-[#DC262626]/40 transition-colors font-medium"
                  >
                    <LogOut className="w-3.5 h-3.5" />
                    <span>Logout</span>
                  </button>
                </div>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* Global Search Dialog Modal */}
      {showSearchModal && (
        <div className="fixed inset-0 z-50 bg-black/30 backdrop-blur-xs flex items-start justify-center pt-20 px-4" onMouseDown={(e) => e.target === e.currentTarget && setShowSearchModal(false)}>
          <div className="w-full max-w-xl bg-[#FFFFFF] rounded-xl shadow-2xl border border-[#E2E8F0] overflow-hidden">
            <div className="flex items-center px-4 py-3 border-b border-[#E2E8F0] gap-3">
              <Search className="w-4 h-4 text-[#475569]" />
              <input
                type="text"
                autoFocus
                placeholder="Search pages and modules..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && searchResults[0] && openResult(searchResults[0].to)}
                className="w-full text-sm text-[#12233F] bg-transparent placeholder-[#64748B] focus:outline-none"
              />
              <button
                onClick={() => setShowSearchModal(false)}
                className="p-1 rounded text-[#64748B] hover:text-[#12233F]"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-3 max-h-80 overflow-y-auto space-y-2">
              <div className="text-[11px] font-semibold uppercase text-[#475569] px-2">{q ? 'Results' : 'Quick Navigation'}</div>
              {searchResults.map((r) => (
                <button
                  key={r.to}
                  onClick={() => openResult(r.to)}
                  className="w-full flex items-center justify-between p-2 rounded-lg hover:bg-[#F1F5F9] text-left text-xs"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <span className={`p-1 rounded font-medium text-[10px] ${r.tag === 'NAV' ? 'bg-[#E7F4EC] text-[#126B3D]' : 'bg-[#EBDCFE] text-[#6B21A8]'}`}>{r.tag}</span>
                    <span className="font-medium text-[#12233F] truncate">{r.label}</span>
                  </div>
                  <span className="text-[11px] text-[#475569]">Jump →</span>
                </button>
              ))}
              {searchResults.length === 0 && <p className="px-2 py-3 text-xs text-[#475569]">No page or module matches "{searchQuery}".</p>}
            </div>

            <div className="px-4 py-2 border-t border-[#E2E8F0] bg-[#F6F8FB] flex items-center justify-between text-[11px] text-[#475569]">
              <span>Searches pages and modules. Record search needs platform/search (not built).</span>
              <span>ESC to close</span>
            </div>
          </div>
        </div>
      )}

      {/* Institutional Help Modal */}
      {showHelpModal && (
        <div className="fixed inset-0 z-50 bg-black/30 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="w-full max-w-lg bg-[#FFFFFF] rounded-xl shadow-2xl border border-[#E2E8F0] p-6 space-y-4">
            <div className="flex items-center justify-between border-b border-[#E2E8F0] pb-3">
              <div className="flex items-center gap-2.5">
                <div className="p-2 rounded-lg bg-[#EBDCFE] text-[#6B21A8]">
                  <Building className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="font-semibold text-sm text-[#12233F]">Education OS Help & Documentation</h3>
                  <p className="text-xs text-[#475569]">Admin console</p>
                </div>
              </div>
              <button onClick={() => setShowHelpModal(false)} className="text-[#475569] hover:text-[#12233F]">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-3 text-xs text-[#12233F]">
              <p>
                Welcome to the <strong>Education OS admin console</strong>. Education OS is one multi-tenant platform: each organisation registers, picks its academy type and plan, and sees only its own data.
              </p>
              <div className="p-3 rounded-lg bg-[#F1F5F9] border border-[#E2E8F0] space-y-1.5">
                <div className="font-semibold text-[#7E22CE]">Active MVP Screens:</div>
                <ul className="list-disc list-inside space-y-1 text-[#475569]">
                  <li><strong>Dashboard:</strong> KPIs, trends, approval queues and upcoming items (sample data).</li>
                  <li><strong>Users & Access:</strong> Multi-department directory with sliding details drawer.</li>
                  <li><strong>Roles & Permissions:</strong> Roles from the academy profile and the permission keys each module defines.</li>
                  <li><strong>Admissions:</strong> Applicant review screen (sample data; the admissions module is not built yet).</li>
                  <li><strong>Role Dashboards, Module Registry, My Profile:</strong> layouts, entitlement and your account, from the repo and the API.</li>
                  <li><strong>Audit Activity:</strong> Sample events using the repo's event names; the platform/audit API is not built yet.</li>
                </ul>
              </div>
              <p className="text-[11px] text-[#475569]">
                For assistance, contact your organisation admin, or the platform operator (super admin).
              </p>
            </div>

            <div className="flex justify-end pt-2">
              <button
                onClick={() => setShowHelpModal(false)}
                className="px-4 py-2 rounded-lg bg-[#12233F] text-white font-medium text-xs hover:bg-[#12233F] transition-colors"
              >
                Close Window
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
