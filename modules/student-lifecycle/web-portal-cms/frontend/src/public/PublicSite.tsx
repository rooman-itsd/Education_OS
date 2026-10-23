import { useEffect, useState } from "react";
import { ThemeScope } from "@eos/ui-kit";
import "@eos/ui-kit/styles.css";
import "./public.css";
import { PUBLIC_THEME, type PublicRoute } from "./content";
import { SiteHeader } from "./components/SiteHeader";
import { SiteFooter } from "./components/SiteFooter";
import { HomePage } from "./pages/HomePage";
import { FeaturesPage } from "./pages/FeaturesPage";
import { SignUpPage } from "./pages/SignUpPage";

/**
 * Root of the Education OS public website.
 *
 * Self-contained: it owns its own lightweight hash routing (`#/`, `#/features`, `#/signup`), the
 * brand theme, and the shared header/footer, so apps/frontend only has to mount <PublicSite /> at a
 * public entry (see the module README / handoff note). It composes the public platform APIs through
 * src/api/public-client.ts and never duplicates tenancy/billing/identity logic.
 */

function parseRoute(hash: string): PublicRoute {
  const path = hash.replace(/^#\/?/, "");
  if (path.startsWith("features")) return "features";
  if (path.startsWith("signup")) return "signup";
  return "home";
}

function hrefFor(route: PublicRoute): string {
  return route === "home" ? "#/" : `#/${route}`;
}

export function PublicSite() {
  const [route, setRoute] = useState<PublicRoute>(() =>
    parseRoute(typeof window === "undefined" ? "" : window.location.hash),
  );

  useEffect(() => {
    const onHashChange = () => setRoute(parseRoute(window.location.hash));
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  const navigate = (next: PublicRoute) => {
    const href = hrefFor(next);
    if (window.location.hash === href) setRoute(next);
    else window.location.hash = href; // the hashchange listener updates the route
    window.scrollTo({ top: 0 });
  };

  return (
    <ThemeScope theme={PUBLIC_THEME} className="wpc">
      <a className="eos-sr-only" href="#wpc-main">
        Skip to content
      </a>
      <SiteHeader route={route} onNavigate={navigate} />
      <main id="wpc-main" className="wpc-main" key={route}>
        {route === "home" && <HomePage onNavigate={navigate} />}
        {route === "features" && <FeaturesPage onNavigate={navigate} />}
        {route === "signup" && <SignUpPage onNavigate={navigate} />}
      </main>
      <SiteFooter onNavigate={navigate} />
    </ThemeScope>
  );
}
