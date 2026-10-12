// Roles, their permission keys and their dashboard layouts, read from the repository:
// - Academy roles: platform/identity/config/profiles/<profile>.yaml (roles are data, ADR-0004).
// - Platform roles: org-admin and super-admin, the only roles fixed in packages/contracts.
// - Permission keys: granted by role name in every contracts/permissions.yaml, resolved like
//   eos_core.config.permissions_for (a super admin also holds every platform:* key).
// - Layouts: platform/identity/config/dashboards/<role>.yaml.
// User counts and data scopes are the admin's sample data.

import { PLATFORM_ROLES, rolesForProfile } from '@eos/contracts';
import { resolveWidgetIds as resolveLayoutWidgets } from '../../dashboard/layouts';
import { useMemo } from 'react';
import type { AcademyProfile } from '../../tenant/entitlements';
import { useEntitlementView } from './entitlement';
import { LAYOUTS, PROFILES, REFERENCE_PROFILE, permissionsFor } from './repo';

export type DataScope = 'Institution' | 'Department' | 'Assigned Records' | 'Self';

export interface RoleDef {
  /** Role id: the profile's role id, or a platform role; also the dashboard layout file name. */
  id: string;
  title: string;
  description: string;
  dataScope: DataScope;
  /** Sample user count. */
  userCount: number;
  /** org-admin and super-admin: fixed by the platform, not by the academy profile. */
  system?: boolean;
  /** Permission keys the repo grants this role. */
  permissions: string[];
}

/** The admin's descriptions and sample counts; titles and ids come from the profile. */
const SAMPLE: Record<string, { description: string; dataScope: DataScope; userCount: number }> = {
  applicant: { description: 'Prospective student applying through the admissions portal.', dataScope: 'Self', userCount: 1842 },
  student: { description: 'Enrolled student: timetable, attendance, LMS, exams, fees and campus services.', dataScope: 'Self', userCount: 3414 },
  athlete: { description: 'Student-athlete. Inherits the Student dashboard, plus training, nutrition and tournaments.', dataScope: 'Self', userCount: 428 },
  faculty: { description: 'Teaches courses, marks attendance, grades LMS work and performs exam duties.', dataScope: 'Assigned Records', userCount: 312 },
  coach: { description: 'Plans training, reviews video, manages squads and books sports facilities. Inherits the Faculty dashboard.', dataScope: 'Assigned Records', userCount: 42 },
  'medical-staff': { description: 'Tracks injuries, physio appointments and fitness clearances.', dataScope: 'Assigned Records', userCount: 9 },
  nutritionist: { description: 'Builds and reviews athlete diet plans and body-composition trends.', dataScope: 'Assigned Records', userCount: 4 },
  'examination-staff': { description: 'Schedules exams, issues hall tickets, processes and publishes results.', dataScope: 'Institution', userCount: 6 },
  'department-admin': { description: 'Runs a department: approvals, faculty load, attendance and results.', dataScope: 'Department', userCount: 18 },
  'finance-staff': { description: 'Fee collection, payment reconciliation, budgets and purchase orders.', dataScope: 'Institution', userCount: 8 },
  'hr-staff': { description: 'Leave, payroll runs, joinings and exits, and e-office file movement.', dataScope: 'Institution', userCount: 7 },
  'facility-staff': { description: 'Bookings, maintenance tickets, stock levels and asset audits.', dataScope: 'Department', userCount: 21 },
  governance: { description: 'Grievances, RTI deadlines, IQAC and regulatory returns.', dataScope: 'Institution', userCount: 11 },
  'support-staff': { description: 'Triages tickets, watches SLA breaches, incidents and AMC renewals.', dataScope: 'Assigned Records', userCount: 15 },
  management: { description: 'Institution leadership: admissions, finance, results, compliance and productions at a glance.', dataScope: 'Institution', userCount: 5 },
  // ARCHITECTURE.md, "Tenancy, plans and the super admin".
  'org-admin': { description: 'Created at registration. Users, roles, settings and subscription of one organisation.', dataScope: 'Institution', userCount: 1 },
  'super-admin': { description: 'Platform operator outside every organisation: approves organisations and academic packages, plans, subscriptions, overrides and audited impersonation.', dataScope: 'Institution', userCount: 1 }
};

