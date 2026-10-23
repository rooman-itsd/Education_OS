import { EduMark } from "@eos/ui-kit";

/**
 * Branded loading indicator: the Education OS mark with a soft ping ring.
 *
 * Motion is the kit's `eos-ping` animation, which the global `prefers-reduced-motion` rule in
 * packages/ui-kit base.css switches off — so it is accessible by default. `role="status"` +
 * `aria-live="polite"` announce the state; the visible label is the accessible name.
 *
 * Render it only during genuine loading (e.g. while fetching academy types or plans). No artificial
 * delay is ever added.
 */
export function BrandedLoader({ label = "Loading…", screen = false }: { label?: string; screen?: boolean }) {
  return (
    <div className={screen ? "wpc-loader wpc-loader--screen" : "wpc-loader"} role="status" aria-live="polite">
      <span className="wpc-loader__mark">
        <span className="wpc-loader__ping eos-ping" aria-hidden />
        <EduMark size={44} />
      </span>
      <span className="wpc-loader__label">{label}</span>
    </div>
  );
}
