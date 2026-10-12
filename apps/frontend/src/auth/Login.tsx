import { useState, type FormEvent } from "react";
import { Button } from "@eos/ui-kit";
import { ApiError } from "../api/client";
import { AuthLayout } from "./AuthLayout";
import { login } from "./session";

export function Login({ slug, onDone, onSignUp }: { slug?: string; onDone: () => void; onSignUp: () => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [org, setOrg] = useState(slug ?? "");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password, org || undefined);
      onDone();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : String(err);
      setError(msg.includes("pending_approval") ? "Your organisation's academic package is waiting for platform approval. Try again once you receive the approval email." : msg);
    } finally {
      setBusy(false);
    }
  };

  return (
    <AuthLayout footnote="Each organisation sees only its own data.">
      <form className="eos-auth__card" onSubmit={submit}>
        <h1>Sign in</h1>
        <label className="eos-field">
          Email
          <input className="eos-input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoFocus autoComplete="email" />
        </label>
        <label className="eos-field">
          Password
          <input className="eos-input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} required autoComplete="current-password" />
        </label>
        <label className="eos-field">
          Organisation short name <span className="eos-field__hint">(only if your email is in more than one)</span>
          <input className="eos-input" value={org} onChange={(e) => setOrg(e.target.value)} />
        </label>
        {error && <p className="eos-form-error" role="alert">{error}</p>}
        <Button variant="primary" type="submit" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</Button>
        <p className="eos-auth__footnote">
          New here? <a href="#signup" onClick={(e) => { e.preventDefault(); onSignUp(); }}>Register your organisation</a>
        </p>
      </form>
    </AuthLayout>
  );
}
