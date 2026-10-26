import React, { useCallback, useEffect, useId, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { ApiError } from '../../../api/client';
import { Building2, CheckCircle2, Search, X } from '../../lib/icons';
import { PANEL, PanelHeader, BTN_PRIMARY, BTN_SECONDARY, BTN_DANGER } from '../ui/dashboard';
import { PROFILES, academyLabel } from '../../data/repo';
import {
  AWAITING_APPROVAL,
  AWAITING_VERIFICATION,
  approveOrganisation,
  getOrganisation,
  listQueueOrganisations,
  rejectOrganisation,
  type AdminOrganisation,
  type AdminOrganisationDetail
} from '../../lib/organisationsAdmin';

/**
 * The super admin's organisation approval queue (ADR-0005), on the existing Dashboard: registered
 * organisations that are still pending (GET ?status=pending_approval and ?status=pending_verification),
 * a review drawer (GET /{id}) and a confirmation for approving (POST /{id}/approve) or rejecting
 * (PUT /{id}/status, archived, with a reason). Only an organisation whose administrator verified
 * their email (pending_approval) can be decided on; the others are listed as waiting. The buttons
 * follow the status the drawer fetched, not the list row, and a detail response that arrives after
 * the drawer moved to another organisation is dropped. After a decision the list is fetched again,
 * so the count stays true; a 409 means someone else already decided, and is handled the same way.
 *
 * Styling uses only class names already used in src/admin (admin.css is generated from them; the
 * kit's stylesheet is not loaded by the admin console). The drawer and the dialog render into
 * document.body: the Dashboard's animated container would otherwise make their `position: fixed`
 * relative to it instead of the window.
 */

const academy = (id: string) => (PROFILES[id] ? academyLabel(PROFILES[id]!) : id);

const date = (iso: string | null | undefined) =>
  iso ? new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : '–';

/** status_reason is String(500) in tenancy. */
const REASON_MAX = 500;

const SESSION_EXPIRED = 'Your session has expired. Sign in again.';
const UNREACHABLE = "Couldn't reach the service. Please try again.";

type Load = 'loading' | 'error' | 'ready';
type Decision = 'approve' | 'reject';

const BADGE = 'inline-flex items-center gap-1 font-medium px-2 py-0.5 rounded bg-[#F1F5F9]';

const StatusBadge: React.FC<{ status: string }> = ({ status }) =>
  status === AWAITING_APPROVAL ? (
    <span className={`${BADGE} text-[#7E22CE]`}>Awaiting approval</span>
  ) : status === AWAITING_VERIFICATION ? (
    <span className={`${BADGE} text-[#64748B]`}>Waiting for email verification</span>
  ) : (
    <span className={`${BADGE} text-[#475569]`}>{status}</span>
  );

/** An error with a retry, in the console's own classes (the kit's ErrorState has no CSS here). */
const LoadError: React.FC<{ title: string; onRetry: () => void; children: React.ReactNode }> = ({ title, onRetry, children }) => (
  <div role="alert" className="p-4 rounded-lg border border-[#E2E8F0] bg-[#F6F8FB] text-xs space-y-3">
    <div className="font-semibold text-[#B91C1C]">{title}</div>
    <p className="text-[#475569]">{children}</p>
    <button type="button" className={BTN_SECONDARY} onClick={onRetry}>
      Try again
    </button>
  </div>
);

export const OrganisationApprovalQueue: React.FC<{
  /** Called with the number of organisations awaiting approval (verified ones only), after every load. */
  onCountChange?: (count: number) => void;
  /** Shows a short confirmation (the Dashboard's toast). */
  onNotify: (message: string) => void;
  /** Called when the API answers 401: the token is no longer valid. */
  onSessionExpired?: () => void;
  /** Changing it reloads the queue (the Dashboard's "Refresh metrics"). */
  refreshKey?: number;
}> = ({ onCountChange, onNotify, onSessionExpired, refreshKey = 0 }) => {
  const uid = useId();
  const [load, setLoad] = useState<Load>('loading');
  const [loadError, setLoadError] = useState<string>('');
  const [orgs, setOrgs] = useState<AdminOrganisation[]>([]);
  const [query, setQuery] = useState('');

  const [selected, setSelected] = useState<AdminOrganisation | null>(null);
  const [detail, setDetail] = useState<AdminOrganisationDetail | null>(null);
  const [detailLoad, setDetailLoad] = useState<Load>('loading');
  const [detailError, setDetailError] = useState<string>('');

  const [decision, setDecision] = useState<Decision | null>(null);
  const [reason, setReason] = useState('');
  const [sending, setSending] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  const reviewButton = useRef<HTMLButtonElement | null>(null);
  const drawerRef = useRef<HTMLDivElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  /** Incremented on every open and close; a detail response for an older number is dropped. */
  const reviewSeq = useRef(0);
  // The Dashboard passes these inline; keeping them in refs stops `refresh` from changing each render.
  const sessionExpired = useRef(onSessionExpired);
  sessionExpired.current = onSessionExpired;

  const refresh = useCallback(async () => {
    setLoad('loading');
    try {
      const list = await listQueueOrganisations();
      setOrgs(list);
      setLoad('ready');
      onCountChange?.(list.filter((o) => o.status === AWAITING_APPROVAL).length);
    } catch (err) {
      const expired = err instanceof ApiError && err.status === 401;
      setLoadError(expired ? SESSION_EXPIRED : "The list of organisations awaiting approval couldn't be loaded.");
      setLoad('error');
      if (expired) sessionExpired.current?.();
    }
  }, [onCountChange]);

  useEffect(() => {
    void refresh();
  }, [refresh, refreshKey]);

  const openReview = async (org: AdminOrganisation, button: HTMLButtonElement) => {
    const seq = ++reviewSeq.current;
    reviewButton.current = button;
    setSelected(org);
    setDetail(null);
    setDetailLoad('loading');
    try {
      const d = await getOrganisation(org.id);
      if (seq !== reviewSeq.current) return; // the drawer closed or moved on meanwhile
      setDetail(d);
      setDetailLoad('ready');
    } catch (err) {
      if (seq !== reviewSeq.current) return;
      const expired = err instanceof ApiError && err.status === 401;
      setDetailError(expired ? SESSION_EXPIRED : "Its details couldn't be loaded. You can still close this panel.");
      setDetailLoad('error');
      if (expired) sessionExpired.current?.();
    }
  };

  const closeReview = useCallback(() => {
    reviewSeq.current++;
    setSelected(null);
    setDetail(null);
    setDecision(null);
    setActionError(null);
    setReason('');
    reviewButton.current?.focus();
  }, []);

  const closeConfirm = useCallback(() => {
    setDecision(null);
    setActionError(null);
  }, []);

  const openConfirm = (d: Decision) => {
    setReason('');
    setActionError(null);
    setDecision(d);
  };

  // Escape closes the dialog first, then the drawer; never while a decision is being sent.
  useEffect(() => {
    if (!selected) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape' || sending) return;
      if (decision) closeConfirm();
      else closeReview();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [selected, decision, sending, closeConfirm, closeReview]);

  // Move focus into whichever surface just opened.
  useEffect(() => {
    if (selected && !decision) drawerRef.current?.focus();
  }, [selected, decision]);
  useEffect(() => {
    if (decision) dialogRef.current?.focus();
  }, [decision]);

  const decide = async () => {
    if (!selected || !decision || sending) return;
    const trimmed = reason.trim();
    if (decision === 'reject' && !trimmed) {
      setActionError('Give a reason for rejecting this organisation.');
      return;
    }
    setSending(true);
    setActionError(null);
    const name = selected.name;
    try {
      if (decision === 'approve') await approveOrganisation(selected.id, trimmed);
      else await rejectOrganisation(selected.id, trimmed);
      closeReview();
      onNotify(
        decision === 'approve'
          ? `${name} approved. Its administrator can now sign in.`
          : `${name} rejected. Its registration is archived.`
      );
      await refresh();
    } catch (err) {
      const status = err instanceof ApiError ? err.status : 0;
      if (status === 409) {
        closeReview();
        onNotify(`${name} is no longer awaiting approval.`);
        await refresh();
      } else if (status === 404) {
        closeReview();
        onNotify(`${name} no longer exists.`);
        await refresh();
      } else if (status === 401) {
        setActionError(SESSION_EXPIRED);
        sessionExpired.current?.();
      } else if (status === 403) {
        setActionError(`You don't have permission to ${decision} organisations.`);
      } else {
        setActionError(UNREACHABLE);
      }
    } finally {
      setSending(false);
    }
  };

  const q = query.trim().toLowerCase();
  const visible = q ? orgs.filter((o) => o.name.toLowerCase().includes(q) || o.slug.toLowerCase().includes(q)) : orgs;

  // Decisions follow the status the drawer fetched, never the possibly stale list row.
  const actionable = detailLoad === 'ready' && detail?.status === AWAITING_APPROVAL;
  const footerNote =
    detailLoad === 'ready' && detail && !actionable
      ? detail.status === AWAITING_VERIFICATION
        ? 'Waiting for the administrator to verify their email.'
        : 'No longer awaiting approval.'
      : null;
  const rejecting = decision === 'reject';

  return (
    <section className={PANEL} aria-labelledby={`${uid}-title`}>
      <PanelHeader
        title={<span id={`${uid}-title`}>Organisations awaiting approval</span>}
        subtitle="Verified registrations can be approved or rejected; unverified ones wait for the administrator's email."
        action={
          load === 'ready' && orgs.length > 0 ? (
            <div className="relative">
              <Search className="w-4 h-4 text-[#475569] absolute left-3 top-2.5" />
              <input
                type="text"
                aria-label="Search organisations awaiting approval"
                placeholder="Search by name or short name..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="w-full pl-9 pr-3 py-1.5 text-xs rounded-lg border border-[#E2E8F0] focus:outline-none focus:ring-2 focus:ring-[#9333EA] bg-[#F6F8FB]"
              />
            </div>
          ) : undefined
        }
      />

      {load === 'loading' && (
        <p className="py-8 text-center text-[#475569] text-xs" role="status">
          Loading organisations…
        </p>
      )}
      {load === 'error' && (
        <div className="p-4">
          <LoadError title="Couldn't load the approval queue" onRetry={() => void refresh()}>
            {loadError}
          </LoadError>
        </div>
      )}
      {load === 'ready' && (
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="bg-[#F6F8FB] border-b border-[#E2E8F0] text-[#475569] font-semibold">
                <th className="py-3 px-4">Organisation</th>
                <th className="py-3 px-4">Academy type</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Registered</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#F1F5F9] text-[#12233F]">
              {visible.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-8 text-center text-[#475569]">
                    {orgs.length === 0 ? 'No organisations are waiting for approval.' : 'No organisations match the search.'}
                  </td>
                </tr>
              ) : (
                visible.map((o) => (
                  <tr key={o.id} className="hover:bg-[#F6F8FB] transition-colors">
                    <td className="py-3 px-4">
                      <div className="font-semibold text-[#12233F]">{o.name}</div>
                      <div className="text-[11px] text-[#64748B] font-mono">{o.slug}</div>
                    </td>
                    <td className="py-3 px-4">
                      <span className={`${BADGE} text-[#7E22CE]`}>{academy(o.academy_type)}</span>
                    </td>
                    <td className="py-3 px-4">
                      <StatusBadge status={o.status} />
                    </td>
                    <td className="py-3 px-4 text-[#475569]">{date(o.created_at)}</td>
                    <td className="py-3 px-4 text-right">
                      <button
                        type="button"
                        className={BTN_SECONDARY}
                        aria-label={`Review ${o.name}`}
                        onClick={(e) => void openReview(o, e.currentTarget)}
                      >
                        Review
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      )}

      {/* REVIEW DRAWER (portal: see the note at the top) */}
      {selected &&
        createPortal(
          <div className="fixed inset-0 z-50 overflow-hidden">
            <div className="absolute inset-0 bg-[#12233F]/50 backdrop-blur-xs transition-opacity" onClick={() => !sending && closeReview()} />
            <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
              <div
                ref={drawerRef}
                role="dialog"
                aria-modal="true"
                aria-labelledby={`${uid}-drawer-title`}
                tabIndex={-1}
                className="w-screen max-w-md bg-[#FFFFFF] shadow-2xl border-l border-[#E2E8F0] flex flex-col focus:outline-none"
              >
                <div className="p-5 border-b border-[#E2E8F0] flex items-center justify-between bg-[#F6F8FB]">
                  <div className="flex items-center gap-2">
                    <Building2 className="w-4 h-4 text-[#7E22CE]" />
                    <span id={`${uid}-drawer-title`} className="text-sm font-bold text-[#12233F]">
                      Review {selected.name}
                    </span>
                  </div>
                  <button
                    type="button"
                    aria-label="Close"
                    onClick={closeReview}
                    disabled={sending}
                    className="p-1 rounded-md text-[#475569] hover:text-[#12233F] hover:bg-[#FFFFFF]"
                  >
                    <X className="w-5 h-5" />
                  </button>
                </div>

                <div className="flex-1 overflow-y-auto p-6 space-y-6">
                  {detailLoad === 'loading' && (
                    <p className="text-xs text-[#475569]" role="status">
                      Loading details…
                    </p>
                  )}
                  {detailLoad === 'error' && (
                    <LoadError
                      title="Couldn't load this organisation"
                      onRetry={() => reviewButton.current && void openReview(selected, reviewButton.current)}
                    >
                      {detailError}
                    </LoadError>
                  )}
                  {detailLoad === 'ready' && detail && (
                    <div className="space-y-3">
                      <h4 className="text-xs font-bold uppercase tracking-wider text-[#475569]">Registration</h4>
                      <dl className="p-3.5 rounded-lg bg-[#F6F8FB] border border-[#E2E8F0] space-y-2.5 text-xs">
                        {(
                          [
                            ['Organisation', detail.name],
                            ['Short name', detail.slug],
                            ['Academy type', academy(detail.academy_type)],
                            ...(detail.requested_academy_type
                              ? [['Requested package change', academy(detail.requested_academy_type)] as [string, React.ReactNode]]
                              : []),
                            ['Country', detail.country || '–'],
                            // The detail endpoint has no plan; the list row it was opened from does.
                            ['Plan', selected.plan ?? '–'],
                            ['Trial ends', date(selected.trial_ends_at ?? detail.entitlement?.trial_ends_at)],
                            ['Registered', date(detail.created_at)],
                            ['Status', <StatusBadge status={detail.status} />],
                            ['Email verified', detail.status === AWAITING_VERIFICATION ? 'No' : 'Yes'],
                            ['Administrator email', detail.admin_email ?? 'Not available from the API yet']
                          ] as [string, React.ReactNode][]
                        ).map(([label, value]) => (
                          <div key={label} className="flex items-center justify-between">
                            <dt className="text-[#475569]">{label}:</dt>
                            <dd className="font-medium text-[#12233F]">{value}</dd>
                          </div>
                        ))}
                      </dl>
                    </div>
                  )}
                </div>

                <div className="p-4 border-t border-[#E2E8F0] bg-[#F6F8FB] flex items-center justify-end gap-2">
                  {footerNote && <span className="text-xs text-[#64748B] flex-1">{footerNote}</span>}
                  <button type="button" onClick={closeReview} disabled={sending} className={BTN_SECONDARY}>
                    Close
                  </button>
                  <button type="button" onClick={() => openConfirm('reject')} disabled={!actionable} className={BTN_DANGER}>
                    <X className="w-3.5 h-3.5" />
                    Reject
                  </button>
                  <button type="button" onClick={() => openConfirm('approve')} disabled={!actionable} className={BTN_PRIMARY}>
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    Approve
                  </button>
                </div>
              </div>
            </div>

            {/* DECISION CONFIRMATION */}
            {decision && (
              <div className="fixed inset-0 z-50 bg-[#12233F]/40 backdrop-blur-xs flex items-center justify-center p-4">
                <div
                  ref={dialogRef}
                  role="dialog"
                  aria-modal="true"
                  aria-labelledby={`${uid}-confirm-title`}
                  aria-describedby={`${uid}-confirm-text`}
                  tabIndex={-1}
                  className="w-full max-w-md bg-[#FFFFFF] rounded-xl shadow-2xl border border-[#E2E8F0] overflow-hidden focus:outline-none"
                >
                  <div className="p-4 border-b border-[#E2E8F0] flex items-center justify-between bg-[#F6F8FB]">
                    <h3 id={`${uid}-confirm-title`} className="text-sm font-bold text-[#12233F]">
                      {rejecting ? 'Reject' : 'Approve'} {selected.name}?
                    </h3>
                    <button type="button" aria-label="Cancel" onClick={closeConfirm} disabled={sending} className="text-[#475569] hover:text-[#12233F]">
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                  <div className="p-5 space-y-4 text-xs">
                    <p id={`${uid}-confirm-text`} className="text-[#475569]">
                      {rejecting
                        ? 'The registration is archived and its administrator cannot sign in.'
                        : 'The organisation becomes active and its administrator can sign in.'}
                    </p>
                    <div>
                      <label htmlFor={`${uid}-reason`} className="block font-semibold text-[#12233F] mb-1">
                        {rejecting ? 'Reason (required)' : 'Reason (optional)'}
                      </label>
                      <textarea
                        id={`${uid}-reason`}
                        value={reason}
                        maxLength={REASON_MAX}
                        required={rejecting}
                        onChange={(e) => setReason(e.target.value)}
                        disabled={sending}
                        className="w-full p-2 bg-[#FFFFFF] text-[#12233F] border border-[#E2E8F0] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#9333EA]"
                      />
                    </div>
                    {actionError && (
                      <div role="alert" className="p-3 bg-[#F1F5F9] border border-[#E2E8F0] rounded-lg text-[11px] text-[#B91C1C]">
                        {actionError}
                      </div>
                    )}
                    <div className="flex justify-end gap-2 pt-2">
                      <button
                        type="button"
                        onClick={closeConfirm}
                        disabled={sending}
                        className="px-3 py-1.5 rounded-lg border border-[#E2E8F0] hover:bg-[#F1F5F9] text-[#475569]"
                      >
                        Cancel
                      </button>
                      <button
                        type="button"
                        onClick={() => void decide()}
                        disabled={sending || (rejecting && !reason.trim())}
                        aria-busy={sending || undefined}
                        className={rejecting ? BTN_DANGER : 'px-4 py-1.5 rounded-lg bg-[#F65B66] text-white font-semibold hover:bg-[#E9505C]'}
                      >
                        {sending ? (rejecting ? 'Rejecting…' : 'Approving…') : rejecting ? 'Reject' : 'Approve'}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>,
          document.body
        )}
    </section>
  );
};
