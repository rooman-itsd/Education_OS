/** Public frontend surface of admissions. apps/frontend mounts routes and registers widgets. */
export const routes = [] as const;
export { widgets } from "./widgets";

/** The applicant's public Track page; the host mounts it on the public site under an organisation's slug. */
export { TrackApplicationPage } from "./pages/TrackApplicationPage";
