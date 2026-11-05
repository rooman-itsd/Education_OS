import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from '../lib/router';
import { AlertTriangle, Building2, CheckCircle2, Search, ShieldCheck, Users } from '../lib/icons';
import { useAuth } from '../lib/auth';
import { describeFailure } from '../lib/adminErrors';
import {
  ORGANISATION_STATUSES,
  getOrganisation,
  listOrganisations,
  setOrganisationStatus,
  type AdminOrganisation,
  type AdminOrganisationDetail
} from '../lib/organisationsAdmin';
import { PROFILES, academyLabel } from '../data/repo';
import { PageHeader, StatGrid, BTN_SECONDARY } from '../components/ui/dashboard';
import { ReasonDialog } from '../components/organisations/ReasonDialog';

/**
 * Organisations (super admin): every tenant with its status, plan and trial, and the two status changes a super admin
 * makes by hand: suspend an active organisation, switch a suspended one back on (infra/runbooks/suspend-a-tenant.md
 * says when). Both go through PUT /tenancy/admin/organisations/{id}/status with a reason, which tenancy records.
 * Approving registrations stays in the Dashboard's approval queue; deleting, purging, exporting and impersonating stay
 * API-only. In preview mode the page shows labelled samples and calls nothing.
 */

const STATUS_LABEL: Record<string, string> = {
  pending_verification: 'Email not verified',
  pending_approval: 'Awaiting approval',
  active: 'Active',
  suspended: 'Suspended',
  archived: 'Archived'
};
const STATUS_STYLE: Record<string, string> = {
  active: 'bg-[#ECFDF3] text-[#15803D]',
  suspended: 'bg-[#FEF2F2] text-[#B91C1C]',
  archived: 'bg-[#F1F5F9] text-[#475569]',
  pending_approval: 'bg-[#FFF7ED] text-[#C2410C]',
  pending_verification: 'bg-[#F1F5F9] text-[#475569]'
};

const SAMPLE: AdminOrganisation[] = [
  { id: 's1', name: 'Riverside Music Academy', slug: 'riverside', academy_type: 'music-academy', requested_academy_type: null, country: 'IN', status: 'active', status_reason: null, created_at: '2026-10-21T09:00:00Z', plan: 'standard', trial_ends_at: null },
  { id: 's2', name: 'Northfield Sports College', slug: 'northfield', academy_type: 'sports-college', requested_academy_type: null, country: 'IN', status: 'active', status_reason: null, created_at: '2026-10-25T09:00:00Z', plan: 'trial', trial_ends_at: '2026-11-08T23:59:59Z' },
  { id: 's3', name: 'Lakeside Institute of Technology', slug: 'lakeside', academy_type: 'engineering-college', requested_academy_type: null, country: 'IN', status: 'suspended', status_reason: 'Invoice unpaid for 60 days', created_at: '2026-10-12T09:00:00Z', plan: 'standard', trial_ends_at: null }
];

const academy = (id: string) => (PROFILES[id] ? academyLabel(PROFILES[id]!) : id);
const day = (iso: string | null | undefined) => {
  if (!iso) return '–';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '–' : d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
};

type Load = { state: 'loading' } | { state: 'error'; message: string; retry: boolean } | { state: 'ready' };
type Change = { org: AdminOrganisation; to: 'active' | 'suspended' };
type Detail = { id: string; data?: AdminOrganisationDetail; error?: string };

const SELECT =
  'w-full px-3 py-1.5 text-xs rounded-lg border border-[#E2E8F0] focus:outline-none focus:ring-2 focus:ring-[#9333EA] bg-[#F6F8FB] text-[#12233F]';

