// Super admin calls to platform/billing for the Subscriptions screen. Shapes follow
// platform/billing/contracts/openapi.yaml (Plan, Subscription); nothing is added here.
//
// PUT /billing/admin/subscriptions/{organisation_id} (platform:subscriptions:manage) sets a plan, a trial end or a
// free period; billing publishes tenancy.entitlement.changed with the reason, so every change is in the audit trail.

import { api } from '../../api/client';

/** GET /billing/plans item: the published price list. */
export interface PublishedPlan {
  id: string;
  title: string;
  price_per_month: number;
  currency: string;
  trial_days: number | null;
  published: boolean;
}

/** PUT /billing/admin/subscriptions/{id} answer. */
export interface AdminSubscription {
  organisation_id: string;
  plan: string;
  status: string;
  trial_ends_at: string | null;
}

/** The trial plan's id (platform/billing/config/plans.yaml); only a trial has an end to extend. */
export const TRIAL_PLAN = 'trial';

export const listPlans = (): Promise<PublishedPlan[]> => api<PublishedPlan[]>('/billing/plans');

const required = (reason: string): string | null => reason.trim() || null;

/** Moves an organisation to another plan. */
export const changePlan = (organisationId: string, plan: string, reason: string): Promise<AdminSubscription> => {
  const r = required(reason);
  if (!r) return Promise.reject(new Error('A reason is required.'));
  return api<AdminSubscription>(`/billing/admin/subscriptions/${encodeURIComponent(organisationId)}`, {
    method: 'PUT',
    json: { plan, reason: r }
  });
};

/** Sets a trial's last day (YYYY-MM-DD): the trial runs to the end of that day, UTC. */
export const extendTrial = (organisationId: string, lastDay: string, reason: string): Promise<AdminSubscription> => {
  const r = required(reason);
  if (!r) return Promise.reject(new Error('A reason is required.'));
  if (!/^\d{4}-\d{2}-\d{2}$/.test(lastDay)) return Promise.reject(new Error('Choose the trial’s new last day.'));
  return api<AdminSubscription>(`/billing/admin/subscriptions/${encodeURIComponent(organisationId)}`, {
    method: 'PUT',
    json: { trial_ends_at: `${lastDay}T23:59:59+00:00`, reason: r }
  });
};
