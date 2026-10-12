// Micro-visualizations for KPI cards: a sparkline, a ring and a thin progress line.
// Label-free and quiet; each fits the same 96×30 slot so the six cards stay uniform.
// They loop slowly (CSS/SVG only) so the data feels live; the resting style is the
// final static state, which is what users with reduced motion see.

import React from 'react';

type Motion = { color: string; /** Start offset so the cards don't move in unison. */ delay?: number };

/** Sparkline that draws left to right, its endpoint travelling with the line, then fades and repeats. */
export const MiniSparkline: React.FC<Motion & { values: number[] }> = ({ values, color, delay = 0 }) => {
  const W = 96;
  const H = 30;
  const min = Math.min(...values);
  const span = Math.max(...values) - min || 1;
  const pts = values.map((v, i) => [(i / (values.length - 1)) * W, H - 3 - ((v - min) / span) * (H - 8)] as const);
  const line = pts.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)} ${y.toFixed(1)}`).join(' ');
  const timing = { animationDelay: `${delay}ms` };
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} className="overflow-visible" aria-hidden>
      <path d={`${line} L${W} ${H} L0 ${H} Z`} fill={color} fillOpacity={0.06} className="eos-kpi-area" style={timing} />
      <path
        d={line}
        fill="none"
        stroke={color}
        strokeOpacity={0.85}
        strokeWidth={1.6}
        strokeLinecap="round"
        strokeLinejoin="round"
        pathLength={1}
        className="eos-kpi-line"
        style={timing}
      />
      <circle r={2.2} fill={color} className="eos-kpi-dot" style={{ ...timing, offsetPath: `path("${line}")` }} />
    </svg>
  );
};

/** Ring that fills to its value, holds, eases back and repeats (never spins). */
export const MiniRing: React.FC<Motion & { pct: number }> = ({ pct, color, delay = 0 }) => {
  const r = 12;
  const c = 2 * Math.PI * r;
  return (
    <svg viewBox="0 0 30 30" className="w-[30px] h-[30px] -rotate-90" aria-hidden>
      <circle cx="15" cy="15" r={r} fill="none" stroke="#EEF1F5" strokeWidth="3" />
      <circle
        cx="15"
        cy="15"
        r={r}
        fill="none"
        stroke={color}
        strokeWidth="3"
        strokeLinecap="round"
        strokeDasharray={c}
        className="eos-kpi-ring"
        style={{ '--ring-c': `${c}`, '--ring-to': `${c * (1 - pct / 100)}`, animationDelay: `${delay}ms` } as React.CSSProperties}
      />
    </svg>
  );
};

/** Very thin progress line that fills to its value, holds, eases back and repeats. */
export const MiniLine: React.FC<Motion & { pct: number }> = ({ pct, color, delay = 0 }) => (
  <div className="w-24 h-[3px] rounded-full bg-[#EEF1F5] overflow-hidden" aria-hidden>
    <div
      className="h-full rounded-full origin-left eos-kpi-bar"
      style={{ width: `${Math.min(100, pct)}%`, backgroundColor: color, animationDelay: `${delay}ms` }}
    />
  </div>
);

/** Small colourful histogram; bars grow up from the baseline left to right, hold, settle and repeat. */
export const MiniHistogram: React.FC<{ values: number[]; colors: string[]; delay?: number }> = ({ values, colors, delay = 0 }) => {
  const max = Math.max(...values);
  const min = Math.min(...values);
  return (
    <div className="flex items-end gap-[3px] w-24 h-[30px]" aria-hidden>
      {values.map((v, i) => (
        <span
          key={i}
          className="flex-1 rounded-t-[2px] origin-bottom eos-kpi-col"
          style={{
            // keep the shortest bar visible: map values onto 30%–100% of the slot
            height: `${30 + ((v - min) / (max - min || 1)) * 70}%`,
            backgroundColor: colors[i % colors.length],
            animationDelay: `${delay + i * 90}ms`
          }}
        />
      ))}
    </div>
  );
};

/** Small colourful pie; each slice sweeps in after the previous one, holds, eases back and repeats. */
export const MiniPie: React.FC<{ slices: { value: number; color: string }[]; delay?: number }> = ({ slices, delay = 0 }) => {
  const r = 8; // stroke width 2r fills the circle, turning the ring into a pie
  const c = 2 * Math.PI * r;
  const total = slices.reduce((n, sl) => n + sl.value, 0) || 1;
  let start = 0;
  return (
    <svg viewBox="0 0 32 32" className="w-8 h-8 -rotate-90" aria-hidden>
      {slices.map((sl, i) => {
        const len = (sl.value / total) * c;
        const offset = -start;
        start += len;
        return (
          <circle
            key={i}
            cx="16"
            cy="16"
            r={r}
            fill="none"
            stroke={sl.color}
            strokeWidth={2 * r}
            strokeDashoffset={offset}
            className="eos-kpi-seg"
            style={{ '--seg': `${len}`, '--seg-c': `${c}`, animationDelay: `${delay + i * 140}ms` } as React.CSSProperties}
          />
        );
      })}
      <circle cx="16" cy="16" r="15.5" fill="none" stroke="#FFFFFF" strokeOpacity="0.9" strokeWidth="1" />
    </svg>
  );
};

/** Stacked columns (e.g. monthly fees split by head); columns grow up in turn, hold, settle and repeat. */
export const MiniStackedBars: React.FC<{ stacks: number[][]; colors: string[]; delay?: number }> = ({ stacks, colors, delay = 0 }) => {
  const max = Math.max(...stacks.map((st) => st.reduce((a, b) => a + b, 0))) || 1;
  return (
    <div className="flex items-end gap-[3px] w-24 h-[30px]" aria-hidden>
      {stacks.map((st, i) => {
        const total = st.reduce((a, b) => a + b, 0);
        return (
          <span
            key={i}
            className="flex-1 flex flex-col-reverse overflow-hidden rounded-t-[2px] origin-bottom eos-kpi-col"
            style={{ height: `${(total / max) * 100}%`, animationDelay: `${delay + i * 90}ms` }}
          >
            {st.map((v, j) => (
              <span key={j} style={{ height: `${(v / total) * 100}%`, backgroundColor: colors[j % colors.length] }} />
            ))}
          </span>
        );
      })}
    </div>
  );
};

/** Small colourful donut; segments sweep in one after another over a grey track, hold, ease back and repeat. */
export const MiniDonut: React.FC<{ slices: { value: number; color: string }[]; /** Total the slices are measured against (e.g. 100 for %). */ of?: number; delay?: number }> = ({
  slices,
  of,
  delay = 0
}) => {
  const r = 12;
  const c = 2 * Math.PI * r;
  const total = of ?? (slices.reduce((n, sl) => n + sl.value, 0) || 1);
  let start = 0;
  return (
    <svg viewBox="0 0 32 32" className="w-8 h-8 -rotate-90" aria-hidden>
      <circle cx="16" cy="16" r={r} fill="none" stroke="#E3E7EE" strokeWidth="5" />
      {slices.map((sl, i) => {
        const len = (sl.value / total) * c;
        const offset = -start;
        start += len;
        return (
          <circle
            key={i}
            cx="16"
            cy="16"
            r={r}
            fill="none"
            stroke={sl.color}
            strokeWidth="5"
            strokeDashoffset={offset}
            className="eos-kpi-seg"
            style={{ '--seg': `${Math.max(0, len - 0.6)}`, '--seg-c': `${c}`, animationDelay: `${delay + i * 140}ms` } as React.CSSProperties}
          />
        );
      })}
    </svg>
  );
};

/** Small horizontal bar chart (e.g. items per queue); bars grow from the left in turn, hold, ease back and repeat. */
export const MiniHBars: React.FC<{ bars: { value: number; color: string }[]; delay?: number }> = ({ bars, delay = 0 }) => {
  const max = Math.max(...bars.map((b) => b.value)) || 1;
  return (
    <div className="flex flex-col justify-end gap-[2.5px] w-24 h-[30px]" aria-hidden>
      {bars.map((b, i) => (
        <span
          key={i}
          className="block h-1 rounded-full origin-left eos-kpi-bar"
          style={{ width: `${(b.value / max) * 100}%`, backgroundColor: b.color, animationDelay: `${delay + i * 120}ms` }}
        />
      ))}
    </div>
  );
};

/** Semicircle gauge with coloured zones; the needle sweeps up to the value, holds, returns and repeats. */
export const MiniGauge: React.FC<{
  /** Value as a fraction of the scale, 0–1. */
  value: number;
  /** Zone end points as fractions (ascending, last = 1) with their colours. */
  zones: { to: number; color: string }[];
  delay?: number;
}> = ({ value, zones, delay = 0 }) => {
  const arc = 'M6 26 A18 18 0 0 1 42 26';
  let from = 0;
  return (
    <svg viewBox="0 0 48 30" className="w-12 h-[30px] overflow-visible" aria-hidden>
      {zones.map((z, i) => {
        const len = z.to - from - (i < zones.length - 1 ? 0.025 : 0); // tiny gap between zones
        const seg = (
          <path
            key={i}
            d={arc}
            fill="none"
            stroke={z.color}
            strokeWidth="5"
            pathLength={1}
            strokeDasharray={`${len} 1`}
            strokeDashoffset={-from}
          />
        );
        from = z.to;
        return seg;
      })}
      <g className="eos-kpi-needle" style={{ '--needle': `${-90 + value * 180}deg`, animationDelay: `${delay}ms` } as React.CSSProperties}>
        <line x1="24" y1="26" x2="24" y2="12" stroke="#12233F" strokeWidth="1.8" strokeLinecap="round" />
      </g>
      <circle cx="24" cy="26" r="2.6" fill="#12233F" />
    </svg>
  );
};
