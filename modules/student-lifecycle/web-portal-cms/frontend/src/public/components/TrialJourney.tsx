import { useEffect, useState, type CSSProperties } from "react";
import { prefersReducedMotion } from "@eos/ui-kit";

export interface JourneyStep {
  id: string;
  title: string;
  text: string;
  /** What the trial dial shows while this step is open: counting through the trial, or its last day. */
  dial?: "count" | "end";
}

/** How long each step stays open while the journey plays by itself. */
const STEP_MS = 5000;

/**
 * Pricing-page journey from registration to a paid plan: a numbered list where one step is open at a
 * time. Until the visitor touches it, it plays through the steps on its own (a bar fills along the open
 * step's rail); any hover, focus or click hands control to the visitor. Each step heading is a button
 * (aria-expanded), so it works by keyboard; closed steps are hidden from assistive technology. Steps
 * that concern the trial drive the dial beside it through `onDial`. Reduced motion: no autoplay.
 */
export function TrialJourney({
  steps,
  label,
  onDial,
}: {
  steps: JourneyStep[];
  label: string;
  onDial: (dial: JourneyStep["dial"] | null) => void;
}) {
  const [active, setActive] = useState(0);
  const [auto, setAuto] = useState(() => !prefersReducedMotion());

  useEffect(() => {
    if (!auto) return;
    const id = window.setInterval(() => setActive((a) => (a + 1) % steps.length), STEP_MS);
    return () => window.clearInterval(id);
  }, [auto, steps.length]);

  const dial = steps[active]?.dial ?? null;
  useEffect(() => {
    onDial(dial);
  }, [dial, onDial]);

  const takeOver = () => setAuto(false);

  return (
    <ol
      className={auto ? "wpc-tj is-auto" : "wpc-tj"}
      aria-label={label}
      onPointerEnter={takeOver}
      onFocus={takeOver}
      style={{ "--step-ms": `${STEP_MS}ms` } as CSSProperties}
    >
      {steps.map((step, i) => {
        const open = i === active;
        const state = open ? " is-active" : i < active ? " is-done" : "";
        return (
          <li key={step.id} className={`wpc-tj__step${state}`}>
            <button
              type="button"
              className="wpc-tj__head"
              aria-expanded={open}
              aria-controls={`wpc-tj-${step.id}`}
              onClick={() => {
                takeOver();
                setActive(i);
              }}
            >
              <span className="wpc-tj__num" aria-hidden>
                {i + 1}
              </span>
              <span className="wpc-tj__title">{step.title}</span>
            </button>
            <div id={`wpc-tj-${step.id}`} className="wpc-tj__body">
              <p>{step.text}</p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
