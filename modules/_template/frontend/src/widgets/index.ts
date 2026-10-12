/**
 * Dashboard widgets this module contributes. The shell in apps/frontend registers them by id and
 * places each by its `kind`: a `figure` joins the key-figure strip at the top, everything else
 * gets a panel on the twelve-column grid. See docs/architecture/frontend-design-system.md.
 *
 * import type { DashboardWidget } from "@eos/ui-kit";
 * import { OutstandingDues } from "./OutstandingDues";     // returns <Figure label=… value=… />
 * import { RecentInvoices } from "./RecentInvoices";       // returns <List>…<ListRow …/></List>
 *
 * export const widgets: DashboardWidget[] = [
 *   { id: "__MODULE_NAME__.outstanding-dues", title: "Outstanding dues", permission: "__MODULE_NAME__:invoice:read", size: "1x1", kind: "figure", component: OutstandingDues },
 *   { id: "__MODULE_NAME__.recent-invoices", title: "Recent invoices", subtitle: "Last 30 days", permission: "__MODULE_NAME__:invoice:read", size: "2x1", kind: "list", component: RecentInvoices },
 * ];
 */
import type { DashboardWidget } from "@eos/ui-kit";

export const widgets: DashboardWidget[] = [];
