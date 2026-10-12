import { useEffect, useState, type CSSProperties, type ReactNode } from "react";
import { ChevronDown, ChevronLeft, ChevronRight, Landmark, Lock } from "../icons";
import { EduMark, Wordmark } from "../components/Wordmark";
import { isNavGroup, type NavGroup, type NavLeaf, type NavSection, type ShellOrganisation } from "./types";

export interface SidebarProps {
  sections: NavSection[];
  /** The current location, matched against each leaf's href. */
  currentHref: string;
  collapsed: boolean;
  onToggleCollapse: () => void;
  mobileOpen: boolean;
  onCloseMobile: () => void;
  organisation?: ShellOrganisation;
  /** Where the brand links to. */
  homeHref?: string;
  /** Renders a leaf's anchor; override to use a router's Link. */
  renderLink?: (leaf: NavLeaf, props: { className: string; children: ReactNode; "aria-current"?: "page"; title?: string; onClick: () => void }) => ReactNode;
}

const sameHref = (current: string, href: string) => current === href || (href.length > 1 && current.startsWith(href + "/"));

function LeafLink({ leaf, current, collapsed, onNavigate, renderLink, child }: { leaf: NavLeaf; current: boolean; collapsed: boolean; onNavigate: () => void; renderLink?: SidebarProps["renderLink"]; child?: boolean }) {
  const className = child ? ["eos-sidebar__child", leaf.locked ? "eos-sidebar__child--locked" : ""].filter(Boolean).join(" ") : "eos-sidebar__item";
  const Icon = leaf.icon;
  const children = child ? (
    <>
      <span className="eos-sidebar__label">{leaf.label}</span>
      {leaf.badge !== undefined && <span className="eos-sidebar__badge">{leaf.badge}</span>}
      {leaf.locked && <Lock aria-label="Not in your plan" />}
    </>
  ) : (
    <>
      {current && <span className="eos-sidebar__indicator eos-bar-in" aria-hidden />}
      {Icon && <Icon className="eos-sidebar__icon" />}
      <span className="eos-sidebar__label">{leaf.label}</span>
      {leaf.badge !== undefined && <span className="eos-sidebar__badge">{leaf.badge}</span>}
    </>
  );
  const props = { className, children, ...(current ? { "aria-current": "page" as const } : {}), title: collapsed ? leaf.label : undefined, onClick: onNavigate };
  if (renderLink) return <>{renderLink(leaf, props)}</>;
  return (
    <a href={leaf.href} className={props.className} aria-current={props["aria-current"]} title={props.title} onClick={onNavigate}>
      {children}
    </a>
  );
}

function Group({ group, currentHref, collapsed, open, onToggle, onNavigate, renderLink }: { group: NavGroup; currentHref: string; collapsed: boolean; open: boolean; onToggle: () => void; onNavigate: () => void; renderLink?: SidebarProps["renderLink"] }) {
  const active = group.items.some((i) => sameHref(currentHref, i.href));
  const Icon = group.icon;
  const style = group.color ? ({ "--nav-color": group.color, "--nav-active": "#fff" } as CSSProperties) : undefined;
  return (
    <div style={style}>
      <button type="button" className="eos-sidebar__item" aria-expanded={open && !collapsed} aria-current={active ? "location" : undefined} title={collapsed ? group.label : undefined} onClick={onToggle}>
        {active && <span className="eos-sidebar__indicator eos-bar-in" aria-hidden />}
        {Icon && <Icon className="eos-sidebar__icon" />}
        <span className="eos-sidebar__label">{group.label}</span>
        <ChevronDown className="eos-sidebar__chevron" />
      </button>
      <div className={open && !collapsed ? "eos-sidebar__children eos-sidebar__children--open" : "eos-sidebar__children"} {...(open && !collapsed ? {} : { inert: "" as unknown as boolean })}>
        <div>
          <div className="eos-sidebar__children-list">
            {group.items.map((leaf) => (
              <LeafLink key={leaf.id} leaf={leaf} current={sameHref(currentHref, leaf.href)} collapsed={collapsed} onNavigate={onNavigate} renderLink={renderLink} child />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * The dark sidebar: brand card, sections of links and folding suite groups, organisation footer.
 * Collapses to icons on desktop and slides in over the page on phones.
 */
export function Sidebar({ sections, currentHref, collapsed, onToggleCollapse, mobileOpen, onCloseMobile, organisation, homeHref = "/", renderLink }: SidebarProps) {
  const activeGroup = sections.flatMap((s) => s.entries).find((e): e is NavGroup => isNavGroup(e) && e.items.some((i) => sameHref(currentHref, i.href)));
  const [open, setOpen] = useState<Record<string, boolean>>(() => (activeGroup ? { [activeGroup.id]: true } : {}));
  useEffect(() => {
    if (activeGroup) setOpen((o) => (o[activeGroup.id] ? o : { ...o, [activeGroup.id]: true }));
  }, [activeGroup]);

  const toggle = (id: string) => {
    if (collapsed) onToggleCollapse();
    setOpen((o) => ({ ...o, [id]: collapsed ? true : !o[id] }));
  };

  return (
    <>
      {mobileOpen && <div className="eos-sidebar-backdrop" onClick={onCloseMobile} aria-hidden />}
      <aside className={["eos-sidebar", collapsed ? "eos-sidebar--collapsed" : "", mobileOpen ? "eos-sidebar--open" : ""].filter(Boolean).join(" ")}>
        <div className="eos-sidebar__brand">
          <a className="eos-sidebar__brand-link" href={homeHref} title="Education OS">
            <EduMark size={36} />
            {!collapsed && <Wordmark />}
          </a>
          <button type="button" className="eos-sidebar__collapse" onClick={onToggleCollapse} aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}>
            {collapsed ? <ChevronRight /> : <ChevronLeft />}
          </button>
        </div>
        <nav className="eos-sidebar__nav" aria-label="Main">
          {sections.map((section, si) => (
            <div key={section.label ?? si} className="eos-nav-in" style={{ animationDelay: `${60 + si * 60}ms` }}>
              {section.label && <div className="eos-sidebar__group">{section.label}</div>}
              {section.entries.map((entry) =>
                isNavGroup(entry) ? (
                  <Group key={entry.id} group={entry} currentHref={currentHref} collapsed={collapsed} open={Boolean(open[entry.id])} onToggle={() => toggle(entry.id)} onNavigate={onCloseMobile} renderLink={renderLink} />
                ) : (
                  <LeafLink key={entry.id} leaf={entry} current={sameHref(currentHref, entry.href)} collapsed={collapsed} onNavigate={onCloseMobile} renderLink={renderLink} />
                ),
              )}
            </div>
          ))}
        </nav>
        {organisation && (
          <div className="eos-sidebar__foot">
            <span className="eos-sidebar__foot-tile" aria-hidden>
              <Landmark />
            </span>
            <div className="eos-sidebar__foot-text">
              <div className="eos-sidebar__foot-name">
                <span>{organisation.name}</span>
                <span className={organisation.connected ? "eos-status-dot eos-status-dot--live" : "eos-status-dot"}>{organisation.connected ? "Connected" : "Preview"}</span>
              </div>
              {organisation.detail && <div className="eos-sidebar__foot-detail">{organisation.detail}</div>}
            </div>
          </div>
        )}
      </aside>
    </>
  );
}
