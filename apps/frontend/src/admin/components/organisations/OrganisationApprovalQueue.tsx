import React, { useCallback, useEffect, useId, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { ErrorState } from '@eos/ui-kit';
import { ApiError } from '../../../api/client';
import { Building2, CheckCircle2, Search, X } from '../../lib/icons';
import { PANEL, PanelHeader, BTN_PRIMARY, BTN_SECONDARY } from '../ui/dashboard';
import { PROFILES, academyLabel } from '../../data/repo';
import {
  approveOrganisation,
  getOrganisation,
  listPendingOrganisations,
  type AdminOrganisation,
  type AdminOrganisationDetail
} from '../../lib/organisationsAdmin';

/**
 * The super admin's organisation approval queue (ADR-0005), on the existing Dashboard: organisations
 * whose administrator verified their email and that wait for approval (GET ?status=pending_approval),
 * a review drawer (GET /{id}) and an approve confirmation (POST /{id}/approve). Approval only ever
 * goes through the approve endpoint. After a decision the list is fetched again, so the count stays
 * true; a 409 means someone else already decided, and is handled the same way.
 *
 * Styling uses only class names already used in src/admin (admin.css is generated from them). The
 * drawer and the dialog render into document.body: the Dashboard's animated container would
 * otherwise make their `position: fixed` relative to it instead of the window.
 */

const academy = (id: string) => (PROFILES[id] ? academyLabel(PROFILES[id]!) : id);

const date = (iso: string | null | undefined) =>
  iso ? new Date(iso).toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }) : '–';

/** status_reason is String(500) in tenancy. */
const REASON_MAX = 500;

type Load = 'loading' | 'error' | 'ready';

