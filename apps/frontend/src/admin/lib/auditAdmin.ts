// Reading platform/audit for the Audit Log page. Shapes follow platform/audit/contracts/openapi.yaml (AuditRecord,
// the page of GET /records); nothing is added here.
//
// An organisation user reads only their own organisation's records (the API ignores organisation_id for them). A
// super admin reads platform-level records (organisation_id null: approvals, impersonation, cross-organisation reads)
// by default, or one organisation's records by passing its id; the API records that read itself
// (audit_trail.read), so looking at an organisation's trail leaves a trail of its own.

import { api } from '../../api/client';
import type { AdminOrganisation } from './organisationsAdmin';

/** GET /audit/records item. */
export interface AuditRecord {
  id: string;
  organisation_id: string | null;
  actor: string | null;
  /** The actor's current display name, resolved at read time; absent when the actor is gone or was the system. */
  actor_name?: string;
  module: string;
  action: string;
  entity_type: string;
  entity_id: string;
  summary: string | null;
  context: Record<string, unknown>;
  occurred_at: string | null;
  /** The before/after payload was replaced by a tombstone under a legal erasure request. */
  redacted: boolean;
}

export interface AuditPage {
  items: AuditRecord[];
  total: number;
}

export const AUDIT_PAGE_SIZE = 50;

/** One page of records, newest first. `organisationId` matters only for a super admin (see above). */
export function listAuditRecords({ organisationId, offset = 0 }: { organisationId?: string | null; offset?: number } = {}): Promise<AuditPage> {
  const q = new URLSearchParams({ limit: String(AUDIT_PAGE_SIZE), offset: String(offset) });
  if (organisationId) q.set('organisation_id', organisationId);
  return api<AuditPage>(`/audit/records?${q.toString()}`);
}

/** Every organisation, for the super admin's "whose trail" choice (GET /tenancy/admin/organisations). */
export const listAllOrganisations = (): Promise<AdminOrganisation[]> => api<AdminOrganisation[]>('/tenancy/admin/organisations');

/** Who acted, as the page shows it: the current name, else a short id, else the system. */
export function actorLabel(r: Pick<AuditRecord, 'actor' | 'actor_name'>): string {
  if (r.actor_name) return r.actor_name;
  if (r.actor) return `User ${r.actor.slice(0, 8)}`;
  return 'System';
}

/** "3 Nov 2026, 14:05" in the viewer's time zone; "" when missing or not a date. */
export function when(iso: string | null): string {
  if (!iso) return '';
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? ''
    : d.toLocaleString('en-GB', { day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

/** Records that happened today in the viewer's time zone. */
export function happenedToday(iso: string | null, now: Date = new Date()): boolean {
  if (!iso) return false;
  const d = new Date(iso);
  return !Number.isNaN(d.getTime()) && d.toDateString() === now.toDateString();
}
