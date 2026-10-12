// Which modules an organisation may use: its entitlement (ADR-0005), never a hand-made list.
// entitlement = academy profile modules ∩ plan (∪ super admin overrides), computed by
// platform/tenancy and enforced per request by the API gateway. Platform services are always
// reachable; each checks its own permissions.

import { useMemo } from 'react';
import { computeEntitlement, type AcademyProfile, type Entitlement } from '../../tenant/entitlements';
import { useAuth } from '../lib/auth';
import { modulePath, type ModuleInfo } from './architecture';
import { PLANS, PROFILES, REFERENCE_PROFILE } from './repo';

/** Preview shows the main app's preview defaults: the reference profile on the trial plan. */
const PREVIEW_PLAN_ID = 'trial';

export interface EntitlementView {
  /** organisation: the signed-in org admin's own; preview: no API; platform: super admin, outside every organisation. */
  source: 'organisation' | 'preview' | 'platform';
  profile: AcademyProfile | null;
  planTitle: string | null;
  entitlement: Entitlement | null;
}

export function useEntitlementView(): EntitlementView {
  const { preview, session } = useAuth();
  return useMemo(() => {
    if (session?.entitlement) {
      const profile = PROFILES[session.entitlement.academyType] ?? null;
      return { source: 'organisation', profile, planTitle: PLANS[session.entitlement.plan]?.title ?? session.entitlement.plan, entitlement: session.entitlement };
    }
    if (preview || !session) {
      const plan = PLANS[PREVIEW_PLAN_ID]!;
      return { source: 'preview', profile: REFERENCE_PROFILE, planTitle: plan.title, entitlement: computeEntitlement(REFERENCE_PROFILE, plan) };
    }
    return { source: 'platform', profile: null, planTitle: null, entitlement: null };
  }, [preview, session]);
}

/**
 * What the entitlement says about one module:
 * included: in profile and plan; upgrade: in the profile, not in this plan; not-in-profile: the
 * academy type does not offer it; platform: platform service, always reachable; per-organisation:
 * super admin view, decided per organisation.
 */
export type Access = 'included' | 'upgrade' | 'not-in-profile' | 'platform' | 'per-organisation';

export function moduleAccess(m: ModuleInfo, view: EntitlementView): Access {
  if (m.kind === 'platform') return 'platform';
  if (!view.entitlement || !view.profile) return 'per-organisation';
  if (m.kind === 'integration') {
    // eos_core.entitlement: profile integrations the plan allows ("*" allows all).
    if (!(view.profile.integrations ?? []).includes(m.id)) return 'not-in-profile';
    const allowed = PLANS[view.entitlement.plan]?.integrations ?? [];
    return allowed.includes('*') || allowed.includes(m.id) ? 'included' : 'upgrade';
  }
  const path = modulePath(m);
  if (view.entitlement.modules.has(path)) return 'included';
  if (view.profile.modules.includes(path)) return 'upgrade';
  return 'not-in-profile';
}

export const ACCESS_LABEL: Record<Access, string> = {
  included: 'Included in plan',
  upgrade: 'Upgrade to unlock',
  'not-in-profile': 'Not in academy profile',
  platform: 'Platform service',
  'per-organisation': 'Per organisation'
};

/** A module the viewer can actually open: built, and within the entitlement. */
export const isLive = (m: ModuleInfo, view: EntitlementView) => {
  const a = moduleAccess(m, view);
  return m.implemented && (a === 'included' || a === 'platform');
};
