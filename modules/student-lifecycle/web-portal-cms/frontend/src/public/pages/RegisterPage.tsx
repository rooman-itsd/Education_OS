import { useEffect, useId, useState, type FormEvent } from "react";
import { Button, ErrorState } from "@eos/ui-kit";
import { APP_URL, type PublicRoute } from "../content";
import { BrandedLoader } from "../components/BrandedLoader";
import { AcademyPicker } from "../components/AcademyPicker";
import { RegistrationOutcome, VerifyEmail } from "../components/RegistrationSteps";
import {
  getAcademyTypes,
  PublicApiError,
  register,
  verifyRegistration,
  type AcademyType,
  type RegisteredOrganisation,
} from "../../api/public-client";

/**
 * Organisation registration: pick the academy package, enter the organisation and its first
 * administrator, accept the terms, submit to platform/tenancy POST /register (public). The form has
 * exactly the fields that endpoint accepts (RegistrationInput) and mirrors its rules, so a visitor
 * sees problems before submitting; whatever the server still rejects is shown against the field or
 * as one message. There is no plan field: every organisation starts on the free trial (billing),
 * and paid plans are chosen after approval.
 *
 * Lifecycle (platform/tenancy): register → `pending_verification` → POST /register/verify →
 * `pending_approval` → super admin approves → `active`. The administrator's email is verified with
 * the 48-hour token tenancy emails them; in dev mode (EOS_DEV_MODE=true) the register response carries
 * `verification_token`, and the page verifies with it at once. Otherwise it shows the "check your email"
 * step (components/RegistrationSteps.tsx VerifyEmail, shared with the `#/verify` page) where the code is
 * entered. Only after verification does the page show RegistrationOutcome: waiting for approval, or
 * active if tenancy auto-approved. It never claims approval itself and never calls an admin endpoint.
 */

/** platform/tenancy SLUG_RE and RESERVED (eos_tenancy/application/service.py). */
const SLUG_RE = /^[a-z0-9-]{3,40}$/;
const RESERVED = new Set(["admin", "api", "www", "app", "platform"]);
/**
 * Close to the server's email-validator (EmailStr): a dot-separated local part without leading,
 * trailing or doubled dots, and a domain of letter/number labels ending in a 2+ letter top level.
 * Lengths follow RFC 5321 and the identity_user column: 64 for the local part, 254 in all.
 */