export const OrganisationsPage: React.FC = () => {
  const { session, preview, signOut } = useAuth();
  const navigate = useNavigate();
  const superAdmin = Boolean(session?.me.is_super_admin) && !preview;

  const [orgs, setOrgs] = useState<AdminOrganisation[]>(preview ? SAMPLE : []);
  const [load, setLoad] = useState<Load>(preview ? { state: 'ready' } : { state: 'loading' });
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('all');
  const [plan, setPlan] = useState('all');
  const [type, setType] = useState('all');
  const [change, setChange] = useState<Change | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [detail, setDetail] = useState<Detail | null>(null);
  const request = useRef(0);

  const expired = useCallback(() => {
    signOut();
    navigate('/login', { replace: true });
  }, [navigate, signOut]);

  const reload = useCallback(() => {
    if (!superAdmin) return;
    const mine = ++request.current;
    setLoad({ state: 'loading' });
    listOrganisations()
      .then((list) => {
        if (mine !== request.current) return;
        setOrgs([...list].sort((a, b) => (b.created_at ?? '').localeCompare(a.created_at ?? '')));
        setLoad({ state: 'ready' });
      })
      .catch((e: unknown) => {
        if (mine !== request.current) return;
        const f = describeFailure(e, 'organisations');
        if (f.expired) return expired();
        setLoad({ state: 'error', message: f.message, retry: f.retry });
      });
  }, [superAdmin, expired]);

  useEffect(reload, [reload]);

  const plans = useMemo(() => Array.from(new Set(orgs.map((o) => o.plan).filter(Boolean) as string[])).sort(), [orgs]);
  const types = useMemo(() => Array.from(new Set(orgs.map((o) => o.academy_type))).sort(), [orgs]);
  const q = query.trim().toLowerCase();
  const shown = orgs.filter(
    (o) =>
      (status === 'all' || o.status === status) &&
      (plan === 'all' || o.plan === plan) &&
      (type === 'all' || o.academy_type === type) &&
      (!q || o.name.toLowerCase().includes(q) || o.slug.toLowerCase().includes(q))
  );
  const count = (s: string) => orgs.filter((o) => o.status === s).length;

  const toggleDetail = (o: AdminOrganisation) => {
    if (detail?.id === o.id) return setDetail(null);
    if (preview) return setDetail({ id: o.id, data: { ...o, entitlement: { status: o.status, subscription_status: o.plan === 'trial' ? 'trialing' : 'active' } } });
    setDetail({ id: o.id });
    getOrganisation(o.id)
      .then((data) => setDetail((d) => (d?.id === o.id ? { id: o.id, data } : d)))
      .catch((e: unknown) => setDetail((d) => (d?.id === o.id ? { id: o.id, error: describeFailure(e, 'the details').message } : d)));
  };

  if (!preview && !session?.me.is_super_admin) {
    return (
      <div className="space-y-6">
        <PageHeader title="Organisations" subtitle="Every organisation on the platform." />
        <p role="alert" className="text-xs text-[#475569]">
          Only a super admin manages organisations.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Organisations"
        subtitle={
          <span className="inline-flex flex-wrap items-center gap-2">
            Every organisation on the platform. Suspending one blocks its sign-ins and its module requests at once and
            keeps all its data; every change is recorded with its reason. Registrations are approved on the Dashboard.
            {preview && (
              <span className="inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full bg-[#F1F5F9] text-[#475569]">
                <ShieldCheck className="w-3 h-3" />
                Sample data
              </span>
            )}
          </span>
        }
      />

      <StatGrid
        stats={[
          { label: 'Organisations', icon: Building2, value: String(orgs.length), note: 'On the platform' },
          { label: 'Active', icon: CheckCircle2, value: String(count('active')), note: 'Can sign in' },
          { label: 'Suspended', icon: AlertTriangle, value: String(count('suspended')), note: 'Blocked, data kept' },
          { label: 'Awaiting approval', icon: Users, value: String(count('pending_approval')), note: 'On the Dashboard' }
        ]}
      />

      {notice && (
        <div role="status" className="p-3 rounded-lg bg-[#ECFDF3] border border-[#BBF7D0] text-xs text-[#15803D]">
          {notice}
        </div>
      )}

      <div className="bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] p-4 shadow-2xs">
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
          <div className="relative">
            <Search className="w-4 h-4 text-[#475569] absolute left-3 top-2.5" />
            <input
              type="text"
              aria-label="Search"
              placeholder="Search by name or slug..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 text-xs rounded-lg border border-[#E2E8F0] focus:outline-none focus:ring-2 focus:ring-[#9333EA] bg-[#F6F8FB]"
            />
          </div>
          <select aria-label="Status" value={status} onChange={(e) => setStatus(e.target.value)} className={SELECT}>
            <option value="all">All statuses</option>
            {ORGANISATION_STATUSES.map((s) => (
              <option key={s} value={s}>
                {STATUS_LABEL[s]}
              </option>
            ))}
          </select>
          <select aria-label="Plan" value={plan} onChange={(e) => setPlan(e.target.value)} className={SELECT}>
            <option value="all">All plans</option>
            {plans.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
          <select aria-label="Academy type" value={type} onChange={(e) => setType(e.target.value)} className={SELECT}>
            <option value="all">All academy types</option>
            {types.map((t) => (
              <option key={t} value={t}>
                {academy(t)}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] shadow-2xs overflow-hidden">
        {load.state === 'error' ? (
          <div role="alert" className="py-8 px-4 text-center text-xs text-[#475569] space-y-3">
            <p className="inline-flex items-center gap-2 text-[#B91C1C]">
              <AlertTriangle className="w-4 h-4" />
              {load.message}
            </p>
            {load.retry && (
              <div>
                <button onClick={reload} className={BTN_SECONDARY}>
                  Try again
                </button>
              </div>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs" aria-busy={load.state === 'loading'}>
              <thead>
                <tr className="bg-[#F6F8FB] border-b border-[#E2E8F0] text-[#475569] font-semibold">
                  <th className="py-3 px-4">Organisation</th>
                  <th className="py-3 px-4">Academy type</th>
                  <th className="py-3 px-4">Status</th>
                  <th className="py-3 px-4">Plan</th>
                  <th className="py-3 px-4">Trial ends</th>
                  <th className="py-3 px-4">Registered</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#F1F5F9] text-[#12233F]">
                {load.state === 'loading' ? (
                  <tr>
                    <td colSpan={7} className="py-8 text-center text-[#475569]">
                      Loading organisations…
                    </td>
                  </tr>
                ) : shown.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="py-8 text-center text-[#475569]">
                      {orgs.length === 0 ? 'No organisations yet.' : 'No organisations match the filters.'}
                    </td>
                  </tr>
                ) : (
                  shown.map((o) => (
                    <React.Fragment key={o.id}>
                      <tr className="hover:bg-[#F6F8FB] transition-colors">
                        <td className="py-3 px-4">
                          <button
                            type="button"
                            onClick={() => toggleDetail(o)}
                            aria-expanded={detail?.id === o.id}
                            className="font-semibold text-[#12233F] hover:underline text-left"
                          >
                            {o.name}
                          </button>
                          <div className="text-[#475569] font-mono">{o.slug}</div>
                        </td>
                        <td className="py-3 px-4">{academy(o.academy_type)}</td>
                        <td className="py-3 px-4">
                          <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold ${STATUS_STYLE[o.status] ?? STATUS_STYLE.archived}`}>
                            {STATUS_LABEL[o.status] ?? o.status}
                          </span>
                        </td>
                        <td className="py-3 px-4">{o.plan ?? '–'}</td>
                        <td className="py-3 px-4 whitespace-nowrap">{day(o.trial_ends_at)}</td>
                        <td className="py-3 px-4 whitespace-nowrap">{day(o.created_at)}</td>
                        <td className="py-3 px-4 text-right">
                          {o.status === 'active' && (
                            <button
                              type="button"
                              disabled={preview}
                              onClick={() => setChange({ org: o, to: 'suspended' })}
                              className="px-3 py-1 rounded-lg border border-[#FECACA] text-[#B91C1C] hover:bg-[#FEF2F2] disabled:opacity-50"
                            >
                              Suspend
                            </button>
                          )}
                          {o.status === 'suspended' && (
                            <button type="button" disabled={preview} onClick={() => setChange({ org: o, to: 'active' })} className={`${BTN_SECONDARY} disabled:opacity-50`}>
                              Reactivate
                            </button>
                          )}
                        </td>
                      </tr>
                      {detail?.id === o.id && (
                        <tr className="bg-[#F6F8FB]">
                          <td colSpan={7} className="py-3 px-4 text-[#475569]">
                            {detail.error ? (
                              <span className="text-[#B91C1C]">{detail.error}</span>
                            ) : !detail.data ? (
                              'Loading details…'
                            ) : (
                              <dl className="grid grid-cols-1 sm:grid-cols-4 gap-2" aria-label={`Details of ${o.name}`}>
                                <div>
                                  <dt className="font-semibold text-[#12233F]">Status reason</dt>
                                  <dd>{detail.data.status_reason || '–'}</dd>
                                </div>
                                <div>
                                  <dt className="font-semibold text-[#12233F]">Subscription</dt>
                                  <dd>{detail.data.entitlement?.subscription_status ?? '–'}</dd>
                                </div>
                                <div>
                                  <dt className="font-semibold text-[#12233F]">Modules entitled</dt>
                                  <dd>{detail.data.entitlement?.modules ? detail.data.entitlement.modules.length : '–'}</dd>
                                </div>
                                <div>
                                  <dt className="font-semibold text-[#12233F]">Deletion</dt>
                                  <dd>{detail.data.delete_after ? `Scheduled ${day(detail.data.delete_after)}` : 'None'}</dd>
                                </div>
                              </dl>
                            )}
                          </td>
                        </tr>
                      )}
                    </React.Fragment>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
        <div className="py-3 px-4 border-t border-[#E2E8F0] bg-[#F6F8FB] text-xs text-[#475569]">
          Showing <strong className="text-[#12233F]">{shown.length}</strong> of {orgs.length} organisations
        </div>
      </div>

      {change && (
        <ReasonDialog
          title={`${change.to === 'suspended' ? 'Suspend' : 'Reactivate'} ${change.org.name}?`}
          description={
            change.to === 'suspended'
              ? 'Nobody in this organisation can sign in, and anyone signed in is refused at once. Nothing is deleted.'
              : 'Its users can sign in again at once; their data is as they left it.'
          }
          confirmLabel={change.to === 'suspended' ? 'Suspend' : 'Reactivate'}
          busyLabel={change.to === 'suspended' ? 'Suspending…' : 'Reactivating…'}
          danger={change.to === 'suspended'}
          onClose={() => setChange(null)}
          onConfirm={async (reason) => {
            await setOrganisationStatus(change.org.id, change.to, reason);
            setNotice(`${change.org.name} is now ${change.to === 'suspended' ? 'suspended' : 'active'}.`);
            setChange(null);
            setDetail(null);
            reload();
          }}
        />
      )}
    </div>
  );
};
