// The organisation the admin screens are about. Education OS is multi-tenant: the name, academy
// type and plan come from the signed-in organisation, never from the UI. A super admin sits outside
// every organisation. Without an API, preview names a demo organisation the way the main app does.

import { useEntitlementView } from '../data/entitlement';
import { academyLabel } from '../data/repo';
import { useAuth } from './auth';

export interface OrganisationContext {
  /** e.g. the organisation's registered name, "Education OS platform", or "Demo Sports College". */
  name: string;
  /** Academy type and plan, or the super admin scope. */
  detail: string;
  /** True when a live API answers. */
  connected: boolean;
}

export function useOrganisation(): OrganisationContext {
  const { preview, session } = useAuth();
  const view = useEntitlementView();
  // Label for the organisation's academy_type, e.g. sports-college -> "Sports College".
  const academy = view.profile ? academyLabel(view.profile) : undefined;
  const plan = view.planTitle ? `${view.planTitle} plan` : undefined;
  if (session?.organisation) {
    return { name: session.organisation.name, detail: [academy, plan].filter(Boolean).join(' · '), connected: true };
  }
  if (session?.me.is_super_admin) {
    return { name: 'Education OS platform', detail: 'Super admin · all organisations', connected: true };
  }
  return { name: `Demo ${academy ?? 'organisation'}`, detail: [plan, 'preview'].filter(Boolean).join(' · '), connected: !preview };
}
