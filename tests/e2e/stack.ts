/**
 * The stack the e2e suite runs against: its own API and web dev server on their own ports, so it never
 * touches a dev server you have running, with a fresh SQLite database every run.
 */
export const API_PORT = Number(process.env.E2E_API_PORT ?? 8100);
export const WEB_PORT = Number(process.env.E2E_WEB_PORT ?? 5180);

/** Seeded at API start-up from these env vars. Test-only credentials; never used outside this suite. */
export const SUPER_ADMIN = {
  email: "root@e2e.example.com",
  password: "E2eRootPassw0rd!",
};
