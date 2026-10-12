import { FigureStrip, WidgetFrame, type DashboardWidget, type WidgetRegistry } from "@eos/ui-kit";
import { resolveWidgetIds, type LayoutMap } from "./layouts";
import { moduleOfWidget, type Entitlement } from "../tenant/entitlements";

export interface DashboardProps {
  role: string;
  layouts: LayoutMap;
  registry: WidgetRegistry;
  /** Permission keys the viewer holds, or "all" during development. */
  permissions: ReadonlySet<string> | "all";
  /**
   * The organisation's entitlement (ADR-0005). Widgets of modules outside it are shown as
   * locked for an org admin and hidden for everyone else. Omit to treat everything as entitled.
   */
  entitlement?: Entitlement;
  /** Whether the viewer may see locked modules and the upgrade prompt. */
  canUpgrade?: boolean;
  /** Hide the layout title (the page hero already names the dashboard). */
  hideTitle?: boolean;
}

type Placed = { id: string; widget?: DashboardWidget; state: "ready" | "empty" | "locked" };

/**
 * The dashboard shell. Reads the role's layout, looks each widget up in the registry, hides the
 * ones the viewer may not see, then lays the rest out: figures in a stat strip at the top, every
 * other widget in a panel on a twelve-column grid. A widget id with no registered widget renders
 * a placeholder so the gap is visible.
 */
export function Dashboard({ role, layouts, registry, permissions, entitlement, canUpgrade = false, hideTitle = false }: DashboardProps) {
  const layout = layouts[role];
  if (!layout) {
    return (
      <p role="alert" className="eos-dashboard__missing">
        No dashboard layout for role "{role}".
      </p>
    );
  }

  const ids = resolveWidgetIds(role, layouts);
  const allowed = (permission: string) => permissions === "all" || permissions.has(permission);
  const entitled = (id: string) => {
    if (!entitlement) return true;
    const mod = moduleOfWidget(id);
    // Platform services (identity, billing, tenancy, audit, workflow, reporting) are always on.
    return entitlement.moduleNames.has(mod) || !entitlement.upgradableModules.some((m) => m.endsWith("/" + mod));
  };

  const placed: Placed[] = ids.flatMap((id): Placed[] => {
    if (!entitled(id)) return canUpgrade ? [{ id, state: "locked" as const }] : [];
    const widget = registry.get(id);
    if (!widget) return [{ id, state: "empty" as const }];
    if (!allowed(widget.permission)) return [];
    return [{ id, widget, state: "ready" as const }];
  });

  const figures = placed.filter((p) => p.widget?.kind === "figure");
  const panels = placed.filter((p) => p.widget?.kind !== "figure");

  return (
    <section className="eos-dashboard" aria-label={`${layout.title} dashboard`}>
      {!hideTitle && <h1 className="eos-dashboard__title">{layout.title}</h1>}
      {placed.length === 0 ? (
        <p className="eos-dashboard__missing">Nothing to show for this role.</p>
      ) : (
        <>
          {figures.length > 0 && (
            <FigureStrip>
              {figures.map(({ id, widget }) => {
                const Body = widget!.component;
                return <Body key={id} role={role} />;
              })}
            </FigureStrip>
          )}
          {panels.length > 0 && (
            <div className="eos-dashboard__grid">
              {panels.map(({ id, widget, state }) => {
                if (state === "locked") return <WidgetFrame key={id} title={id} size="1x1" state="locked" message="Not in your plan · Upgrade to unlock" />;
                if (!widget) return <WidgetFrame key={id} title={id} size="1x1" state="empty" message="Not built yet" />;
                const Body = widget.component;
                return (
                  <WidgetFrame key={id} title={widget.title} subtitle={widget.subtitle} size={widget.size} kind={widget.kind}>
                    <Body role={role} />
                  </WidgetFrame>
                );
              })}
            </div>
          )}
        </>
      )}
    </section>
  );
}
