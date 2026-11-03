import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from '../lib/router';
import { History, Search, CheckCircle2, AlertTriangle, FileCheck2, ShieldCheck, ShieldAlert } from '../lib/icons';
import { MOCK_AUDIT_LOGS } from '../data/mockData';
import { ApiError } from '../../api/client';
import { useAuth } from '../lib/auth';
import { AUDIT_PAGE_SIZE, actorLabel, happenedToday, listAllOrganisations, listAuditRecords, when, type AuditRecord } from '../lib/auditAdmin';
import type { AdminOrganisation } from '../lib/organisationsAdmin';
import { PageHeader, StatGrid, BTN_SECONDARY } from '../components/ui/dashboard';

/** Preview mode (no API): the sample events, in the real record's shape, labelled as samples. */
const SAMPLE: AuditRecord[] = MOCK_AUDIT_LOGS.map((l) => ({
  id: l.id,
  organisation_id: null,
  actor: null,
  actor_name: l.user,
  module: l.action.split('.')[0] ?? '',
  action: l.action,
  entity_type: l.resource.split(':')[0]?.trim() ?? '',
  entity_id: l.resource.split(':')[1]?.trim() ?? '',
  summary: null,
  context: {},
  occurred_at: null,
  redacted: false
}));

type Load = { state: 'loading' } | { state: 'error'; message: string; retry: boolean } | { state: 'ready' };

/** What the page says when the API refuses or is missing, as the other admin screens do. */
function failure(e: unknown): { message: string; retry: boolean; expired: boolean } {
  if (e instanceof ApiError && e.status === 401) return { message: 'Your session has ended. Sign in again.', retry: false, expired: true };
  if (e instanceof ApiError && e.status === 403) return { message: 'You do not have access to audit records.', retry: false, expired: false };
  if (!(e instanceof ApiError) || [404, 502, 503].includes(e.status)) {
    return { message: 'Audit records are not available yet.', retry: true, expired: false };
  }
  return { message: 'Could not load audit records. Try again in a moment.', retry: true, expired: false };
}

