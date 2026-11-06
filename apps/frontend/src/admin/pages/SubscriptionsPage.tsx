import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from '../lib/router';
import { AlertTriangle, CalendarRange, CreditCard, Search, ShieldCheck } from '../lib/icons';
import { useAuth } from '../lib/auth';
import { describeFailure } from '../lib/adminErrors';
import { listOrganisations, type AdminOrganisation } from '../lib/organisationsAdmin';
import { TRIAL_PLAN, changePlan, extendTrial, listPlans, type PublishedPlan } from '../lib/subscriptionsAdmin';
import { PageHeader, StatGrid, BTN_SECONDARY } from '../components/ui/dashboard';
import { ReasonDialog } from '../components/organisations/ReasonDialog';

/**
 * Subscriptions (super admin): each organisation's plan and trial, and the two changes a super admin makes by hand:
 * move an organisation to another plan, or extend a trial. Both go through PUT /billing/admin/subscriptions/{id} with a
 * reason, which billing records (tenancy.entitlement.changed). Organisations still registering have no plan yet and are
 * left out. In preview mode the page shows labelled samples and calls nothing.
 */

const SAMPLE_ORGS: AdminOrganisation[] = [
  { id: 's1', name: 'Riverside Music Academy', slug: 'riverside', academy_type: 'music-academy', requested_academy_type: null, country: 'IN', status: 'active', status_reason: null, created_at: '2026-10-21T09:00:00Z', plan: 'standard', trial_ends_at: null },
  { id: 's2', name: 'Northfield Sports College', slug: 'northfield', academy_type: 'sports-college', requested_academy_type: null, country: 'IN', status: 'active', status_reason: null, created_at: '2026-10-25T09:00:00Z', plan: 'trial', trial_ends_at: '2026-11-08T23:59:59Z' }
];
const SAMPLE_PLANS: PublishedPlan[] = [
  { id: 'trial', title: 'Trial', price_per_month: 0, currency: 'INR', trial_days: 14, published: true },
  { id: 'standard', title: 'Standard', price_per_month: 25000, currency: 'INR', trial_days: null, published: true }
];

const day = (iso: string | null | undefined) => {
  if (!iso) return '–';
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '–' : d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
};
/** YYYY-MM-DD, `days` from `from` (UTC). */
const isoDay = (from: Date, days = 0) => new Date(from.getTime() + days * 86_400_000).toISOString().slice(0, 10);

type Load = { state: 'loading' } | { state: 'error'; message: string; retry: boolean } | { state: 'ready' };
type Action = { org: AdminOrganisation; kind: 'plan' | 'trial' };

const FIELD =
  'w-full px-3 py-1.5 text-xs rounded-lg border border-[#E2E8F0] focus:outline-none focus:ring-2 focus:ring-[#9333EA] bg-[#F6F8FB] text-[#12233F]';