export const OrganisationApprovalQueue: React.FC<{
  /** Called with the number of organisations waiting, after every load. */
  onCountChange?: (count: number) => void;
  /** Shows a short confirmation (the Dashboard's toast). */
  onNotify: (message: string) => void;
  /** Changing it reloads the queue (the Dashboard's "Refresh metrics"). */
  refreshKey?: number;
}> = ({ onCountChange, onNotify, refreshKey = 0 }) => {
  const uid = useId();
  const [load, setLoad] = useState<Load>('loading');
  const [orgs, setOrgs] = useState<AdminOrganisation[]>([]);
  const [query, setQuery] = useState('');

  const [selected, setSelected] = useState<AdminOrganisation | null>(null);
  const [detail, setDetail] = useState<AdminOrganisationDetail | null>(null);
  const [detailLoad, setDetailLoad] = useState<Load>('loading');

  const [confirming, setConfirming] = useState(false);
  const [reason, setReason] = useState('');
  const [sending, setSending] = useState(false);
  const [approveError, setApproveError] = useState<string | null>(null);

  const reviewButton = useRef<HTMLButtonElement | null>(null);
  const drawerRef = useRef<HTMLDivElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);

  const refresh = useCallback(async () => {
    setLoad('loading');
    try {
      const list = await listPendingOrganisations();
      setOrgs(list);
      setLoad('ready');
      onCountChange?.(list.length);
    } catch {
      setLoad('error');
    }
  }, [onCountChange]);

  useEffect(() => {
    void refresh();
  }, [refresh, refreshKey]);

  const openReview = async (org: AdminOrganisation, button: HTMLButtonElement) => {
    reviewButton.current = button;
    setSelected(org);
    setDetail(null);
    setDetailLoad('loading');
    try {
      setDetail(await getOrganisation(org.id));
      setDetailLoad('ready');
    } catch {
      setDetailLoad('error');
    }
  };

  const closeReview = useCallback(() => {
    setSelected(null);
    setDetail(null);
    setConfirming(false);
    setApproveError(null);
    setReason('');
    reviewButton.current?.focus();
  }, []);

  const closeConfirm = useCallback(() => {
    setConfirming(false);
    setApproveError(null);
  }, []);

  // Escape closes the dialog first, then the drawer; never while an approval is being sent.
  useEffect(() => {
    if (!selected) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== 'Escape' || sending) return;
      if (confirming) closeConfirm();
      else closeReview();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [selected, confirming, sending, closeConfirm, closeReview]);

  // Move focus into whichever surface just opened.
  useEffect(() => {
    if (selected && !confirming) drawerRef.current?.focus();
  }, [selected, confirming]);
  useEffect(() => {
    if (confirming) dialogRef.current?.focus();
  }, [confirming]);

  const approve = async () => {
    if (!selected || sending) return;
    setSending(true);
    setApproveError(null);
    const name = selected.name;
    try {
      await approveOrganisation(selected.id, reason);
      closeReview();
      onNotify(`${name} approved. Its administrator can now sign in.`);
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
      } else if (status === 403) {
        setApproveError("You don't have permission to approve organisations.");
      } else {
        setApproveError("Couldn't reach the service. Please try again.");
      }
    } finally {
      setSending(false);
    }
  };

  const q = query.trim().toLowerCase();
  const visible = q ? orgs.filter((o) => o.name.toLowerCase().includes(q) || o.slug.toLowerCase().includes(q)) : orgs;

  return (
    <section className={PANEL} aria-labelledby={`${uid}-title`}>
      <PanelHeader
        title={<span id={`${uid}-title`}>Organisations awaiting approval</span>}
        subtitle="Email verified; waiting for a super admin to approve the academic package."
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
          <ErrorState title="Couldn't load the approval queue" onRetry={() => void refresh()}>
            The list of organisations awaiting approval couldn't be loaded.
          </ErrorState>
        </div>
      )}
      {load === 'ready' && (
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="bg-[#F6F8FB] border-b border-[#E2E8F0] text-[#475569] font-semibold">
                <th className="py-3 px-4">Organisation</th>
                <th className="py-3 px-4">Academy type</th>
                <th className="py-3 px-4">Registered</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#F1F5F9] text-[#12233F]">
              {visible.length === 0 ? (
                <tr>
                  <td colSpan={4} className="py-8 text-center text-[#475569]">
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
                      <span className="inline-flex items-center gap-1 font-medium px-2 py-0.5 rounded bg-[#F1F5F9] text-[#7E22CE]">
                        {academy(o.academy_type)}
                      </span>
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
                  <ErrorState title="Couldn't load this organisation" onRetry={() => reviewButton.current && void openReview(selected, reviewButton.current)}>
                    Its details couldn't be loaded. You can still close this panel.
                  </ErrorState>
                )}
                {detailLoad === 'ready' && detail && (
                  <div className="space-y-3">
                    <h4 className="text-xs font-bold text-[#12233F] uppercase tracking-wider text-[#475569]">Registration</h4>
                    <dl className="p-3.5 rounded-lg bg-[#F6F8FB] border border-[#E2E8F0] space-y-2.5 text-xs">
                      {[
                        ['Organisation', detail.name],
                        ['Short name', detail.slug],
                        ['Academy type', academy(detail.academy_type)],
                        ...(detail.requested_academy_type ? [['Requested package change', academy(detail.requested_academy_type)]] : []),
                        ['Country', detail.country || '–'],
                        // The detail endpoint has no plan; the list row it was opened from does.
                        ['Plan', selected.plan ?? '–'],
                        ['Trial ends', date(selected.trial_ends_at ?? detail.entitlement?.trial_ends_at)],
                        ['Registered', date(detail.created_at)],
                        ['Status', detail.status === 'pending_approval' ? 'Awaiting approval' : detail.status],
                        ['Email verified', detail.status === 'pending_approval' ? 'Yes' : '–'],
                        ['Administrator email', detail.admin_email ?? 'Not available from the API yet']
                      ].map(([label, value]) => (
                        <div key={label} className="flex items-center justify-between">
                          <dt className="text-[#475569]">{label}:</dt>
                          <dd className="font-medium text-[#12233F]">{value}</dd>
                        </div>
                      ))}
                    </dl>
                  </div>
                )}
              </div>

              <div className="p-4 border-t border-[#E2E8F0] bg-[#F6F8FB] flex justify-end gap-2">
                <button type="button" onClick={closeReview} disabled={sending} className={BTN_SECONDARY}>
                  Close
                </button>
                <button
                  type="button"
                  onClick={() => setConfirming(true)}
                  disabled={detailLoad !== 'ready' || selected.status !== 'pending_approval'}
                  className={BTN_PRIMARY}
                >
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  Approve
                </button>
              </div>
            </div>
          </div>

          {/* APPROVE CONFIRMATION */}
          {confirming && (
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
                    Approve {selected.name}?
                  </h3>
                  <button type="button" aria-label="Cancel" onClick={closeConfirm} disabled={sending} className="text-[#475569] hover:text-[#12233F]">
                    <X className="w-4 h-4" />
                  </button>
                </div>
                <div className="p-5 space-y-4 text-xs">
                  <p id={`${uid}-confirm-text`} className="text-[#475569]">
                    The organisation becomes active and its administrator can sign in.
                  </p>
                  <div>
                    <label htmlFor={`${uid}-reason`} className="block font-semibold text-[#12233F] mb-1">
                      Reason (optional)
                    </label>
                    <textarea
                      id={`${uid}-reason`}
                      value={reason}
                      maxLength={REASON_MAX}
                      onChange={(e) => setReason(e.target.value)}
                      disabled={sending}
                      className="w-full p-2 bg-[#FFFFFF] text-[#12233F] border border-[#E2E8F0] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#9333EA]"
                    />
                  </div>
                  {approveError && (
                    <div role="alert" className="p-3 bg-[#F1F5F9] border border-[#E2E8F0] rounded-lg text-[11px] text-[#B91C1C]">
                      {approveError}
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
                      onClick={() => void approve()}
                      disabled={sending}
                      aria-busy={sending || undefined}
                      className="px-4 py-1.5 rounded-lg bg-[#F65B66] text-white font-semibold hover:bg-[#E9505C]"
                    >
                      {sending ? 'Approving…' : 'Approve'}
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
