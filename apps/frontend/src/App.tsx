import { useEffect, useMemo, useState } from "react";
import { rolesForProfile } from "@eos/contracts";
import { AppShell, Icons, Notice, PageHero, Segmented, type Crumb } from "@eos/ui-kit";
import { apiReachable, getToken } from "./api/client";
import { Login } from "./auth/Login";
import { SignUp } from "./auth/SignUp";
import { loadSession, logout, upgrade, type Session } from "./auth/session";
import { Dashboard } from "./dashboard/Dashboard";
import { loadLayouts } from "./dashboard/layouts";
import { registry, registerEnabledModules } from "./modules";
import { buildSearch, buildSections, moduleLabel, SUITES } from "./shell/navigation";
import { ModulePage } from "./shell/ModulePage";
import { computeEntitlement, loadPlans, loadProfiles } from "./tenant";

const layouts = loadLayouts();
const profiles = loadProfiles();
const plans = loadPlans();

type Mode = "loading" | "preview" | "login" | "signup" | "app";

function fromUrl(key: string, fallback: string, valid: (v: string) => boolean): string {
  const value = new URLSearchParams(window.location.search).get(key) ?? fallback;
  return valid(value) ? value : fallback;
}

function setUrl(key: string, value: string) {
  const url = new URL(window.location.href);
  url.searchParams.set(key, value);
  window.history.replaceState(null, "", url);
}

