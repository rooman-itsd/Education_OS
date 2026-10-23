import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { Button } from "@eos/ui-kit";
import { APP_URL } from "../content";
import { PublicApiError, verifyRegistration, type VerifiedOrganisation } from "../../api/public-client";

/**
 * The steps after POST /tenancy/register (ADR-0005): the organisation is `pending_verification` until
 * the administrator proves they control the email address with the token tenancy issued; POST
 * /tenancy/register/verify moves it to `pending_approval`, the only state the super admin can approve.
 *
 * - Where the API returns the token in the register response (EOS_DEV_MODE=true: local and staging),
 *   VerifyEmail confirms it straight away, as apps/frontend/src/auth/SignUp.tsx does.
 * - Otherwise (production) the token arrives by email; the visitor enters it here, or opens the
 *   emailed link, which lands on the public site's verify route (pages/VerifyPage.tsx).
 *
 * The token is never logged or stored; the verify route removes it from the address bar.
 */

const INVALID_TOKEN =
  "This code is invalid, has expired or has already been used. Check the latest email, or register again if it is more than 48 hours old.";

export function VerifyEmail({
  email,
  initialToken = "",
  autoSubmit = false,
  onVerified,
}: {
  email?: string;
  initialToken?: string;
  autoSubmit?: boolean;
  onVerified: (org: VerifiedOrganisation) => void;
}) {
  const uid = useId();
  const [token, setToken] = useState(initialToken);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const started = useRef(false);

  const confirm = async (value: string) => {
    const code = value.trim();
    if (!code) {
      setError("Enter the verification code from the email.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      onVerified(await verifyRegistration(code));
    } catch (err) {
      setError(
        err instanceof PublicApiError && err.status === 400
          ? INVALID_TOKEN
          : "Couldn't reach the service. Please check your connection and try again.",
      );
    } finally {
      setBusy(false);
    }
  };

  // Dev/staging token or an emailed link: confirm once, without waiting for a click.
  useEffect(() => {
    if (!autoSubmit || !initialToken || started.current) return;
    started.current = true;
    void confirm(initialToken);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoSubmit, initialToken]);

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (!busy) void confirm(token);
  };

  return (
    <div className="wpc-container wpc-reg__done">
      <span className="wpc-reg__done-mark" aria-hidden>
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="3" y="5" width="18" height="14" rx="2" />
          <path d="M3.5 6.5l8.5 6.5 8.5-6.5" />
        </svg>
      </span>
      <h1 className="wpc-reg__title">Check your email to confirm your address</h1>
      <p className="wpc-reg__lead">
        {email ? (
          <>
            We sent a verification code to <strong>{email}</strong>.
          </>
        ) : (
          "Enter the verification code from your email."
        )}{" "}
        Confirming the address proves you control it; the Education OS team then reviews your organisation.
      </p>

      {busy && autoSubmit && !error ? (
        <p className="wpc-reg__hint" role="status">
          Confirming your email address…
        </p>
      ) : (
        <form className="wpc-reg__verify" onSubmit={onSubmit} noValidate>
          <div className="wpc-field">
            <label htmlFor={`${uid}-token`}>Verification code</label>
            <input
              id={`${uid}-token`}
              type="text"
              autoComplete="one-time-code"
              autoCapitalize="none"
              spellCheck={false}
              value={token}
              aria-invalid={error ? true : undefined}
              aria-describedby={error ? `${uid}-token-err` : undefined}
              onChange={(e) => setToken(e.target.value)}
            />
            {error && (
              <p id={`${uid}-token-err`} className="wpc-reg__err" role="alert">
                {error}
              </p>
            )}
          </div>
          <div className="wpc-reg__actions">
            <Button variant="primary" type="submit" disabled={busy} aria-busy={busy || undefined}>
              {busy ? "Confirming…" : "Confirm email"}
            </Button>
          </div>
        </form>
      )}
    </div>
  );
}

/** What the visitor sees once the email is confirmed, from the status tenancy returned. */
export function RegistrationOutcome({
  status,
  email,
  onHome,
}: {
  status: string;
  email?: string;
  onHome: () => void;
}) {
  const active = status === "active";
  return (
    <div className="wpc-container wpc-reg__done" role="status">
      <span className="wpc-reg__done-mark" aria-hidden>
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
          <path d="M5 12.5l4.5 4.5L19 7.5" />
        </svg>
      </span>
      {active ? (
        <>
          <h1 className="wpc-reg__title">Your organisation is ready</h1>
          <p className="wpc-reg__lead">Your email is confirmed and your organisation is active. You can sign in now.</p>
        </>
      ) : (
        <>
          <h1 className="wpc-reg__title">Waiting for approval</h1>
          <p className="wpc-reg__lead">
            Your email is confirmed and your organisation registration is waiting for approval by the Education OS
            administration team.
          </p>
          <ol className="wpc-reg__next">
            <li>The Education OS team reviews your organisation and academy package.</li>
            <li>
              Once approved, sign in as the organisation administrator
              {email ? (
                <>
                  {" "}
                  with <strong>{email}</strong>
                </>
              ) : null}
              .
            </li>
          </ol>
        </>
      )}
      <div className="wpc-reg__actions">
        {active && (
          <a className="eos-btn eos-btn--primary" href={APP_URL}>
            Sign in
          </a>
        )}
        <a
          className="wpc-link"
          href="#/"
          onClick={(e) => {
            e.preventDefault();
            onHome();
          }}
        >
          Back to home
        </a>
      </div>
    </div>
  );
}
