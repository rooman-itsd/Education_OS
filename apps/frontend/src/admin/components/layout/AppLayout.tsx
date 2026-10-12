import React, { useState } from 'react';
import { Link, Outlet, useLocation } from '../../lib/router';
import { X } from '../../lib/icons';
import { Sidebar } from './Sidebar';
import { Topbar } from './Topbar';
import { useOrganisation } from '../../lib/organisation';
import { useAuth } from '../../lib/auth';

export const AppLayout: React.FC = () => {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [showNotice, setShowNotice] = useState(true);
  const location = useLocation();
  const org = useOrganisation();
  const { session, preview } = useAuth();
  // A real notice: the organisation's trial end, or that preview shows sample data. None for a super admin.
  const trialEnds = session?.trialEndsAt ? new Date(session.trialEndsAt).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : null;
  const notice = trialEnds
    ? { text: `Trial ends ${trialEnds} · ${org.detail}`, link: { to: '/modules', label: 'See what your plan includes →' } }
    : preview || !session
      ? { text: 'Preview mode: sample data, no API connected.', link: null }
      : null;

  return (
    <div className="min-h-screen bg-[#F6F8FB] flex flex-col font-sans">
      {/* Sidebar */}
      <Sidebar
        collapsed={sidebarCollapsed}
        onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
        mobileOpen={mobileMenuOpen}
        onCloseMobile={() => setMobileMenuOpen(false)}
      />

      {/* Main Content Area */}
      <div
        className={`flex-1 flex flex-col transition-all duration-300 ease-in-out ${
          sidebarCollapsed ? 'lg:pl-[72px]' : 'lg:pl-[260px]'
        }`}
      >
        {/* Announcement bar (positive green) */}
        {showNotice && notice && (
          <div className="relative bg-[#08875D] text-white text-[13px] font-medium px-10 py-2 text-center">
            {notice.text}{' '}
            {notice.link && (
              <Link to={notice.link.to} className="underline underline-offset-2 font-semibold hover:text-[#D1FAE5]">{notice.link.label}</Link>
            )}
            <button
              onClick={() => setShowNotice(false)}
              aria-label="Dismiss announcement"
              className="absolute right-3 top-1/2 -translate-y-1/2 w-6 h-6 rounded-full flex items-center justify-center hover:bg-white/15"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        )}
        <Topbar onToggleMobileMenu={() => setMobileMenuOpen(!mobileMenuOpen)} />

        <main className="flex-1 p-4 sm:p-6 max-w-7xl w-full mx-auto">
          <div key={location.pathname} className="page-enter"><Outlet /></div>
        </main>

        <footer className="py-4 px-6 border-t border-[#E2E8F0] text-center text-xs text-[#475569] flex flex-col sm:flex-row items-center justify-between gap-2">
          <span>
            © 2026 {org.name}. All rights reserved.
          </span>
          <div className="flex items-center gap-4 text-[11px]">
            <span className="text-[#64748B] font-medium">Education OS</span>
            <span className="text-[#CBD5E1]">•</span>
            <span>{org.detail}</span>
          </div>
        </footer>
      </div>
    </div>
  );
};
