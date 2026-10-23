/** Public frontend surface of web-portal-cms. apps/frontend mounts routes and registers widgets. */
export const routes = [] as const;
export { widgets } from "./widgets";

/** The public marketing website + organisation sign-up (mounted by a public entry in apps/frontend). */
export { PublicSite } from "./public/PublicSite";
export type { PublicRoute } from "./public/content";
