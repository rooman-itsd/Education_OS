/** Lets TypeScript accept `import "./public.css"` and `import "@eos/ui-kit/styles.css"`.
 *  The bundler (Vite, in apps/frontend) turns these into real stylesheet links at build time. */
declare module "*.css";
