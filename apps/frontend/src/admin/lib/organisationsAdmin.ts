// Super admin calls to platform/tenancy for the organisation approval queue (ADR-0005). Shapes follow
// platform/tenancy/contracts/openapi.yaml (Organisation, OrganisationDetail); nothing is added here.
// Approval always goes through POST /approve, never PUT /status, so tenancy publishes
// tenancy.organisation.approved and refuses anything not pending_approval (409). Rejection archives
// the organisation through PUT /status, whose body requires a reason.

import { api } from '../../api/client';

/** GET /tenancy/admin/organisations item (Organisation in the contract, plus plan and trial end). */
export interface AdminOrganisation {
  id: string;
  name: string;
  slug: string;
  academy_type: string;
  requested_academy_type: string | null;
  country: string | null;
  status: string;
  status_reason: string | null;
  created_at: string | null;
  plan?: string | null;
  trial_ends_at?: string | null;
}

/** GET /tenancy/admin/organisations/{id} (OrganisationDetail). `admin_email` is in the contract but
 *  not yet returned by the API, so it is optional and shown only when present. */
export interface AdminOrganisationDetail extends AdminOrganisation {
  entitlement?: { modules?: string[]; status?: string; subscription_status?: string | null; trial_ends_at?: string | null };
  admin_email?: string;
}

/** The two registration states the queue shows; only the first can be approved or rejected. */
export const AWAITING_APPROVAL = 'pending_approval';
export const AWAITING_VERIFICATION = 'pending_verification';

const listByStatus = (status: string): Promise<AdminOrganisation[]> =>
  api<AdminOrganisation[]>(`/tenancy/admin/organisations?status=${status}`);

/** Organisations whose email is verified and that wait for a super admin. */
export const listPendingOrganisations = (): Promise<AdminOrganisation[]> => listByStatus(AWAITING_APPROVAL);

/** Organisations whose administrator has not verified their email yet; nothing can be done with them. */
export const listUnverifiedOrganisations = (): Promise<AdminOrganisation[]> => listByStatus(AWAITING_VERIFICATION);

/** Both registration states, newest first. The API filters by one status per call. */
export const listQueueOrganisations = async (): Promise<AdminOrganisation[]> => {
  const [pending, unverified] = await Promise.all([listPendingOrganisations(), listUnverifiedOrganisations()]);
  return [...pending, ...unverified].sort((a, b) => (b.created_at ?? '').localeCompare(a.created_at ?? ''));
};

export const getOrganisation = (id: string): Promise<AdminOrganisationDetail> =>
  api<AdminOrganisationDetail>(`/tenancy/admin/organisations/${encodeURIComponent(id)}`);

/** The contract's body is `{ reason?: string }`; an empty reason is left out. */
export const approveOrganisation = (id: string, reason?: string): Promise<AdminOrganisation> => {
  const r = reason?.trim();
  return api<AdminOrganisation>(`/tenancy/admin/organisations/${encodeURIComponent(id)}/approve`, {
    method: 'POST',
    json: r ? { reason: r } : {}
  });
};

/** Rejects a registration: PUT /status archives the organisation. The contract requires a reason. */
export const rejectOrganisation = (id: string, reason: string): Promise<AdminOrganisation> => {
  const r = reason.trim();
  if (!r) return Promise.reject(new Error('A reason is required to reject an organisation.'));
  return api<AdminOrganisation>(`/tenancy/admin/organisations/${encodeURIComponent(id)}/status`, {
    method: 'PUT',
    json: { status: 'archived', reason: r }
  });
};
