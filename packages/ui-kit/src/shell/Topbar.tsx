import { Fragment, useEffect, useRef, useState, type ReactNode } from "react";
import { Bell, HelpCircle, LogOut, Menu, Search, User as UserIcon, X } from "../icons";
import type { Crumb, SearchResult, ShellUser } from "./types";

export interface TopbarProps {
  crumbs: Crumb[];
  user?: ShellUser;
  /** Pages and modules the search dialog offers; empty hides the search. */
  search?: SearchResult[];
  searchPlaceholder?: string;
  onNavigate: (href: string) => void;
  onToggleMobileMenu: () => void;
  onSignOut?: () => void;
  onOpenProfile?: () => void;
  /** Items in the notifications menu; omit to hide the bell. */
  notifications?: { id: string; title: string; detail?: string; time?: string; tone?: "success" | "warning" | "danger" }[];
  notificationsFooter?: ReactNode;
  /** Shown instead of the account menu, e.g. a role switcher in preview. */
  accountSlot?: ReactNode;
  onHelp?: () => void;
}

const initialsOf = (name: string) =>
  name
    .split(/[\s@.]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((w) => w[0]!.toUpperCase())
    .join("") || "U";

/** The sticky top bar: menu button, breadcrumb, search, help, notifications and the account menu. */
export function Topbar({ crumbs, user, search = [], searchPlaceholder = "Search pages and modules…", onNavigate, onToggleMobileMenu, onSignOut, onOpenProfile, notifications, notificationsFooter, accountSlot, onHelp }: TopbarProps) {
  const [query, setQuery] = useState("");
  const [showSearch, setShowSearch] = useState(false);
  const [showNotifications, setShowNotifications] = useState(false);
  const [showAccount, setShowAccount] = useState(false);
  const notifRef = useRef<HTMLDivElement>(null);
  const accountRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onDown = (e: MouseEvent) => {
      if (notifRef.current && !notifRef.current.contains(e.target as Node)) setShowNotifications(false);
      if (accountRef.current && !accountRef.current.contains(e.target as Node)) setShowAccount(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k" && search.length) {
        e.preventDefault();
        setShowSearch((s) => !s);
      }
      if (e.key === "Escape") setShowSearch(false);
    };
    document.addEventListener("mousedown", onDown);
    window.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      window.removeEventListener("keydown", onKey);
    };
  }, [search.length]);

  const q = query.trim().toLowerCase();
  const results = search.filter((r) => !q || r.label.toLowerCase().includes(q) || (r.hint ?? "").toLowerCase().includes(q)).slice(0, 8);
  const open = (href: string) => {
    setShowSearch(false);
    setQuery("");
    onNavigate(href);
  };

  return (
    <>
      <header className="eos-topbar">
        <div className="eos-topbar__left">
          <button type="button" className="eos-btn eos-btn--ghost eos-btn--icon eos-topbar__menu" onClick={onToggleMobileMenu} aria-label="Open navigation menu">
            <Menu />
          </button>
          <nav className="eos-breadcrumb" aria-label="Breadcrumb">
            {crumbs.map((c, i) => (
              <Fragment key={i}>
                {i > 0 && <span className="eos-breadcrumb__sep">/</span>}
                {c.href && i < crumbs.length - 1 ? (
                  <a
                    href={c.href}
                    onClick={(e) => {
                      e.preventDefault();
                      onNavigate(c.href!);
                    }}
                  >
                    {c.label}
                  </a>
                ) : (
                  <span className={i === crumbs.length - 1 ? "eos-breadcrumb__current" : undefined}>{c.label}</span>
                )}
              </Fragment>
            ))}
          </nav>
        </div>

        {search.length > 0 && (
          <div className="eos-topbar__search">
            <button type="button" className="eos-search-trigger" onClick={() => setShowSearch(true)}>
              <span style={{ display: "inline-flex", alignItems: "center", gap: 8, minWidth: 0 }}>
                <Search />
                <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{searchPlaceholder}</span>
              </span>
              <kbd className="eos-kbd">Ctrl K</kbd>
            </button>
          </div>
        )}

        <div className="eos-topbar__right">
          {search.length > 0 && (
            <button type="button" className="eos-btn eos-btn--ghost eos-btn--icon" style={{ display: "inline-flex" }} onClick={() => setShowSearch(true)} aria-label="Search">
              <Search />
            </button>
          )}
          {onHelp && (
            <button type="button" className="eos-btn eos-btn--ghost eos-btn--icon" onClick={onHelp} aria-label="Help">
              <HelpCircle />
            </button>
          )}
          {notifications && (
            <div style={{ position: "relative" }} ref={notifRef}>
              <button type="button" className="eos-btn eos-btn--ghost eos-btn--icon" style={{ position: "relative" }} onClick={() => setShowNotifications((s) => !s)} aria-label={`Notifications, ${notifications.length}`} aria-expanded={showNotifications}>
                <Bell />
                {notifications.length > 0 && <span className="eos-dot-badge eos-pulse" aria-hidden />}
              </button>
              {showNotifications && (
                <div className="eos-menu eos-menu--wide" role="menu">
                  <div className="eos-menu__head" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <b>Notifications</b>
                    <button type="button" className="eos-panel-link" onClick={() => setShowNotifications(false)}>
                      Close
                    </button>
                  </div>
                  <ul className="eos-list eos-list--divided" style={{ maxHeight: 320, overflowY: "auto", padding: "0 14px" }}>
                    {notifications.map((n) => (
                      <li key={n.id} style={{ padding: "10px 0" }}>
                        <span className="eos-row__title">{n.title}</span>
                        {n.detail && <span className="eos-row__meta" style={{ whiteSpace: "normal" }}>{n.detail}</span>}
                        {n.time && <span className="eos-row__meta">{n.time}</span>}
                      </li>
                    ))}
                    {notifications.length === 0 && <li className="eos-list__empty">Nothing new.</li>}
                  </ul>
                  {notificationsFooter && <div className="eos-menu__foot">{notificationsFooter}</div>}
                </div>
              )}
            </div>
          )}
          {accountSlot}
          {user && (
            <div style={{ position: "relative" }} ref={accountRef}>
              <button type="button" className="eos-topbar__account" onClick={() => setShowAccount((s) => !s)} aria-haspopup="menu" aria-expanded={showAccount}>
                <span className="eos-topbar__account-text">
                  <span className="eos-topbar__account-name" style={{ display: "block" }}>
                    {user.name}
                  </span>
                  {user.role && (
                    <span className="eos-topbar__account-role" style={{ display: "block" }}>
                      {user.role}
                    </span>
                  )}
                </span>
                <span className="eos-avatar" aria-hidden>
                  {user.photo ? <img src={user.photo} alt="" style={{ width: "100%", height: "100%", objectFit: "cover" }} /> : user.initials ?? initialsOf(user.name)}
                </span>
              </button>
              {showAccount && (
                <div className="eos-menu" role="menu">
                  <div className="eos-menu__head">
                    <b>{user.name}</b>
                    {user.email && <span>{user.email}</span>}
                  </div>
                  {onOpenProfile && (
                    <button
                      type="button"
                      className="eos-menu__item"
                      role="menuitem"
                      onClick={() => {
                        setShowAccount(false);
                        onOpenProfile();
                      }}
                    >
                      <UserIcon />
                      Profile
                    </button>
                  )}
                  {onSignOut && (
                    <>
                      <div className="eos-menu__sep" />
                      <button
                        type="button"
                        className="eos-menu__item eos-menu__item--danger"
                        role="menuitem"
                        onClick={() => {
                          setShowAccount(false);
                          onSignOut();
                        }}
                      >
                        <LogOut />
                        Sign out
                      </button>
                    </>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      </header>

      {showSearch && (
        <div className="eos-dialog-backdrop" onMouseDown={(e) => e.target === e.currentTarget && setShowSearch(false)}>
          <div className="eos-dialog" role="dialog" aria-label="Search">
            <div className="eos-dialog__search">
              <Search />
              <input autoFocus placeholder={searchPlaceholder} value={query} onChange={(e) => setQuery(e.target.value)} onKeyDown={(e) => e.key === "Enter" && results[0] && open(results[0].href)} />
              <button type="button" className="eos-btn eos-btn--ghost eos-btn--icon eos-btn--sm" onClick={() => setShowSearch(false)} aria-label="Close search">
                <X />
              </button>
            </div>
            <div className="eos-dialog__list">
              <div className="eos-dialog__group">{q ? "Results" : "Quick navigation"}</div>
              {results.map((r) => (
                <button key={r.href} type="button" className="eos-dialog__result" onClick={() => open(r.href)}>
                  <span style={{ display: "inline-flex", alignItems: "center", minWidth: 0 }}>
                    {r.tag && <span className="eos-dialog__result-tag">{r.tag}</span>}
                    <span style={{ fontWeight: 500, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.label}</span>
                  </span>
                  <span style={{ color: "var(--eos-text-3)", fontSize: "var(--eos-text-xs)" }}>Jump</span>
                </button>
              ))}
              {results.length === 0 && <p className="eos-list__empty">No page or module matches "{query}".</p>}
            </div>
            <div className="eos-dialog__foot">
              <span>Pages and modules</span>
              <span>Esc to close</span>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