export const SubscriptionsPage: React.FC = () => {
  const { session, preview, signOut } = useAuth();
  const navigate = useNavigate();
  const superAdmin = Boolean(session?.me.is_super_admin) && !preview;

  const [orgs, setOrgs] = useState<AdminOrganisation[]>(preview ? SAMPLE_ORGS : []);
  const [plans, setPlans] = useState<PublishedPlan[]>(preview ? SAMPLE_PLANS : []);
  const [load, setLoad] = useState<Load>(preview ? { state: 'ready' } : { state: 'loading' });
  const [query, setQuery] = useState('');
  const [planFilter, setPlanFilter] = useState('all');
  const [action, setAction] = useState<Action | null>(null);
  const [newPlan, setNewPlan] = useState('');
  const [lastDay, setLastDay] = useState('');
  const [notice, setNotice] = useState<string | null>(null);
  const request = useRef(0);

  const reload = useCallback(() => {
    if (!superAdmin) return;
    const mine = ++request.current;
    setLoad({ state: 'loading' });
    Promise.all([listOrganisations(), listPlans()])
      .then(([list, published]) => {
        if (mine !== request.current) return;
        setOrgs(list.filter((o) => o.plan).sort((a, b) => a.name.localeCompare(b.name)));
        setPlans(published);
        setLoad({ state: 'ready' });
      })
      .catch((e: unknown) => {
        if (mine !== request.current) return;
        const f = describeFailure(e, 'subscriptions');
        if (f.expired) {
          signOut();
          navigate('/login', { replace: true });
          return;
        }
        setLoad({ state: 'error', message: f.message, retry: f.retry });
      });
  }, [superAdmin, navigate, signOut]);

  useEffect(reload, [reload]);

  const title = useMemo(() => new Map(plans.map((p) => [p.id, p.title])), [plans]);
  const now = new Date();
  const q = query.trim().toLowerCase();
  const shown = orgs.filter(
    (o) => (planFilter === 'all' || o.plan === planFilter) && (!q || o.name.toLowerCase().includes(q) || o.slug.toLowerCase().includes(q))
  );
  const onTrial = orgs.filter((o) => o.plan === TRIAL_PLAN);
  const endingSoon = onTrial.filter((o) => o.trial_ends_at && new Date(o.trial_ends_at).getTime() - now.getTime() < 7 * 86_400_000);

  const open = (org: AdminOrganisation, kind: Action['kind']) => {
    setNewPlan(kind === 'plan' ? (plans.find((p) => p.id !== org.plan)?.id ?? '') : '');
    const base = org.trial_ends_at && new Date(org.trial_ends_at) > now ? new Date(org.trial_ends_at) : now;
    setLastDay(kind === 'trial' ? isoDay(base, 14) : '');
    setAction({ org, kind });
  };

  if (!preview && !session?.me.is_super_admin) {
    return (
      <div className="space-y-6">
        <PageHeader title="Subscriptions" subtitle="Each organisation's plan and trial." />
        <p role="alert" className="text-xs text-[#475569]">
          Only a super admin manages subscriptions.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Subscriptions"
        subtitle={
          <span className="inline-flex flex-wrap items-center gap-2">
            Each organisation&rsquo;s plan and trial. A plan change applies at once and changes which modules the organisation
            may use; every change is recorded with its reason.
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
          { label: 'Subscriptions', icon: CreditCard, value: String(orgs.length), note: 'Organisations with a plan' },
          { label: 'On trial', icon: CalendarRange, value: String(onTrial.length), note: 'Trial plan' },
          { label: 'Trials ending', icon: AlertTriangle, value: String(endingSoon.length), note: 'Within 7 days' },
          { label: 'Plans', icon: CreditCard, value: String(plans.length), note: 'Published' }
        ]}
      />

      {notice && (
        <div role="status" className="p-3 rounded-lg bg-[#ECFDF3] border border-[#BBF7D0] text-xs text-[#15803D]">
          {notice}
        </div>
      )}

      <div className="bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] p-4 shadow-2xs">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
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
          <select aria-label="Plan" value={planFilter} onChange={(e) => setPlanFilter(e.target.value)} className={FIELD}>
            <option value="all">All plans</option>
            {plans.map((p) => (
              <option key={p.id} value={p.id}>
                {p.title}
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
                  <th className="py-3 px-4">Organisation status</th>
                  <th className="py-3 px-4">Plan</th>
                  <th className="py-3 px-4">Trial ends</th>
                  <th className="py-3 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#F1F5F9] text-[#12233F]">
                {load.state === 'loading' ? (
                  <tr>
                    <td colSpan={5} className="py-8 text-center text-[#475569]">
                      Loading subscriptions…
                    </td>
                  </tr>
                ) : shown.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="py-8 text-center text-[#475569]">
                      {orgs.length === 0 ? 'No subscriptions yet.' : 'No subscriptions match the filters.'}
                    </td>
                  </tr>
                ) : (
                  shown.map((o) => {
                    const ended = o.plan === TRIAL_PLAN && o.trial_ends_at && new Date(o.trial_ends_at) < now;
                    return (
                      <tr key={o.id} className="hover:bg-[#F6F8FB] transition-colors">
                        <td className="py-3 px-4">
                          <div className="font-semibold">{o.name}</div>
                          <div className="text-[#475569] font-mono">{o.slug}</div>
                        </td>
                        <td className="py-3 px-4">{o.status}</td>
                        <td className="py-3 px-4">{title.get(o.plan ?? '') ?? o.plan}</td>
                        <td className="py-3 px-4 whitespace-nowrap">
                          {o.plan === TRIAL_PLAN ? day(o.trial_ends_at) : '–'}
                          {ended && <span className="ml-2 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-[#FEF2F2] text-[#B91C1C]">Ended</span>}
                        </td>
                        <td className="py-3 px-4 text-right whitespace-nowrap space-x-2">
                          {o.plan === TRIAL_PLAN && (
                            <button type="button" disabled={preview} onClick={() => open(o, 'trial')} className={`${BTN_SECONDARY} disabled:opacity-50`}>
                              Extend trial
                            </button>
                          )}
                          <button type="button" disabled={preview || plans.length < 2} onClick={() => open(o, 'plan')} className={`${BTN_SECONDARY} disabled:opacity-50`}>
                            Change plan
                          </button>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        )}
        <div className="py-3 px-4 border-t border-[#E2E8F0] bg-[#F6F8FB] text-xs text-[#475569]">
          Showing <strong className="text-[#12233F]">{shown.length}</strong> of {orgs.length} subscriptions
        </div>
      </div>

      {action?.kind === 'plan' && (
        <ReasonDialog
          title={`Change ${action.org.name}'s plan`}
          description={`From ${title.get(action.org.plan ?? '') ?? action.org.plan}. The new plan applies at once and changes which modules the organisation may use.`}
          confirmLabel="Change plan"
          busyLabel="Changing…"
          ready={Boolean(newPlan) && newPlan !== action.org.plan}
          extra={
            <div>
              <label htmlFor="new-plan" className="block font-semibold text-[#12233F] mb-1">
                New plan
              </label>
              <select id="new-plan" value={newPlan} onChange={(e) => setNewPlan(e.target.value)} className={FIELD}>
                {plans
                  .filter((p) => p.id !== action.org.plan)
                  .map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.title}
                    </option>
                  ))}
              </select>
            </div>
          }
          onClose={() => setAction(null)}
          onConfirm={async (reason) => {
            await changePlan(action.org.id, newPlan, reason);
            setNotice(`${action.org.name} is now on ${title.get(newPlan) ?? newPlan}.`);
            setAction(null);
            reload();
          }}
        />
      )}

      {action?.kind === 'trial' && (
        <ReasonDialog
          title={`Extend ${action.org.name}'s trial`}
          description={`The trial now ends on ${day(action.org.trial_ends_at)}. It runs to the end of the day you choose (UTC).`}
          confirmLabel="Extend trial"
          busyLabel="Extending…"
          ready={/^\d{4}-\d{2}-\d{2}$/.test(lastDay) && lastDay >= isoDay(now)}
          extra={
            <div>
              <label htmlFor="trial-last-day" className="block font-semibold text-[#12233F] mb-1">
                New last day of the trial
              </label>
              <input id="trial-last-day" type="date" min={isoDay(now)} value={lastDay} onChange={(e) => setLastDay(e.target.value)} className={FIELD} />
            </div>
          }
          onClose={() => setAction(null)}
          onConfirm={async (reason) => {
            await extendTrial(action.org.id, lastDay, reason);
            setNotice(`${action.org.name}'s trial now ends on ${day(`${lastDay}T12:00:00Z`)}.`);
            setAction(null);
            reload();
          }}
        />
      )}
    </div>
  );
};
