import React, { useEffect, useId, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { X } from '../../lib/icons';
import { BTN_DANGER, BTN_PRIMARY } from '../ui/dashboard';
import { actionFailure } from '../../lib/adminErrors';

/** status_reason is String(500) in tenancy; billing's reason travels in an event, kept to the same length. */
export const REASON_MAX = 500;

/**
 * A confirmation that always asks why. Every super admin change is recorded with its reason (tenancy's status
 * change, billing's tenancy.entitlement.changed), so the button stays off until one is written. `extra` holds the
 * change's own field (the new plan, the trial's last day); `ready` says whether that field is filled in.
 * Escape and the close button cancel, except while the change is being sent.
 */
export const ReasonDialog: React.FC<{
  title: string;
  description: React.ReactNode;
  confirmLabel: string;
  busyLabel: string;
  danger?: boolean;
  extra?: React.ReactNode;
  ready?: boolean;
  onConfirm: (reason: string) => Promise<void>;
  onClose: () => void;
}> = ({ title, description, confirmLabel, busyLabel, danger = false, extra, ready = true, onConfirm, onClose }) => {
  const uid = useId();
  const [reason, setReason] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const reasonRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!extra) reasonRef.current?.focus();
  }, [extra]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !sending) onClose();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [onClose, sending]);

  const confirm = async () => {
    setSending(true);
    setError(null);
    try {
      await onConfirm(reason.trim());
    } catch (e) {
      setError(actionFailure(e));
      setSending(false);
    }
  };

  return createPortal(
    <div className="fixed inset-0 z-50 bg-[#12233F]/40 backdrop-blur-xs flex items-center justify-center p-4">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby={`${uid}-title`}
        aria-describedby={`${uid}-text`}
        className="w-full max-w-md bg-[#FFFFFF] rounded-xl shadow-2xl border border-[#E2E8F0] overflow-hidden"
      >
        <div className="p-4 border-b border-[#E2E8F0] flex items-center justify-between bg-[#F6F8FB]">
          <h3 id={`${uid}-title`} className="text-sm font-bold text-[#12233F]">
            {title}
          </h3>
          <button type="button" aria-label="Cancel" onClick={onClose} disabled={sending} className="text-[#475569] hover:text-[#12233F]">
            <X className="w-4 h-4" />
          </button>
        </div>
        <div className="p-5 space-y-4 text-xs">
          <p id={`${uid}-text`} className="text-[#475569]">
            {description}
          </p>
          {extra}
          <div>
            <label htmlFor={`${uid}-reason`} className="block font-semibold text-[#12233F] mb-1">
              Reason (required, kept in the audit trail)
            </label>
            <textarea
              ref={reasonRef}
              id={`${uid}-reason`}
              value={reason}
              maxLength={REASON_MAX}
              required
              onChange={(e) => setReason(e.target.value)}
              disabled={sending}
              className="w-full p-2 bg-[#FFFFFF] text-[#12233F] border border-[#E2E8F0] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#9333EA]"
            />
          </div>
          {error && (
            <div role="alert" className="p-3 bg-[#F1F5F9] border border-[#E2E8F0] rounded-lg text-[11px] text-[#B91C1C]">
              {error}
            </div>
          )}
          <div className="flex justify-end gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              disabled={sending}
              className="px-3 py-1.5 rounded-lg border border-[#E2E8F0] hover:bg-[#F1F5F9] text-[#475569]"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={() => void confirm()}
              disabled={sending || !ready || !reason.trim()}
              aria-busy={sending || undefined}
              className={danger ? BTN_DANGER : BTN_PRIMARY}
            >
              {sending ? busyLabel : confirmLabel}
            </button>
          </div>
        </div>
      </div>
    </div>,
    document.body
  );
};
