// What each API endpoint requires, read at build time from the platform routers
// (platform/<service>/backend/src/*/api/router.py), so the Role & Access page follows the backend:
//   require("<key>")                       -> the caller must hold that permission key
//   require("<key>", organisation=True)    -> ...and belong to an organisation (not a super admin)
//   require_organisation                   -> the caller must belong to an organisation
//   current_principal                      -> any signed-in user
//   none of these                          -> public (sign-in, registration, plans)
// Every organisation user also holds the implicit `member` role (platform/tenancy/contracts/permissions.yaml).

import { ROLE_GRANTS } from './repo';

const routers = import.meta.glob<string>('../../../../../platform/*/backend/src/*/api/router.py', {
  query: '?raw',
  import: 'default',
  eager: true
});

export type Requirement =
  | { kind: 'permission'; key: string; organisation?: boolean }
  | { kind: 'organisation' }
  | { kind: 'signed-in' }
  | { kind: 'public' };

export interface Endpoint {
  service: string;
  method: string;
  /** Full path as mounted by apps/backend: /api/v1/<service><route>. */
  path: string;
  /** First line of the handler's docstring, or its name. */
  summary: string;
  requires: Requirement;
}

const humanise = (fn: string) => fn.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase());

function parse(service: string, source: string): Endpoint[] {
  const blocks = source.split(/^(?=@router\.)/m).slice(1);
  return blocks.flatMap((block) => {
    const head = block.match(/^@router\.(get|post|put|patch|delete)\("([^"]+)"/);
    if (!head) return [];
    const fn = block.match(/def\s+(\w+)\s*\(/)?.[1] ?? '';
    const doc = block.match(/"""\s*([^\n"]+)/)?.[1]?.trim();
    const guard = block.match(/require\("([^"]+)"(,\s*organisation=True)?\s*\)/);
    const key = guard?.[1];
    const requires: Requirement = key
      ? guard?.[2]
        ? { kind: 'permission', key, organisation: true }
        : { kind: 'permission', key }
      : /require_organisation/.test(block)
        ? { kind: 'organisation' }
        : /current_principal/.test(block)
          ? { kind: 'signed-in' }
          : { kind: 'public' };
    return [{ service, method: head[1]!.toUpperCase(), path: `/api/v1/${service}${head[2]}`, summary: doc ?? humanise(fn), requires }];
  });
}

export const ENDPOINTS: Endpoint[] = Object.entries(routers).flatMap(([path, source]) => {
  const service = path.split('/platform/')[1]?.split('/')[0] ?? '';
  return parse(service, source);
});

export interface Caller {
  permissions: string[];
  organisationId: string | null;
}

/** Whether the backend lets this caller call the endpoint (identity deps: require / require_organisation). */
export function allows(e: Endpoint, c: Caller): boolean {
  switch (e.requires.kind) {
    case 'permission': {
      if (e.requires.organisation && !c.organisationId) return false;
      const implicit = c.organisationId ? ROLE_GRANTS['member'] ?? new Set<string>() : new Set<string>();
      return c.permissions.includes(e.requires.key) || implicit.has(e.requires.key);
    }
    case 'organisation':
      return Boolean(c.organisationId);
    default:
      return true;
  }
}

export const requirementLabel = (r: Requirement) =>
  r.kind === 'permission'
    ? r.organisation
      ? `${r.key} (organisation user)`
      : r.key
    : r.kind === 'organisation'
      ? 'organisation user'
      : r.kind === 'signed-in'
        ? 'any signed-in user'
        : 'public';