/** The route lives in the hash: `#/` is the dashboard, `#/modules/<domain>/<id>` a module page. */
function useHashRoute(): string {
  const read = () => window.location.hash.replace(/^#/, "") || "/";
  const [route, setRoute] = useState(read);
  useEffect(() => {
    const onChange = () => setRoute(read());
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return route;
}

const greeting = () => {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
};

/**
 * With the API reachable: real sign-up, sign-in, organisation and entitlement (ADR-0005).
 * Without it, or with `?preview=1`: preview mode, where academy, role and plan come from the URL and
 * the entitlement rule runs locally. The rule is the same in both cases.
 */
export function App() {
  const [mode, setMode] = useState<Mode>("loading");
  const [session, setSession] = useState<Session | null>(null);
  const [ready, setReady] = useState(false);
  const [loginSlug, setLoginSlug] = useState<string | undefined>();
  const [noticeOpen, setNoticeOpen] = useState(true);
  const route = useHashRoute();

  // preview-mode state
  const [academy, setAcademy] = useState(() => fromUrl("academy", "sports-college", (v) => v in profiles));
  const [planId, setPlanId] = useState(() => fromUrl("plan", "trial", (v) => v in plans));
  const [role, setRole] = useState(() => fromUrl("role", "student", () => true));

  useEffect(() => {
    registerEnabledModules().then(() => setReady(true));
    const preview = new URLSearchParams(window.location.search).get("preview") === "1";
    (async () => {
      if (preview || !(await apiReachable())) {
        setMode("preview");
        return;
      }
      if (!getToken()) {
        setMode(window.location.hash === "#signup" ? "signup" : "login");
        return;
      }
      try {
        setSession(await loadSession());
        setMode("app");
      } catch {
        logout();
        setMode("login");
      }
    })();
  }, []);

  const previewProfile = profiles[academy]!;
  const previewEntitlement = useMemo(() => computeEntitlement(previewProfile, plans[planId]!), [previewProfile, planId]);

  const profile = mode === "app" && session?.organisation ? profiles[session.organisation.academy_type] : previewProfile;
  const roles = useMemo(() => rolesForProfile(profile?.roles ?? []), [profile]);
  const entitlement = mode === "app" ? session?.entitlement ?? undefined : previewEntitlement;

  useEffect(() => {
    if (mode === "app" && session) {
      const own = session.me.is_super_admin ? "super-admin" : session.me.roles[0] ?? "student";
      setRole(own);
    } else if (!roles.some((r) => r.id === role)) {
      setRole("student");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, session, roles]);

  const changeRole = (next: string) => {
    setUrl("role", next);
    setRole(next);
  };
  const changePlan = async (next: string) => {
    if (mode === "app") {
      const r = await upgrade(next);
      if (r.activated) setSession(await loadSession());
      else if (r.payment_url) window.location.assign(r.payment_url);
      return;
    }
    setUrl("plan", next);
    setPlanId(next);
  };
  const changeAcademy = (next: string) => {
    setUrl("academy", next);
    setAcademy(next);
  };
  const signOut = () => {
    logout();
    setSession(null);
    setMode("login");
  };
  const navigate = (href: string) => {
    window.location.hash = href.replace(/^#/, "");
  };

  if (mode === "loading") return <main className="eos-shell__content" aria-busy="true">Loading…</main>;
  if (mode === "signup") return <SignUp onDone={(slug) => { setLoginSlug(slug); setMode("login"); }} onLogin={() => setMode("login")} />;
  if (mode === "login") return <Login slug={loginSlug} onDone={async () => { setSession(await loadSession()); setMode("app"); }} onSignUp={() => setMode("signup")} />;

  const canUpgrade = mode === "app" ? Boolean(session?.me.permissions.includes("billing:subscription:manage")) : role === "org-admin" || role === "management";
  const plan = entitlement ? plans[entitlement.plan] : undefined;
  const organisationName = mode === "app" ? session?.organisation?.name ?? "Education OS platform" : `Demo ${profile?.title.split(" / ")[0] ?? "organisation"}`;
  const organisationDetail = [profile?.title, plan ? `${plan.title} plan` : undefined].filter(Boolean).join(" · ");
  const roleTitle = roles.find((r) => r.id === role)?.title ?? role;
  const locked = entitlement?.upgradableModules.length ?? 0;
  const trialNote = session?.trialEndsAt ? `Trial ends ${new Date(session.trialEndsAt).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}` : plan?.trial_days ? `Trial · ${plan.trial_days} days` : null;

  const moduleMatch = route.match(/^\/modules\/([^/]+)\/([^/]+)/);
  const crumbs: Crumb[] = moduleMatch
    ? [{ label: "Education OS", href: "#/" }, { label: SUITES.find((s) => s.id === moduleMatch[1])?.label ?? moduleMatch[1]! }, { label: moduleLabel(moduleMatch[2]!) }]
    : [{ label: "Education OS", href: "#/" }, { label: "Dashboard" }];

  const notice =
    mode === "preview" && noticeOpen ? (
      <Notice onDismiss={() => setNoticeOpen(false)}>Preview mode: sample data, no API connected. Academy, role and plan come from the URL.</Notice>
    ) : trialNote && noticeOpen && mode === "app" ? (
      <Notice onDismiss={() => setNoticeOpen(false)}>
        {trialNote}
        {locked > 0 && canUpgrade ? (
          <>
            {" · "}
            <a href="#upgrade" onClick={(e) => { e.preventDefault(); changePlan("standard"); }}>
              {locked} module{locked === 1 ? "" : "s"} locked, upgrade
            </a>
          </>
        ) : null}
      </Notice>
    ) : null;

  const previewControls =
    mode === "preview" ? (
      <div className="eos-topbar__controls">
        <label className="eos-sr-only" htmlFor="eos-academy">Academy</label>
        <select id="eos-academy" className="eos-select" value={profile?.profile} onChange={(e) => changeAcademy(e.target.value)}>
          {Object.values(profiles).map((p) => (
            <option key={p.profile} value={p.profile}>{p.title}</option>
          ))}
        </select>
        <label className="eos-sr-only" htmlFor="eos-role">View as</label>
        <select id="eos-role" className="eos-select" value={role} onChange={(e) => changeRole(e.target.value)}>
          {roles.map((r) => (
            <option key={r.id} value={r.id}>{r.title}</option>
          ))}
        </select>
        <Segmented label="Plan" value={entitlement?.plan ?? planId} options={Object.values(plans).map((p) => [p.id, p.title] as [string, string])} onChange={(v) => void changePlan(v)} />
      </div>
    ) : undefined;

  return (
    <AppShell
      sidebar={{ sections: buildSections(profile, entitlement), currentHref: `#${route}`, homeHref: "#/" }}
      topbar={{
        crumbs,
        search: buildSearch(profile),
        onNavigate: navigate,
        accountSlot: previewControls,
        user: mode === "app" && session ? { name: session.me.name, role: roleTitle + (session.me.impersonated_by ? " · impersonated" : ""), email: session.me.email } : undefined,
        onSignOut: mode === "app" ? signOut : undefined,
      }}
      organisation={{ name: organisationName, detail: organisationDetail, connected: mode === "app" }}
      notice={notice}
      pageKey={route}
    >
      {moduleMatch ? (
        <ModulePage domain={moduleMatch[1]!} id={moduleMatch[2]!} entitlement={entitlement} canUpgrade={canUpgrade} onUpgrade={() => changePlan("standard")} />
      ) : (
        <div className="eos-dashboard">
          <PageHero
            eyebrow={profile?.title}
            title={`${greeting()}, ${mode === "app" && session ? session.me.name.split(" ")[0] : roleTitle}`}
            subtitle={`${organisationName} · ${roleTitle} dashboard`}
            actions={
              locked > 0 && canUpgrade ? (
                <button type="button" className="eos-btn eos-btn--primary" onClick={() => changePlan("standard")}>
                  <Icons.Lock /> Unlock {locked} module{locked === 1 ? "" : "s"}
                </button>
              ) : undefined
            }
          />
          {ready ? (
            <Dashboard role={role} layouts={layouts} registry={registry} permissions="all" entitlement={entitlement} canUpgrade={canUpgrade} hideTitle />
          ) : (
            <p className="eos-dashboard__missing" aria-busy="true">Loading modules…</p>
          )}
        </div>
      )}
    </AppShell>
  );
}
