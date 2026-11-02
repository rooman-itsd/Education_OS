import type { DashboardWidget } from "@eos/ui-kit";
import { MyPortfolioWidget } from "./MyPortfolioWidget";
import { ReviewsPendingWidget } from "./ReviewsPendingWidget";

/**
 * Dashboard widgets exported by practice/portfolio.
 * Ids are referenced in platform/identity/config/dashboards/*.yaml.
 */
export const widgets: DashboardWidget[] = [
  {
    id: "portfolio.my-portfolio",
    title: "My Portfolio",
    permission: "portfolio:item:read",
    size: "1x1",
    kind: "list",
    subtitle: "Your creative works and submissions",
    component: MyPortfolioWidget,
  },
  {
    id: "portfolio.reviews-pending",
    title: "Reviews Pending",
    permission: "portfolio:review:write",
    size: "1x1",
    kind: "list",
    subtitle: "Submissions awaiting your review",
    component: ReviewsPendingWidget,
  },
];
