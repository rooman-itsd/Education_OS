/** A small line of values over time, drawn as plain SVG. Decorative: the widget states the values in text. */
export function Sparkline({ values, target }: { values: number[]; target?: number }) {
  if (values.length < 2) return null;
  const all = target === undefined ? values : [...values, target];
  const min = Math.min(...all);
  const max = Math.max(...all);
  const span = max - min || 1;
  const W = 120;
  const H = 32;
  const x = (i: number) => (i / (values.length - 1)) * W;
  const y = (v: number) => H - 2 - ((v - min) / span) * (H - 4);
  const line = values.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  return (
    <svg className="eos-ap__spark" viewBox={`0 0 ${W} ${H}`} width={W} height={H} aria-hidden focusable="false">
      {target !== undefined && <line className="eos-ap__spark-target" x1={0} x2={W} y1={y(target)} y2={y(target)} />}
      <polyline className="eos-ap__spark-line" points={line} fill="none" />
      <circle className="eos-ap__spark-dot" cx={x(values.length - 1)} cy={y(values[values.length - 1]!)} r={2.5} />
    </svg>
  );
}