export const AuditPage: React.FC = () => {
  const { session, preview, signOut } = useAuth();
  const navigate = useNavigate();
  const superAdmin = Boolean(session?.me.is_super_admin) && !preview;

  const [records, setRecords] = useState<AuditRecord[]>(preview ? SAMPLE : []);
  const [total, setTotal] = useState(preview ? SAMPLE.length : 0);
  const [load, setLoad] = useState<Load>(preview ? { state: 'ready' } : { state: 'loading' });
  const [loadingMore, setLoadingMore] = useState(false);
  const [organisations, setOrganisations] = useState<AdminOrganisation[]>([]);
  // Super admin only: '' is the platform's own records, else one organisation's trail.
  const [organisationId, setOrganisationId] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedModule, setSelectedModule] = useState('All');
  const request = useRef(0);

  const onFailure = useCallback(
    (e: unknown) => {
      const f = failure(e);
      if (f.expired) {
        signOut();
        navigate('/login', { replace: true });
        return;
      }
      setLoad({ state: 'error', message: f.message, retry: f.retry });
    },
    [navigate, signOut]
  );

  const loadFirstPage = useCallback(() => {
    if (preview) return;
    const mine = ++request.current;
    setLoad({ state: 'loading' });
    listAuditRecords({ organisationId: superAdmin ? organisationId || null : null })
      .then((page) => {
        if (mine !== request.current) return; // a newer choice of organisation is loading
        setRecords(page.items);
        setTotal(page.total);
        setLoad({ state: 'ready' });
      })
      .catch((e: unknown) => mine === request.current && onFailure(e));
  }, [preview, superAdmin, organisationId, onFailure]);

  useEffect(loadFirstPage, [loadFirstPage]);

  useEffect(() => {
    if (!superAdmin) return;
    listAllOrganisations()
      .then((orgs) => setOrganisations([...orgs].sort((a, b) => a.name.localeCompare(b.name))))
      .catch(() => setOrganisations([])); // the platform's own records still show
  }, [superAdmin]);

  const loadMore = () => {
    const mine = request.current;
    setLoadingMore(true);
    listAuditRecords({ organisationId: superAdmin ? organisationId || null : null, offset: records.length })
      .then((page) => {
        if (mine !== request.current) return;
        setRecords((prev) => [...prev, ...page.items]);
        setTotal(page.total);
      })
      .catch(onFailure)
      .finally(() => setLoadingMore(false));
  };

  const modules = useMemo(() => ['All', ...Array.from(new Set(records.map((r) => r.module))).sort()], [records]);
  const filtered = records.filter((r) => {
    const q = searchQuery.trim().toLowerCase();
    const matchesSearch =
      !q ||
      [actorLabel(r), r.action, r.entity_type, r.entity_id, r.summary ?? ''].some((v) => v.toLowerCase().includes(q));
    return matchesSearch && (selectedModule === 'All' || r.module === selectedModule);
  });

  const scopeNote = preview
    ? 'Sample events: the API is not connected, so these use the event names in the repo’s contracts.'
    : superAdmin
      ? organisationId
        ? 'This organisation’s trail. Reading it is itself recorded, as a super admin action.'
        : 'The platform’s own records: approvals, impersonation and other super admin actions.'
      : `Your organisation’s trail${session?.organisation ? `: ${session.organisation.name}` : ''}.`;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Audit Activity"
        subtitle={
          <span className="inline-flex flex-wrap items-center gap-2">
            Every recorded state change, newest first. Audit records are append-only: nothing here can be edited or
            deleted. {scopeNote}
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
          { label: 'Records', icon: History, value: String(total), note: preview ? 'Sample events' : 'In this trail' },
          { label: 'Today', icon: CheckCircle2, value: String(records.filter((r) => happenedToday(r.occurred_at)).length), note: 'Among those loaded' },
          { label: 'Modules', icon: FileCheck2, value: String(modules.length - 1), note: 'That recorded changes' },
          { label: 'Actors', icon: ShieldAlert, value: String(new Set(records.map(actorLabel)).size), note: 'Distinct users and the system' }
        ]}
      />

      {/* FILTERS BAR */}
      <div className="bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] p-4 shadow-2xs">
        <div className={`grid grid-cols-1 gap-3 ${superAdmin ? 'sm:grid-cols-3' : 'sm:grid-cols-2'}`}>
          {superAdmin && (
            <div>
              <select
                aria-label="Whose trail"
                value={organisationId}
                onChange={(e) => {
                  setOrganisationId(e.target.value);
                  setSelectedModule('All');
                }}
                className="w-full px-3 py-1.5 text-xs rounded-lg border border-[#E2E8F0] focus:outline-none focus:ring-2 focus:ring-[#9333EA] bg-[#F6F8FB] text-[#12233F]"
              >
                <option value="">Platform (super admin actions)</option>
                {organisations.map((o) => (
                  <option key={o.id} value={o.id}>
                    {o.name}
                  </option>
                ))}
              </select>
            </div>
          )}
          <div className="relative">
            <Search className="w-4 h-4 text-[#475569] absolute left-3 top-2.5" />
            <input
              type="text"
              aria-label="Search"
              placeholder="Search by actor, action, entity or summary..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 text-xs rounded-lg border border-[#E2E8F0] focus:outline-none focus:ring-2 focus:ring-[#9333EA] bg-[#F6F8FB]"
            />
          </div>
          <div>
            <select
              aria-label="Module"
              value={selectedModule}
              onChange={(e) => setSelectedModule(e.target.value)}
              className="w-full px-3 py-1.5 text-xs rounded-lg border border-[#E2E8F0] focus:outline-none focus:ring-2 focus:ring-[#9333EA] bg-[#F6F8FB] text-[#12233F]"
            >
              <option value="All">All modules</option>
              {modules
                .filter((m) => m !== 'All')
                .map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
            </select>
          </div>
        </div>
      </div>

      {/* AUDIT RECORDS TABLE */}
      <div className="bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] shadow-2xs overflow-hidden">
        {load.state === 'error' ? (
          <div role="alert" className="py-8 px-4 text-center text-xs text-[#475569] space-y-3">
            <p className="inline-flex items-center gap-2 text-[#B91C1C]">
              <AlertTriangle className="w-4 h-4" />
              {load.message}
            </p>
            {load.retry && (
              <div>
                <button onClick={loadFirstPage} className={BTN_SECONDARY}>
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
                  <th className="py-3 px-4 w-40">When</th>
                  <th className="py-3 px-4">Actor</th>
                  <th className="py-3 px-4">Module</th>
                  <th className="py-3 px-4">Action</th>
                  <th className="py-3 px-4">Entity</th>
                  <th className="py-3 px-4">Summary</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#F1F5F9] text-[#12233F]">
                {load.state === 'loading' ? (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-[#475569]">
                      Loading audit records…
                    </td>
                  </tr>
                ) : filtered.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="py-8 text-center text-[#475569]">
                      {records.length === 0 ? 'No audit records yet.' : 'No audit records match the search.'}
                    </td>
                  </tr>
                ) : (
                  filtered.map((r) => (
                    <tr key={r.id} className="hover:bg-[#F6F8FB] transition-colors">
                      <td className="py-3 px-4 font-mono text-[#475569] whitespace-nowrap">{when(r.occurred_at) || '–'}</td>
                      <td className="py-3 px-4 font-semibold text-[#12233F]">{actorLabel(r)}</td>
                      <td className="py-3 px-4">
                        <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-[#F1F5F9] text-[#7E22CE]">{r.module}</span>
                      </td>
                      <td className="py-3 px-4 font-mono text-[#12233F]">{r.action}</td>
                      <td className="py-3 px-4 font-mono text-[#7E22CE] font-semibold">
                        {r.entity_type}: {r.entity_id}
                      </td>
                      <td className="py-3 px-4 text-[#475569]">
                        {r.summary ?? ''}
                        {r.redacted && (
                          <span className="ml-2 px-2 py-0.5 rounded-full text-[10px] font-semibold bg-[#F39A1926] text-[#8A4F00]">Redacted</span>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}

        <div className="py-3 px-4 border-t border-[#E2E8F0] bg-[#F6F8FB] flex items-center justify-between text-xs text-[#475569]">
          <span>
            Showing <strong className="text-[#12233F]">{filtered.length}</strong> of {total} records
          </span>
          {!preview && load.state === 'ready' && records.length < total && (
            <button onClick={loadMore} disabled={loadingMore} className={BTN_SECONDARY}>
              {loadingMore ? 'Loading…' : `Load ${Math.min(AUDIT_PAGE_SIZE, total - records.length)} more`}
            </button>
          )}
        </div>
      </div>
    </div>
  );
};