const PLATFORM_ROLE_IDS = new Set(PLATFORM_ROLES.map((r) => r.id));

/** An academy profile's roles plus the platform roles (packages/contracts rolesForProfile adds org-admin and super-admin). */
export function buildRoles(profile: AcademyProfile): RoleDef[] {
  return rolesForProfile(profile.roles).map((r) => ({
    id: r.id,
    title: r.title,
    description: SAMPLE[r.id]?.description ?? '',
    dataScope: SAMPLE[r.id]?.dataScope ?? 'Self',
    userCount: SAMPLE[r.id]?.userCount ?? 0,
    system: PLATFORM_ROLE_IDS.has(r.id),
    permissions: permissionsFor([r.id], r.id === 'super-admin')
  }));
}

/** Layouts of a set of roles, read from the repo. */
export const layoutsFor = (roles: RoleDef[]) =>
  Object.fromEntries(roles.flatMap((r) => (LAYOUTS[r.id] ? [[r.id, LAYOUTS[r.id]!] as const] : [])));

/** Roles of the reference profile, for code outside a signed-in context. */
export const ROLES: RoleDef[] = buildRoles(REFERENCE_PROFILE);

/**
 * The roles the admin screens show: the signed-in organisation's academy profile, or the
 * reference profile in preview and for a super admin (who sits outside every organisation).
 */
export function useRoles() {
  const view = useEntitlementView();
  const profile = view.profile ?? REFERENCE_PROFILE;
  return useMemo(() => {
    const roles = buildRoles(profile);
    return {
      ROLES: roles,
      ROLE_LAYOUTS: layoutsFor(roles),
      ROLES_SOURCE: `platform/identity/config/profiles/${profile.profile}.yaml`,
      ROLES_PROFILE_TITLE: profile.title
    };
  }, [profile]);
}

/** Every role title in every profile, so ids from any organisation resolve. */
const ALL_TITLES = new Map<string, string>([
  ...Object.values(PROFILES).flatMap((p) => rolesForProfile(p.roles).map((r) => [r.id, r.title] as [string, string])),
  ...PLATFORM_ROLES.map((r) => [r.id, r.title] as [string, string])
]);

export const findRole = (id: string) => ROLES.find((r) => r.id === id);
export const roleTitle = (id: string) => findRole(id)?.title ?? ALL_TITLES.get(id) ?? id;

// ---------------------------------------------------------------------------
// Role dashboard layouts (platform/identity/config/dashboards/*.yaml)
// ---------------------------------------------------------------------------

export type { RoleLayout } from '@eos/ui-kit';

/** Layouts of the reference profile's roles. */
export const ROLE_LAYOUTS = layoutsFor(ROLES);

/** Same rules as apps/frontend/src/dashboard/layouts.ts (it is that function): parent first, one level, de-duplicated. */
export const resolveWidgetIds = (roleId: string): string[] => resolveLayoutWidgets(roleId, LAYOUTS);

export const widgetModuleId = (widgetId: string) => widgetId.split('.')[0]!;

/** Role ids whose dashboard includes a widget from this module. */
export const rolesUsingModule = (moduleId: string) =>
  Object.keys(ROLE_LAYOUTS).filter((r) => resolveWidgetIds(r).some((w) => widgetModuleId(w) === moduleId));

/** Every widget id any layout references, grouped by module. */
export const widgetsByModule = (moduleId: string) =>
  [...new Set(Object.keys(ROLE_LAYOUTS).flatMap(resolveWidgetIds))].filter((w) => widgetModuleId(w) === moduleId);
