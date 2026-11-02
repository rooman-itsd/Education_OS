import type { DashboardWidget } from "@eos/ui-kit";
import { AppointmentsToday } from "./AppointmentsToday";
import { AthletesOnPlans } from "./AthletesOnPlans";
import { InjuredAthletes } from "./InjuredAthletes";
import { NutritionPlan } from "./NutritionPlan";
import { PlanReviewsDue } from "./PlanReviewsDue";
import "./widgets.css";

/**
 * Dashboard widgets exported by sports-nutrition-health.
 * Ids are "sports-nutrition-health.<widget>". The role layouts in
 * platform/identity/config/dashboards/*.yaml refer to them by id.
 * A widget imports only from this module and packages/, and fetches data
 * through this module's API client in ../api.
 *
 * Endpoints and permissions per contracts/openapi.yaml and contracts/permissions.yaml. Athletes are shown by short
 * id: this module references them by id only and has no endpoint that names them. No widget shows clinical notes.
 */
export const widgets: DashboardWidget[] = [
  {
    id: "sports-nutrition-health.nutrition-plan",
    title: "Nutrition plan",
    permission: "sports-nutrition-health:plan:read",
    kind: "panel",
    size: "1x1",
    subtitle: "Your active plan and next review",
    component: NutritionPlan,
  },
  {
    id: "sports-nutrition-health.injured-athletes",
    title: "Injured athletes",
    permission: "sports-nutrition-health:injury:read",
    kind: "list",
    size: "2x1",
    subtitle: "Active and recovering, with expected return",
    component: InjuredAthletes,
  },
  {
    id: "sports-nutrition-health.appointments-today",
    title: "Appointments today",
    permission: "sports-nutrition-health:appointment:read",
    kind: "list",
    size: "1x1",
    subtitle: "Physiotherapy, medical and nutrition",
    component: AppointmentsToday,
  },
  {
    id: "sports-nutrition-health.athletes-on-plans",
    title: "Athletes on plans",
    permission: "sports-nutrition-health:plan:read",
    kind: "list",
    size: "1x1",
    subtitle: "Active nutrition plans",
    component: AthletesOnPlans,
  },
  {
    id: "sports-nutrition-health.plan-reviews-due",
    title: "Plan reviews due",
    permission: "sports-nutrition-health:plan:read",
    kind: "list",
    size: "1x1",
    subtitle: "Overdue and due this week",
    component: PlanReviewsDue,
  },
];
