import type { DashboardWidget } from "@eos/ui-kit";
import { CollectionsToday } from "./CollectionsToday";
import { CollectionVsTarget } from "./CollectionVsTarget";
import { FeeDue, FeeDues } from "./Dues";
import { OutstandingDues } from "./OutstandingDues";
import "./widgets.css";

/**
 * Dashboard widgets exported by fees-accounts.
 * Ids are "fees-accounts.<widget>". The role layouts in
 * platform/identity/config/dashboards/*.yaml refer to them by id.
 * A widget imports only from this module and packages/, and fetches data
 * through this module's generated API client in ../api.
 *
 * Endpoints and permissions per contracts/openapi.yaml and contracts/permissions.yaml (issue #107).
 */
export const widgets: DashboardWidget[] = [
  {
    id: "fees-accounts.fee-due",
    title: "Fee due",
    permission: "fees-accounts:self:read",
    kind: "list",
    size: "1x1",
    component: FeeDue,
  },
  {
    id: "fees-accounts.fee-dues",
    title: "Fee dues",
    permission: "fees-accounts:self:read",
    kind: "list",
    size: "2x1",
    component: FeeDues,
  },
  {
    id: "fees-accounts.collections-today",
    title: "Collections today",
    permission: "fees-accounts:report:read",
    kind: "panel",
    size: "1x1",
    component: CollectionsToday,
  },
  {
    id: "fees-accounts.outstanding-dues",
    title: "Outstanding dues",
    permission: "fees-accounts:report:read",
    kind: "panel",
    size: "2x1",
    component: OutstandingDues,
  },
  {
    id: "fees-accounts.collection-vs-target",
    title: "Collection vs target",
    permission: "fees-accounts:report:read",
    kind: "panel",
    size: "2x1",
    component: CollectionVsTarget,
  },
];
