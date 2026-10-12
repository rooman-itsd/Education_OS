// What the admin screens know about the repository, read at build time from the files the backend
// reads: module manifests, contracts/permissions.yaml, academy profiles, plans and role layouts.
// Nothing here is hand-copied, so the screens follow the repo as it changes.

import { parse } from 'yaml';
import { loadLayouts, type LayoutMap } from '../../dashboard/layouts';
import { loadPlans, loadProfiles, type AcademyProfile, type Plan } from '../../tenant/entitlements';

// ---------- Module manifests (module.yaml) ----------

export interface Manifest {
  name: string;
  kind: 'feature' | 'platform' | 'integration';
  domain: string;
  tier: string;
  field?: string;
  status: string;
  description: string;
}

const manifestFiles = import.meta.glob<string>(
  ['../../../../../modules/*/*/module.yaml', '../../../../../platform/*/module.yaml', '../../../../../integrations/*/module.yaml'],
  { query: '?raw', import: 'default', eager: true }
);

/** Manifests by module id (the folder name, which is also the manifest `name`). */
export const MANIFESTS: Record<string, Manifest> = Object.fromEntries(
  Object.entries(manifestFiles).map(([path, raw]) => {
    const id = path.split('/').slice(-2, -1)[0]!;
    return [id, parse(raw) as Manifest];
  })
);

// ---------- Permissions (contracts/permissions.yaml) ----------

export interface PermissionDef {
  key: string;
  description?: string;
}

interface PermissionsFile {
  module?: string;
  permissions?: PermissionDef[] | null;
  roles?: { name: string; description?: string; grants?: string[] | null }[] | null;
}

const permissionFiles = import.meta.glob<string>(
  ['../../../../../modules/*/*/contracts/permissions.yaml', '../../../../../platform/*/contracts/permissions.yaml', '../../../../../integrations/*/contracts/permissions.yaml'],
  { query: '?raw', import: 'default', eager: true }
);

/** Permission keys each module defines, by module id. A module with none maps to []. */
export const MODULE_PERMISSIONS: Record<string, PermissionDef[]> = {};
/** Role name -> keys granted to it, unioned across every permissions.yaml (eos_core.config.load_role_grants). */
export const ROLE_GRANTS: Record<string, Set<string>> = {};

for (const [path, raw] of Object.entries(permissionFiles)) {
  const id = path.split('/').slice(-3, -2)[0]!;
  const data = (parse(raw) as PermissionsFile | null) ?? {};
  MODULE_PERMISSIONS[id] = data.permissions ?? [];
  for (const role of data.roles ?? []) {
    const set = (ROLE_GRANTS[role.name] ??= new Set());
    for (const key of role.grants ?? []) set.add(key);
  }
}

/** The keys a role holds, by the backend rule (eos_core.config.permissions_for). */
export function permissionsFor(roleIds: string[], superAdmin = false): string[] {
  const out = new Set<string>();
  for (const r of roleIds) for (const k of ROLE_GRANTS[r] ?? []) out.add(k);
  if (superAdmin) for (const keys of Object.values(ROLE_GRANTS)) for (const k of keys) if (k.startsWith('platform:')) out.add(k);
  return [...out].sort();
}

/** The module that defines a permission key, if any. */
export function moduleOfPermission(key: string): string | undefined {
  return Object.entries(MODULE_PERMISSIONS).find(([, defs]) => defs.some((d) => d.key === key))?.[0];
}

// ---------- Academy profiles, plans and role layouts ----------

export const PROFILES: Record<string, AcademyProfile> = loadProfiles();
export const PLANS: Record<string, Plan> = loadPlans();
export const LAYOUTS: LayoutMap = loadLayouts();

/**
 * The display label for an academy type: the part of the profile's title that matches its
 * academy_type (profile id), e.g. sports-college -> "Sports College" from
 * "Sports University / Sports College". Falls back to the full title when no part matches.
 */
export function academyLabel(profile: AcademyProfile): string {
  const slug = (text: string) => text.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
  return profile.title.split(' / ').find((part) => slug(part) === profile.profile) ?? profile.title;
}

/** The profile the admin screens describe until an organisation's own profile is known. */
export const REFERENCE_PROFILE_ID = 'sports-college';
export const REFERENCE_PROFILE: AcademyProfile = PROFILES[REFERENCE_PROFILE_ID]!;
