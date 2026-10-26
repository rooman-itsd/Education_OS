import type { DashboardWidget } from "@eos/ui-kit";
import { BudgetVsSpend } from "./BudgetVsSpend";
import { MyGrants } from "./MyGrants";
import "./widgets.css";

/**
 * Dashboard widgets exported by budget-grants.
 * Ids are "budget-grants.<widget>". The role layouts in
 * platform/identity/config/dashboards/*.yaml refer to them by id.
 * A widget imports only from this module and packages/, and fetches data
 * through this module's generated API client in ../api.
 *
 * Endpoints and permissions per contracts/openapi.yaml and contracts/permissions.yaml (issue #128).
 */
export const widgets: DashboardWidget[] = [
  {
    id: "budget-grants.budget-vs-spend",
    title: "Budget vs spend",
    permission: "budget-grants:report:read",
    kind: "panel",
    size: "2x1",
    component: BudgetVsSpend,
  },
  {
    id: "budget-grants.my-grants",
    title: "My grants",
    permission: "budget-grants:self:read",
    kind: "list",
    size: "2x1",
    component: MyGrants,
  },
];
