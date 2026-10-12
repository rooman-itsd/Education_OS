// Admin sign-in, on the same identity API and token as the main app (src/auth, src/api).
// With the API reachable, only a super admin or an organisation admin gets past the login page.
// Without it, or with `?preview=1` (as in the main app), the login page is a demo: any credentials
// open the dashboard for this browser tab.

import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { ApiError, apiReachable, getToken } from "../../api/client";
import { loadSession, login, logout, type Session } from "../../auth/session";

const PREVIEW_KEY = "eos.admin.preview";

export type AuthStatus = "loading" | "signed-out" | "signed-in";

interface AuthState {
  status: AuthStatus;
  /** No API: demo sign-in. */
  preview: boolean;
  session: Session | null;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

export const isAdmin = (s: Session) => s.me.is_super_admin || s.me.roles.includes("org-admin");

/** A message for the login page, in the main app's wording where it has one. */
export function signInError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.message.includes("pending_approval"))
      return "Your organisation's academic package is waiting for platform approval. Try again once you receive the approval email.";
    if (err.status === 401) return "Incorrect email or password.";
    if (err.status === 422) return "Enter your institutional email address.";
    return err.message;
  }
  if (err instanceof Error) return err.message;
  return String(err);
}

function previewSignedIn(): boolean {
  try {
    return sessionStorage.getItem(PREVIEW_KEY) === "1";
  } catch {
    return false;
  }
}
function setPreviewSignedIn(on: boolean) {
  try {
    if (on) sessionStorage.setItem(PREVIEW_KEY, "1");
    else sessionStorage.removeItem(PREVIEW_KEY);
  } catch {
    /* storage unavailable: preview sign-in lasts until reload */
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [preview, setPreview] = useState(false);
  const [session, setSession] = useState<Session | null>(null);

  useEffect(() => {
    let live = true;
    (async () => {
      const forced = new URLSearchParams(window.location.search).get("preview") === "1";
      if (forced || !(await apiReachable())) {
        if (!live) return;
        setPreview(true);
        setStatus(previewSignedIn() ? "signed-in" : "signed-out");
        return;
      }
      if (!getToken()) {
        if (live) setStatus("signed-out");
        return;
      }
      try {
        const s = await loadSession();
        if (!live) return;
        if (isAdmin(s)) {
          setSession(s);
          setStatus("signed-in");
        } else {
          logout();
          setStatus("signed-out");
        }
      } catch {
        logout();
        if (live) setStatus("signed-out");
      }
    })();
    return () => {
      live = false;
    };
  }, []);

  const signIn = useCallback(
    async (email: string, password: string) => {
      if (preview) {
        setPreviewSignedIn(true);
        setStatus("signed-in");
        return;
      }
      await login(email, password);
      const s = await loadSession();
      if (!isAdmin(s)) {
        logout();
        throw new Error("This account is not an administrator. Sign in with a super admin or organisation admin account.");
      }
      setSession(s);
      setStatus("signed-in");
    },
    [preview],
  );

  const signOut = useCallback(() => {
    logout();
    setPreviewSignedIn(false);
    setSession(null);
    setStatus("signed-out");
  }, []);

  return <AuthContext.Provider value={{ status, preview, session, signIn, signOut }}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const auth = useContext(AuthContext);
  if (!auth) throw new Error("useAuth() must be used inside <AuthProvider>");
  return auth;
}