const EMAIL_LOCAL_RE = /^[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+(\.[A-Za-z0-9!#$%&'*+/=?^_`{|}~-]+)*$/;
const EMAIL_DOMAIN_RE = /^([A-Za-z0-9]([A-Za-z0-9-]{0,61}[A-Za-z0-9])?\.)+[A-Za-z]{2,63}$/;
/** identity_user.name and tenancy organisation name are String(200). */
const NAME_MAX = 200;

export function isValidEmail(raw: string): boolean {
  const email = raw.trim();
  if (email.length > 254) return false;
  const at = email.lastIndexOf("@");
  if (at < 1) return false;
  const local = email.slice(0, at);
  const domain = email.slice(at + 1);
  return local.length <= 64 && EMAIL_LOCAL_RE.test(local) && EMAIL_DOMAIN_RE.test(domain);
}

type Field = "organisation_name" | "slug" | "academy_type" | "name" | "email" | "password" | "terms";
type Errors = Partial<Record<Field, string>>;

interface FormState {
  organisation_name: string;
  slug: string;
  academy_type: string;
  name: string;
  email: string;
  password: string;
  terms: boolean;
}

const EMPTY: FormState = {
  organisation_name: "",
  slug: "",
  academy_type: "",
  name: "",
  email: "",
  password: "",
  terms: false,
};

/** A short name suggested from the organisation name, until the visitor edits it themselves. */
export function suggestSlug(name: string): string {
  return name
    .toLowerCase()
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 40)
    .replace(/-+$/g, "");
}

export function validate(f: FormState): Errors {
  const e: Errors = {};
  const orgName = f.organisation_name.trim();
  if (orgName.length < 2) e.organisation_name = "Enter your organisation's name (at least 2 characters).";
  else if (orgName.length > 200) e.organisation_name = "Keep the name under 200 characters.";
  if (!SLUG_RE.test(f.slug)) e.slug = "Use 3–40 lowercase letters, numbers or hyphens.";
  else if (RESERVED.has(f.slug)) e.slug = "This short name is reserved. Choose another.";
  if (!f.academy_type) e.academy_type = "Choose your academy package.";
  const adminName = f.name.trim();
  if (!adminName) e.name = "Enter the administrator's name.";
  else if (adminName.length > NAME_MAX) e.name = "Keep the name under 200 characters.";
  if (!f.email.trim()) e.email = "Enter the administrator's email address.";
  else if (!isValidEmail(f.email)) e.email = "Enter a valid email address, like name@institution.edu.";
  if (f.password.length < 8) e.password = "Use at least 8 characters.";
  else if (!f.password.trim()) e.password = "The password can't be only spaces.";
  if (!f.terms) e.terms = "Accept the terms to continue.";
  return e;
}

const FIELD_ORDER: Field[] = ["academy_type", "organisation_name", "slug", "name", "email", "password", "terms"];

export function RegisterPage({ onNavigate }: { onNavigate: (route: PublicRoute) => void }) {
  const uid = useId();
  const [types, setTypes] = useState<AcademyType[]>([]);
  const [loadState, setLoadState] = useState<"loading" | "error" | "ready">("loading");
  const [form, setForm] = useState<FormState>(EMPTY);
  const [slugEdited, setSlugEdited] = useState(false);
  const [errors, setErrors] = useState<Errors>({});
  const [submitted, setSubmitted] = useState(false);
  const [sending, setSending] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  /** Registered, email not yet verified: the "check your email" step. `token` is prefilled only when a dev-mode auto-verify failed. */
  const [registered, setRegistered] = useState<{ org: RegisteredOrganisation; token: string } | null>(null);
  /** Verified: `status` is tenancy's answer, pending_approval unless it auto-approved. */
  const [done, setDone] = useState<{ org: RegisteredOrganisation; email: string; status: string } | null>(null);

  const loadTypes = () => {
    setLoadState("loading");
    getAcademyTypes()
      .then((t) => {
        setTypes(t);
        setLoadState("ready");
      })
      .catch(() => setLoadState("error"));
  };
  useEffect(loadTypes, []);

  const set = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    const next = { ...form, [key]: value };
    if (key === "organisation_name" && !slugEdited) next.slug = suggestSlug(String(value));
    setForm(next);
    // Once the visitor has tried to submit, keep the messages current as they fix things.
    if (submitted) setErrors(validate(next));
  };

  /** Move focus to a field; for the package, to the first card's radio. */
  const focusField = (f: Field) => {
    const el =
      f === "academy_type"
        ? document.querySelector<HTMLInputElement>(".wpc-ap__input")
        : document.getElementById(`${uid}-${f}`);
    el?.focus();
  };

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (sending) return;
    setSubmitted(true);
    setFormError(null);
    const found = validate(form);
    setErrors(found);
    const first = FIELD_ORDER.find((f) => found[f]);
    if (first) {
      focusField(first);
      return;
    }
    setSending(true);
    try {
      const org = await register({
        organisation_name: form.organisation_name.trim(),
        slug: form.slug,
        academy_type: form.academy_type,
        admin: { name: form.name.trim(), email: form.email.trim(), password: form.password },
        accepted_terms: true,
      });
      window.scrollTo({ top: 0 });
      if (org.verification_token) {
        // Dev mode: tenancy handed us the token instead of emailing it; verify straight away.
        try {
          const v = await verifyRegistration(org.verification_token);
          setDone({ org, email: form.email.trim(), status: v.status });
          return;
        } catch {
          // Fall through to the token step, prefilled, so the visitor can still finish.
        }
      }
      setRegistered({ org, token: org.verification_token ?? "" });
    } catch (err) {
      if (err instanceof PublicApiError) {
        if (err.status === 409) {
          setErrors((x) => ({ ...x, slug: "This short name is already taken. Choose another." }));
          focusField("slug");
        } else if (err.status === 403) {
          setFormError("New registrations are closed right now. Please try again later.");
        } else if (err.status === 400 && /slug/i.test(err.message)) {
          setErrors((x) => ({ ...x, slug: "Use 3–40 lowercase letters, numbers or hyphens, not a reserved word." }));
        } else if (err.status === 400 || err.status === 422) {
          setFormError("Some details weren't accepted. Please check the form and try again.");
        } else {
          setFormError("Couldn't reach the service. Please try again.");
        }
      } else {
        setFormError("Couldn't reach the service. Please check your connection and try again.");
      }
    } finally {
      setSending(false);
    }
  };

  const email = form.email.trim();

  if (done) {
    return (
      <div className="wpc-page wpc-reg">
        <RegistrationOutcome status={done.status} slug={done.org.slug} email={done.email} onHome={() => onNavigate("home")} />
      </div>
    );
  }

  if (registered) {
    return (
      <div className="wpc-page wpc-reg">
        <VerifyEmail
          email={email}
          initialToken={registered.token}
          laterLink
          onVerified={(v) => {
            setDone({ org: registered.org, email, status: v.status });
            window.scrollTo({ top: 0 });
          }}
        />
      </div>
    );
  }

  const err = (f: Field) =>
    errors[f] ? (
      <p id={`${uid}-${f}-err`} className="wpc-reg__err">
        {errors[f]}
      </p>
    ) : null;
  const a11y = (f: Field, hint?: boolean) => ({
    id: `${uid}-${f}`,
    "aria-invalid": errors[f] ? true : undefined,
    "aria-describedby": [hint ? `${uid}-${f}-hint` : "", errors[f] ? `${uid}-${f}-err` : ""].filter(Boolean).join(" ") || undefined,
  });

  return (
    <div className="wpc-page wpc-reg">
      <div className="wpc-container wpc-reg__inner">
        <header className="wpc-reg__head">
          <h1 className="wpc-reg__title">Create your organisation</h1>
          <p className="wpc-reg__lead">
            Choose your academy package and tell us who will run the account. Every organisation starts on the
            free trial; the Education OS team reviews each new academy before it goes live.
          </p>
        </header>

        {loadState === "loading" && <BrandedLoader label="Loading academy packages…" />}
        {loadState === "error" && (
          <ErrorState title="Couldn't load academy packages" onRetry={loadTypes}>
            The list of academy packages couldn't be loaded right now. Please try again.
          </ErrorState>
        )}

        {loadState === "ready" && (
          <form className="wpc-reg__form" onSubmit={onSubmit} noValidate>
            {formError && (
              <p className="wpc-reg__banner" role="alert">
                {formError}
              </p>
            )}

            <section className="wpc-reg__section" aria-labelledby="wpc-ap-label">
              <h2 id="wpc-ap-label" className="wpc-reg__h2">
                1. Academy package
              </h2>
              <p className="wpc-reg__hint" id={`${uid}-academy_type-hint`}>
                Your package sets the modules, roles and vocabulary your institution starts with. You can request a
                change later; each change is approved by the Education OS team.
              </p>
              <AcademyPicker
                types={types}
                value={form.academy_type}
                onChange={(id) => set("academy_type", id)}
                describedBy={[`${uid}-academy_type-hint`, errors.academy_type ? `${uid}-academy_type-err` : ""].filter(Boolean).join(" ")}
              />
              {err("academy_type")}
            </section>

            <div className="wpc-reg__cols">
              <section className="wpc-reg__section" aria-labelledby={`${uid}-org-h`}>
                <h2 id={`${uid}-org-h`} className="wpc-reg__h2">
                  2. Organisation
                </h2>
                <div className="wpc-field">
                  <label htmlFor={`${uid}-organisation_name`}>Organisation name</label>
                  <input
                    {...a11y("organisation_name")}
                    type="text"
                    autoComplete="organization"
                    maxLength={NAME_MAX}
                    value={form.organisation_name}
                    onChange={(e) => set("organisation_name", e.target.value)}
                  />
                  {err("organisation_name")}
                </div>
                <div className="wpc-field">
                  <label htmlFor={`${uid}-slug`}>Short name</label>
                  <input
                    {...a11y("slug", true)}
                    type="text"
                    autoCapitalize="none"
                    spellCheck={false}
                    maxLength={40}
                    value={form.slug}
                    onChange={(e) => {
                      setSlugEdited(true);
                      set("slug", e.target.value.toLowerCase());
                    }}
                  />
                  <p className="wpc-reg__hint" id={`${uid}-slug-hint`}>
                    Identifies your organisation at sign-in. 3–40 lowercase letters, numbers or hyphens.
                  </p>
                  {err("slug")}
                </div>
              </section>

              <section className="wpc-reg__section" aria-labelledby={`${uid}-admin-h`}>
                <h2 id={`${uid}-admin-h`} className="wpc-reg__h2">
                  3. Organisation administrator
                </h2>
                <div className="wpc-field">
                  <label htmlFor={`${uid}-name`}>Full name</label>
                  <input
                    {...a11y("name")}
                    type="text"
                    autoComplete="name"
                    maxLength={NAME_MAX}
                    value={form.name}
                    onChange={(e) => set("name", e.target.value)}
                  />
                  {err("name")}
                </div>
                <div className="wpc-field">
                  <label htmlFor={`${uid}-email`}>Work email</label>
                  <input
                    {...a11y("email", true)}
                    type="email"
                    autoComplete="email"
                    maxLength={254}
                    value={form.email}
                    onChange={(e) => set("email", e.target.value)}
                  />
                  <p className="wpc-reg__hint" id={`${uid}-email-hint`}>
                    You'll sign in with this email once your organisation is approved.
                  </p>
                  {err("email")}
                </div>
                <div className="wpc-field">
                  <label htmlFor={`${uid}-password`}>Password</label>
                  <input
                    {...a11y("password", true)}
                    type="password"
                    autoComplete="new-password"
                    value={form.password}
                    onChange={(e) => set("password", e.target.value)}
                  />
                  <p className="wpc-reg__hint" id={`${uid}-password-hint`}>
                    At least 8 characters.
                  </p>
                  {err("password")}
                </div>
              </section>
            </div>

            <div className="wpc-reg__submit">
              <label className="wpc-reg__terms">
                <input
                  {...a11y("terms")}
                  type="checkbox"
                  checked={form.terms}
                  onChange={(e) => set("terms", e.target.checked)}
                />
                <span>I accept the Education OS terms of service on behalf of this organisation.</span>
              </label>
              {err("terms")}
              <div className="wpc-reg__actions">
                <Button variant="primary" type="submit" disabled={sending} aria-busy={sending || undefined}>
                  {sending ? "Submitting…" : "Submit registration"}
                </Button>
                <a className="wpc-link" href={APP_URL}>
                  Already registered? Sign in
                </a>
              </div>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
