import { useEffect, useRef, useState, type RefObject } from "react";
import { prefersReducedMotion } from "@eos/ui-kit";

/** Radii in the SVG's own units (viewBox is 920 wide, centred on 0,0). */
const R_TICK_IN = 334;
const R_TICK_OUT = 352;
const R_ARC = 368;
const R_MINUTE = 392;
const R_LABEL = 440;

/**
 * Pricing-page hero background: the free trial drawn as a dial around the photo. One tick per trial
 * day (the count comes from billing's trial plan) and an orange arc for the trial, which draws itself
 * on arrival; an outer ring of fine marks turns slowly, like a billing cycle. Pointing anywhere in the
 * section scrubs the arc to the day at that angle and labels it ("Day 12 · 18 days left"); on touch
 * screens the arc fills and empties slowly instead. `demo` lets the journey beside it drive the dial:
 * "count" runs through the trial day by day, "end" shows its last day (the pointer still wins). Decorative: hidden from assistive technology, the
 * trial length is stated in the text beside it.
 */
export function TrialDial({
  days,
  hostRef,
  demo = null,
}: {
  days: number;
  hostRef: RefObject<HTMLElement>;
  demo?: "count" | "end" | null;
}) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [pointerDay, setDay] = useState<number | null>(null);
  const [demoDay, setDemoDay] = useState<number | null>(null);

  useEffect(() => {
    if (!demo) {
      setDemoDay(null);
      return;
    }
    if (demo === "end" || prefersReducedMotion()) {
      setDemoDay(days);
      return;
    }
    let raf = 0;
    const start = performance.now();
    const step = (now: number) => {
      const p = Math.min(1, (now - start) / 2800);
      setDemoDay(Math.max(1, Math.ceil(p * days)));
      if (p < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [demo, days]);

  const day = pointerDay ?? demoDay;

  useEffect(() => {
    const host = hostRef.current;
    const svg = svgRef.current;
    if (!host || !svg) return;
    let frame = 0;
    let last: PointerEvent | null = null;
    const update = () => {
      frame = 0;
      if (!last) return;
      const box = svg.getBoundingClientRect();
      const dx = last.clientX - (box.left + box.width / 2);
      const dy = last.clientY - (box.top + box.height / 2);
      // 0 at twelve o'clock, growing clockwise.
      const turn = (Math.atan2(dy, dx) + Math.PI / 2 + 2 * Math.PI) % (2 * Math.PI);
      setDay(Math.min(days, Math.max(1, Math.ceil((turn / (2 * Math.PI)) * days))));
    };
    const onMove = (e: PointerEvent) => {
      if (e.pointerType !== "mouse") return;
      last = e;
      if (!frame) frame = requestAnimationFrame(update);
    };
    const onLeave = () => {
      last = null;
      setDay(null);
    };
    host.addEventListener("pointermove", onMove);
    host.addEventListener("pointerleave", onLeave);
    return () => {
      host.removeEventListener("pointermove", onMove);
      host.removeEventListener("pointerleave", onLeave);
      if (frame) cancelAnimationFrame(frame);
    };
  }, [days, hostRef]);

  const shown = day ?? days;
  const at = (i: number, r: number) => {
    const a = ((i - 0.5) / days) * 2 * Math.PI - Math.PI / 2;
    return { x: Math.cos(a) * r, y: Math.sin(a) * r };
  };
  const label = day ? at(day, R_LABEL) : null;
  const left = day ? days - day : 0;

  return (
    <svg
      ref={svgRef}
      className={day ? "wpc-dial is-scrubbing" : "wpc-dial"}
      viewBox="-460 -460 920 920"
      aria-hidden
      focusable="false"
    >
      <circle className="wpc-dial__glow" r={400} />
      <circle className="wpc-dial__face" r={R_TICK_IN - 14} />
      <g className="wpc-dial__minutes">
        {Array.from({ length: 120 }, (_, i) => {
          const a = (i / 120) * 2 * Math.PI;
          const long = i % 10 === 0;
          const r1 = long ? R_MINUTE - 8 : R_MINUTE - 3;
          return (
            <line
              key={i}
              x1={Math.cos(a) * r1}
              y1={Math.sin(a) * r1}
              x2={Math.cos(a) * (R_MINUTE + 3)}
              y2={Math.sin(a) * (R_MINUTE + 3)}
            />
          );
        })}
      </g>
      {Array.from({ length: days }, (_, k) => {
        const i = k + 1;
        const a = at(i, R_TICK_IN);
        const b = at(i, R_TICK_OUT);
        const cls = i === day ? "wpc-dial__tick is-now" : i <= shown ? "wpc-dial__tick is-used" : "wpc-dial__tick";
        return <line key={i} className={cls} x1={a.x} y1={a.y} x2={b.x} y2={b.y} />;
      })}
      <circle className="wpc-dial__track" r={R_ARC} />
      <circle
        className="wpc-dial__arc"
        r={R_ARC}
        pathLength={100}
        style={day ? { strokeDashoffset: 100 * (1 - day / days) } : undefined}
      />
      {label && (
        <g className="wpc-dial__label" transform={`translate(${label.x} ${label.y})`}>
          <rect x={-150} y={-28} width={300} height={56} rx={28} />
          <text textAnchor="middle" dy="0.35em">
            Day {day} · {left === 0 ? "last day" : `${left} ${left === 1 ? "day" : "days"} left`}
          </text>
        </g>
      )}
    </svg>
  );
}
