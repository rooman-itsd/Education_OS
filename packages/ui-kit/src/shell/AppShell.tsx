import { useState, type ReactNode } from "react";
import { X } from "../icons";
import { Sidebar, type SidebarProps } from "./Sidebar";
import { Topbar, type TopbarProps } from "./Topbar";
import type { ShellOrganisation } from "./types";

export interface NoticeProps {
  children: ReactNode;
  tone?: "positive" | "warning";
  onDismiss?: () => void;
}

/** A one-line announcement under the sidebar: trial end, preview mode, maintenance. */
export function Notice({ children, tone = "positive", onDismiss }: NoticeProps) {
  return (
    <div className={tone === "warning" ? "eos-notice eos-notice--warning" : "eos-notice"} role="status">
      {children}
      {onDismiss && (
        <button type="button" className="eos-notice__close" onClick={onDismiss} aria-label="Dismiss">
          <X />
        </button>
      )}
    </div>
  );
}

export interface AppShellProps {
  sidebar: Omit<SidebarProps, "collapsed" | "onToggleCollapse" | "mobileOpen" | "onCloseMobile" | "organisation">;
  topbar: Omit<TopbarProps, "onToggleMobileMenu">;
  organisation?: ShellOrganisation;
  notice?: ReactNode;
  /** A key that changes with the page, so the content fades in on navigation. */
  pageKey?: string;
  footer?: ReactNode;
  children: ReactNode;
}

/**
 * The frame every signed-in screen shares: dark sidebar, sticky top bar, notice, content column
 * and footer. The role dashboards, the admin console and every module page render inside it.
 */
export function AppShell({ sidebar, topbar, organisation, notice, pageKey, footer, children }: AppShellProps) {
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  return (
    <div className={collapsed ? "eos-shell eos-shell--collapsed" : "eos-shell"}>
      <Sidebar {...sidebar} organisation={organisation} collapsed={collapsed} onToggleCollapse={() => setCollapsed((c) => !c)} mobileOpen={mobileOpen} onCloseMobile={() => setMobileOpen(false)} />
      <div className="eos-shell__main">
        {notice}
        <Topbar {...topbar} onToggleMobileMenu={() => setMobileOpen((o) => !o)} />
        <main className="eos-shell__content">
          <div key={pageKey} className="eos-page-enter">
            {children}
          </div>
        </main>
        {footer !== undefined ? (
          footer
        ) : (
          <footer className="eos-shell__footer">
            <span>© {new Date().getFullYear()} {organisation?.name ?? "Education OS"}</span>
            <span className="eos-shell__footer-meta">
              <span style={{ fontWeight: 500 }}>Education OS</span>
              {organisation?.detail && (
                <>
                  <span aria-hidden>•</span>
                  <span>{organisation.detail}</span>
                </>
              )}
            </span>
          </footer>
        )}
      </div>
    </div>
  );
}
