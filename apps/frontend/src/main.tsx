import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@eos/ui-kit/styles.css";
import { App } from "./App";
import { PublicSite } from "../../../modules/student-lifecycle/web-portal-cms/frontend/src/index";

// The public marketing site is served at /public and keeps its own hash routing
// (#/, #/features, #/signup). Everything else — /, login, dashboards, auth — is
// handled by <App/> and is left completely unchanged.
const isPublicSite = window.location.pathname.replace(/\/+$/, "") === "/public";

createRoot(document.getElementById("root")!).render(
  <StrictMode>{isPublicSite ? <PublicSite /> : <App />}</StrictMode>,
);
