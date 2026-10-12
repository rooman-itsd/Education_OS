// What each API endpoint requires, read at build time from the platform routers
// (platform/<service>/backend/src/*/api/router.py), so the Role & Access page follows the backend:
//   require("<key>")       -> the caller must hold that permission key
//   require_organisation   -> the caller must belong to an organisation (not a super admin)
//   current_principal      -> any signed-in user
//   none of these          -> public (sign-in, registration, plans)

const routers = import.meta.glob<string>('../../../../../platform/*/backend/src/*/api/router.py', {
  query: '?raw',
  import: 'default',
  eager: true
});

export type Requirement =
  | { kind: 'permission'; key: string }
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
    const key = block.match(/require\("([^"]+)"\)/)?.[1];
    const requires: Requirement = key
      ? { kind: 'permission', key }
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
    case 'permission':
      return c.permissions.includes(e.requires.key);
    case 'organisation':
      return Boolean(c.organisationId);
    default:
      return true;
  }
}

export const requirementLabel = (r: Requirement) =>
  r.kind === 'permission' ? r.key : r.kind === 'organisation' ? 'organisation user' : r.kind === 'signed-in' ? 'any signed-in user' : 'public';
