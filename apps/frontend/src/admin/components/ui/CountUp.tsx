import React from 'react';
import { easeOut, useElapsed } from '../../lib/motion';

export interface CountUpProps {
  end: number;
  decimals?: number;
  prefix?: string;
  suffix?: string;
  duration?: number;
  /** Start counting; defaults to at once. */
  active?: boolean;
  delay?: number;
}

/** Counts from 0 to `end` with an ease-out curve; ends on exactly `end`. Reduced motion shows `end` at once. */
export const CountUp: React.FC<CountUpProps> = ({ end, decimals = 0, prefix = '', suffix = '', duration = 1000, active = true, delay = 0 }) => {
  const t = useElapsed(active, duration + delay);
  const k = Math.max(0, Math.min(1, (t - delay) / duration));
  const value = k >= 1 ? end : end * easeOut(k);
  return (
    <>
      {prefix}
      {value.toLocaleString('en-IN', { minimumFractionDigits: decimals, maximumFractionDigits: decimals })}
      {suffix}
    </>
  );
};
