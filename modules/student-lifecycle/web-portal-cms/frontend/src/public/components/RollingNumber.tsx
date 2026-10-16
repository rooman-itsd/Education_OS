import { useEffect, useRef, useState, type CSSProperties } from "react";
import { prefersReducedMotion } from "@eos/ui-kit";

/** Extra full turns each digit makes before it lands; digits further right spin more. */
const MAX_LAPS = 3;

/**
 * A number whose digits roll into place like an odometer: each digit is a column of 0–9 that spins
 * quickly through a few turns and settles on its value, the right-hand digits spinning longest.
 * It starts once the number is on screen, after `delay` ms (so it plays as its card finishes
 * arriving). Non-digits (separators, currency) stay still. Screen readers get the plain text; the
 * columns are hidden from them. Reduced motion, or no IntersectionObserver: the plain number.
 */
export function RollingNumber({ text, delay = 0 }: { text: string; delay?: number }) {
  const ref = useRef<HTMLSpanElement>(null);
  const [still] = useState(() => prefersReducedMotion() || typeof IntersectionObserver === "undefined");
  const [go, setGo] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (still || !el) return;
    let timer = 0;
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          io.disconnect();
          // Two frames so the columns paint at 0 before they start moving.
          timer = window.setTimeout(() => requestAnimationFrame(() => setGo(true)), delay);
        }
      },
      { threshold: 0.4 },
    );
    io.observe(el);
    return () => {
      io.disconnect();
      window.clearTimeout(timer);
    };
  }, [still, delay]);

  if (still) return <>{text}</>;

  const digits = [...text].filter((c) => /\d/.test(c)).length;
  let seen = 0;
  return (
    <span ref={ref} className={go ? "wpc-odo is-go" : "wpc-odo"}>
      <span className="eos-sr-only">{text}</span>
      <span className="wpc-odo__cols" aria-hidden>
        {[...text].map((ch, i) => {
          if (!/\d/.test(ch)) {
            return (
              <span key={i} className="wpc-odo__sep">
                {ch}
              </span>
            );
          }
          const pos = seen++; // 0 = leftmost digit
          const laps = 1 + Math.round(((MAX_LAPS - 1) * pos) / Math.max(1, digits - 1));
          const style = {
            "--odo-to": laps * 10 + Number(ch),
            "--odo-dur": `${1100 + pos * 140}ms`,
          } as CSSProperties;
          return (
            <span key={i} className="wpc-odo__col">
              <span className="wpc-odo__strip" style={style}>
                {Array.from({ length: (MAX_LAPS + 1) * 10 }, (_, n) => (
                  <span key={n}>{n % 10}</span>
                ))}
              </span>
            </span>
          );
        })}
      </span>
    </span>
  );
}
