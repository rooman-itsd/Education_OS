import { useEffect, useState, type FormEvent } from "react";
import { Button } from "@eos/ui-kit";
import { api, ApiError } from "../api/client";
import { AuthLayout } from "./AuthLayout";

interface AcademyType {
  id: string;
  title: string;
  description: string;
}

interface Registered {
  id: string;
  slug: string;
  verification_token?: string;
}

export function SignUp({ onDone, onLogin }: { onDone: (slug: string) => void; onLogin: () => void }) {
  const [types, setTypes] = useState<AcademyType[]>([]);
  const [form, setForm] = useState({ organisation_name: "", slug: "", academy_type: "", name: "", email: "", password: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [registered, setRegistered] = useState<Registered | null>(null);
  const [verified, setVerified] = useState<{ status: string } | null>(null);
  const [token, setToken] = useState("");

  useEffect(() => {
    api<AcademyType[]>("/tenancy/academy-types").then((t) => {
      setTypes(t);
      setForm((f) => ({ ...f, academy_type: f.academy_type || t[0]?.id || "" }));
    });
  }, []);

  const slugFromName = (name: string) => name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 40);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const r = await api<Registered>("/tenancy/register", {
        method: "POST",
        json: {
          organisation_name: form.organisation_name,
          slug: form.slug || slugFromName(form.organisation_name),
          academy_type: form.academy_type,
          admin: { name: form.name, email: form.email, password: form.password },
          accepted_terms: true,
        },
      });
      setRegistered(r);
      if (r.verification_token) setToken(r.verification_token);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const verify = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const org = await api<{ status: string }>("/tenancy/register/verify", { method: "POST", json: { token } });
      if (org.status === "active") onDone(registered!.slug);
      else setVerified(org);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const backToLogin = (
    <a href="#login" onClick={(e) => { e.preventDefault(); onLogin(); }}>Back to sign in</a>
  );

  if (verified) {
    return (
      <AuthLayout>
        <div className="eos-auth__card">
          <h1>Email verified</h1>
          <p>{form.organisation_name} is waiting for the platform administrator to approve its academic package. You will get an email when it is approved, and can then sign in.</p>
          <p className="eos-auth__footnote">{backToLogin}</p>
        </div>
      </AuthLayout>
    );
  }

  if (registered) {
    return (
      <AuthLayout>
        <form className="eos-auth__card" onSubmit={verify}>
          <h1>Verify your email</h1>
          <p>We sent a verification token to {form.email}. Paste it below to activate {form.organisation_name}.</p>
          <label className="eos-field">
            Verification token
            <input className="eos-input" value={token} onChange={(e) => setToken(e.target.value)} required />
          </label>
          {error && <p className="eos-form-error" role="alert">{error}</p>}
          <Button variant="primary" type="submit" disabled={busy}>Activate organisation</Button>
        </form>
      </AuthLayout>
    );
  }

  const chosen = types.find((t) => t.id === form.academy_type);
  return (
    <AuthLayout footnote="Start a free 30-day trial. Pick the academy type and you get the common platform plus the features of that field.">
      <form className="eos-auth__card" onSubmit={submit}>
        <h1>Register your organisation</h1>
        <label className="eos-field">
          Organisation name
          <input className="eos-input" value={form.organisation_name} onChange={(e) => setForm({ ...form, organisation_name: e.target.value, slug: slugFromName(e.target.value) })} required />
        </label>
        <label className="eos-field">
          Short name <span className="eos-field__hint">(used in your URL)</span>
          <input className="eos-input" value={form.slug} onChange={(e) => setForm({ ...form, slug: e.target.value })} pattern="[a-z0-9-]{3,40}" required />
        </label>
        <label className="eos-field">
          Academy type
          <select className="eos-select" value={form.academy_type} onChange={(e) => setForm({ ...form, academy_type: e.target.value })}>
            {types.map((t) => (
              <option key={t.id} value={t.id}>{t.title}</option>
            ))}
          </select>
          {chosen && <span className="eos-field__hint">{chosen.description}</span>}
        </label>
        <label className="eos-field">
          Your name
          <input className="eos-input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required autoComplete="name" />
        </label>
        <label className="eos-field">
          Work email
          <input className="eos-input" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required autoComplete="email" />
        </label>
        <label className="eos-field">
          Password
          <input className="eos-input" type="password" minLength={8} value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required autoComplete="new-password" />
        </label>
        {error && <p className="eos-form-error" role="alert">{error}</p>}
        <Button variant="primary" type="submit" disabled={busy}>{busy ? "Creating…" : "Create organisation"}</Button>
        <p className="eos-auth__footnote">
          Already registered? <a href="#login" onClick={(e) => { e.preventDefault(); onLogin(); }}>Sign in</a>
        </p>
      </form>
    </AuthLayout>
  );
}
