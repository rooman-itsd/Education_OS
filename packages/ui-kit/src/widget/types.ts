import type { ComponentType } from "react";

/** Grid footprint of a widget: a third, two thirds or the full width of the dashboard. */
export type WidgetSize = "1x1" | "2x1" | "2x2" | "full";

/**
 * What a widget is, which decides how the shell lays it out:
 * - `figure`: one key number with its change. Figures are gathered into a stat strip at the top.
 * - `list`: rows of items (queue, upcoming, people). Rendered in a panel.
 * - `table`: a data table. Rendered in a panel, usually two thirds or full width.
 * - `chart`: a chart with a title. Rendered in a panel.
 * - `panel`: anything else, in a plain panel.
 */
export type WidgetKind = "figure" | "list" | "table" | "chart" | "panel";

/**
 * The dashboard widget contract.
 *
 * A module exports an array of these from `frontend/src/widgets/index.ts`.
 * The dashboard shell in apps/frontend knows nothing else about the module.
 */
export interface DashboardWidget {
  /** Globally unique. Convention: `<module>.<widget>`, e.g. `fees-accounts.outstanding-dues`. */
  id: string;
  /** Shown in the widget header (or as the figure label). */
  title: string;
  /** Permission key the viewer must hold, `<module>:<resource>:<action>`. The shell hides the widget otherwise. */
  permission: string;
  size: WidgetSize;
  /** Decides the layout. Defaults to `panel`. */
  kind?: WidgetKind;
  /** Small line under the title in the panel header. */
  subtitle?: string;
  /** Renders the widget body. Fetches its own data through the module's generated API client. */
  component: ComponentType<WidgetProps>;
}

/** Props the shell passes to every widget component. */
export interface WidgetProps {
  /** Role the dashboard is rendered for. */
  role: string;
}

/** Declared in a role layout file, platform/identity/config/dashboards/<role>.yaml. */
export interface RoleLayout {
  role: string;
  title: string;
  /** Another role id whose widgets come first. */
  extends?: string;
  widgets: string[];
}
