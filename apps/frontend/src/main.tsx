import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@eos/ui-kit/styles.css";
import { App } from "./App";
import { PublicSite } from "../../../modules/student-lifecycle/web-portal-cms/frontend/src/index";

// One bundle, two surfaces, chosen by path (both keep their own hash routing):
//  - /app (and /app/…): the role-dashboard app — login, sign-up (#signup), dashboards (#/…) — unchanged.
//  - everything else, including /: the public marketing site (#/, #/features, #/signup).
// The admin console is its own page (admin.html) and is not affected. Old /public links are rewritten
// in place to / (no reload), so they keep working without a second entry point.
const path = window.location.pathname.replace(/\/+$/, "");
if (path === "/public") {
  window.history.replaceState(null, "", `/${window.location.search}${window.location.hash}`);
}
const isApp = path === "/app" || path.startsWith("/app/");

createRoot(document.getElementById("root")!).render(
  <StrictMode>{isApp ? <App /> : <PublicSite />}</StrictMode>,
);
