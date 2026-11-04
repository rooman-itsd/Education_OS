import { useEffect, useRef, useState } from "react";
import { Button } from "@eos/ui-kit";
import { cancelBooking, checkInBooking, describeActionFailure, type Booking, type RowAction } from "../api/client";

export interface BookingActionsProps {
  booking: Booking;
  /** The booking in words, "Track · U19 sprints, Today · 07:00–09:00": part of every button's accessible name. */
  subject: string;
  /** Ask for a reason before cancelling (the managed list: facility-booking:booking:manage must give one). */
  requireReason: boolean;
  /** Called after an action succeeds, so the list loads again. */
  onDone: () => void;
}

/**
 * A row's "Check in" and "Cancel" buttons, each shown only when `booking.can` lists the action. Cancel opens an inline
 * confirm (with a reason field when one is required). While a request runs the row's buttons are disabled; a failure
 * is said in words on the row, from the status code, never the server's text. Leaving the page aborts the request.
 */
export function BookingActions({ booking, subject, requireReason, onDone }: BookingActionsProps) {
  const can = booking.can ?? [];
  const [confirming, setConfirming] = useState(false);
  const [reason, setReason] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const ctrl = useRef<AbortController | null>(null);
  const box = useRef<HTMLSpanElement>(null);
  const reopen = useRef(false);

  // The request in flight belongs to this row: abort it if the row or the widget goes away.
  useEffect(() => () => ctrl.current?.abort(), []);
  // A refresh after success hands the row a new booking (with its new `can`): the row is idle again.
  useEffect(() => {
    setPending(false);
  }, [booking]);
  // Back from the confirm without cancelling: focus returns to the Cancel button.
  useEffect(() => {
    if (!confirming && reopen.current) {
      reopen.current = false;
      box.current?.querySelector<HTMLButtonElement>("[data-action=cancel]")?.focus();
    }
  }, [confirming]);

  const showCheckIn = can.includes("check_in");
  const showCancel = can.includes("cancel");
  if (!showCheckIn && !showCancel) return null;

  const run = (action: RowAction) => {
    if (pending) return;
    const c = new AbortController();
    ctrl.current = c;
    setPending(true);
    setError(null);
    const call = action === "cancel" ? cancelBooking(booking.id, reason, c.signal) : checkInBooking(booking.id, c.signal);
    call.then(
      () => {
        if (c.signal.aborted) return;
        setConfirming(false);
        setReason("");
        onDone(); // stays pending until the refreshed booking arrives
      },
      (e: unknown) => {
        if (c.signal.aborted) return;
        setPending(false);
        setError(describeActionFailure(e, action));
      },
    );
  };

  const keep = () => {
    reopen.current = true;
    setConfirming(false);
    setReason("");
  };
  const reasonGiven = reason.trim().length > 0;
  const submitCancel = () => {
    if (!requireReason || reasonGiven) run("cancel");
  };

  return (
    <span ref={box} className="eos-fb__actions" aria-busy={pending || undefined}>
      {confirming ? (
        <span className="eos-fb__confirm">
          {requireReason ? (
            <label className="eos-fb__reason">
              <span>Reason for cancelling</span>
              <input
                className="eos-input"
                value={reason}
                autoFocus
                disabled={pending}
                onChange={(e) => setReason(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") submitCancel();
                  if (e.key === "Escape") keep();
                }}
              />
            </label>
          ) : (
            <span>Cancel this booking?</span>
          )}
          <span className="eos-fb__buttons">
            <Button
              size="sm"
              variant="danger"
              disabled={pending || (requireReason && !reasonGiven)}
              aria-label={`Cancel booking: ${subject}`}
              autoFocus={!requireReason}
              onClick={submitCancel}
            >
              Cancel booking
            </Button>
            <Button size="sm" variant="ghost" disabled={pending} aria-label={`Keep booking: ${subject}`} onClick={keep}>
              Keep booking
            </Button>
          </span>
        </span>
      ) : (
        <span className="eos-fb__buttons">
          {showCheckIn && (
            <Button size="sm" variant="secondary" disabled={pending} aria-label={`Check in: ${subject}`} onClick={() => run("check_in")}>
              Check in
            </Button>
          )}
          {showCancel && (
            <Button
              data-action="cancel"
              size="sm"
              variant="ghost"
              disabled={pending}
              aria-label={`Cancel: ${subject}`}
              onClick={() => {
                setError(null);
                setConfirming(true);
              }}
            >
              Cancel
            </Button>
          )}
        </span>
      )}
      {error && (
        <span className="eos-fb__error" role="alert">
          {error}
        </span>
      )}
    </span>
  );
}
