// The subset of the Recharts 3 API the admin dashboard's histogram uses (bar and monotone area
// charts with a category x-axis, a numeric y-axis, a grid and a hover tooltip), drawn as plain SVG.
// Recharts is not on docs/architecture/approved-stack.yaml; this reproduces its layout rules
// (offsets, nice ticks, bar sizing, preserveEnd tick hiding, tooltip placement, animations) so the
// charts look the same as in the design.

import {
  Children,
  Fragment,
  cloneElement,
  isValidElement,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
  type MouseEvent,
  type ReactElement,
  type ReactNode,
} from "react";
import { easeOut, useElapsed, useInView } from "./motion";

type Row = Record<string, string | number>;
type Margin = { top: number; right: number; left: number; bottom: number };

interface AxisProps {
  dataKey?: string;
  stroke?: string;
  fontSize?: number;
  tickLine?: boolean;
  axisLine?: boolean | { stroke?: string };
  width?: number;
  height?: number;
  tickFormatter?: (v: number) => string;
}
interface GridProps {
  stroke?: string;
  vertical?: boolean;
}
interface TooltipProps {
  cursor?: { fill?: string; stroke?: string };
  formatter?: (value: unknown, name: unknown) => [string, string];
  labelFormatter?: (label: unknown) => ReactNode;
  contentStyle?: CSSProperties;
  itemStyle?: CSSProperties;
  labelStyle?: CSSProperties;
}
interface BarProps {
  dataKey: string;
  name?: string;
  fill?: string;
  radius?: [number, number, number, number];
  maxBarSize?: number;
  animationDuration?: number;
}
interface AreaProps {
  type?: "monotone";
  dataKey: string;
  name?: string;
  stroke?: string;
  strokeWidth?: number;
  fill?: string;
  activeDot?: { r?: number; strokeWidth?: number; stroke?: string };
  animationDuration?: number;
}
interface ChartProps {
  data: Row[];
  margin?: Partial<Margin>;
  barCategoryGap?: string | number;
  barGap?: number;
  width?: number;
  height?: number;
  children?: ReactNode;
  /** Set by ResponsiveContainer: the chart has scrolled into view, so its entrance animation may start. */
  active?: boolean;
}

// Configuration-only children, read by the chart like Recharts reads them.
export const XAxis = (_p: AxisProps): null => null;
export const YAxis = (_p: AxisProps): null => null;
export const CartesianGrid = (_p: GridProps): null => null;
export const Tooltip = (_p: TooltipProps): null => null;
export const Bar = (_p: BarProps): null => null;
export const Area = (_p: AreaProps): null => null;

/** Fills its parent and hands the measured size to its one chart child. */
export function ResponsiveContainer({ width = "100%", height = "100%", children }: { width?: string; height?: string; children: ReactElement<ChartProps> }) {
  const ref = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState<{ w: number; h: number } | null>(null);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const measure = () => setSize({ w: el.clientWidth, h: el.clientHeight });
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const inView = useInView(ref);
  return (
    <div ref={ref} className="recharts-responsive-container" style={{ width, height, minWidth: 0 }}>
      {/* Like Recharts: a zero-size box so the chart never stretches the layout it measures. */}
      <div style={{ width: 0, height: 0, overflow: "visible" }}>
        {size && size.w > 0 && size.h > 0 && cloneElement(children, { width: size.w, height: size.h, active: inView })}
      </div>
    </div>
  );
}

function flatten(children: ReactNode): ReactElement[] {
  const out: ReactElement[] = [];
  Children.forEach(children, (c) => {
    if (!isValidElement(c)) return;
    if (c.type === Fragment) out.push(...flatten((c.props as { children?: ReactNode }).children));
    else out.push(c);
  });
  return out;
}
function find<P>(items: ReactElement[], type: unknown): P | undefined {
  return items.find((c) => c.type === type)?.props as P | undefined;
}
function all<P>(items: ReactElement[], type: unknown): P[] {
  return items.filter((c) => c.type === type).map((c) => c.props as P);
}

// ---------- Recharts' nice ticks (recharts-scale getNiceTickValues, tickCount 5) ----------
const fix = (n: number) => Number(n.toPrecision(12));
function formatStep(rough: number, correction: number): number {
  if (rough <= 0) return 0;
  const digitCount = Math.floor(Math.log10(rough)) + 1;
  const digitValue = 10 ** digitCount;
  const ratio = rough / digitValue;
  const scale = digitCount !== 1 ? 0.05 : 0.1;
  return fix((Math.ceil(fix(ratio / scale)) + correction) * scale * digitValue);
}
function niceTicks(max: number, tickCount = 5, correction = 0): number[] {
  if (max <= 0) return [0, 1, 2, 3, 4].slice(0, tickCount);
  const step = formatStep(max / (tickCount - 1), correction);
  let up = Math.ceil(fix(max / step));
  const count = up + 1;
  if (count > tickCount) return niceTicks(max, tickCount, correction + 1);
  if (count < tickCount) up += tickCount - count;
  return Array.from({ length: up + 1 }, (_, i) => fix(i * step));
}

// ---------- Tick measurement and preserveEnd (recharts getTicks / getTicksEnd) ----------
// Recharts measures each tick label in a hidden span. It hands the span a numeric fontSize, which
// the DOM ignores, so labels are measured at the inherited font size; this does the same.
function textSize(text: string): { width: number; height: number } {
  let span = document.getElementById("recharts_measurement_span");
  if (!span) {
    span = document.createElement("span");
    span.id = "recharts_measurement_span";
    span.setAttribute("aria-hidden", "true");
    document.body.appendChild(span);
  }
  Object.assign(span.style, { position: "absolute", top: "-20000px", left: 0, padding: 0, margin: 0, border: "none", whiteSpace: "pre" });
  span.textContent = text;
  const r = span.getBoundingClientRect();
  return { width: r.width, height: r.height };
}
/**
 * Recharts' default `interval="preserveEnd"`: walk from the last tick back, nudging the last one
 * inside the chart and dropping any that would overlap. Bounds are the whole chart (Recharts 3
 * passes the chart box as the axis viewBox), `sign` the direction ticks advance in.
 */
function preserveEnd(coords: number[], sizes: number[], start: number, end: number): { i: number; at: number }[] {
  const sign = coords.length >= 2 ? Math.sign(coords[1]! - coords[0]!) || 1 : 1;
  const [lo, hi] = sign === 1 ? [start, end] : [end, start];
  let bound = hi;
  const shown: { i: number; at: number }[] = [];
  for (let i = coords.length - 1; i >= 0; i--) {
    const size = sizes[i]!;
    let at = coords[i]!;
    if (i === coords.length - 1) {
      const gap = sign * (at + (sign * size) / 2 - bound);
      if (gap > 0) at -= gap * sign;
    }
    const inside = !(sign * at < sign * lo || sign * at > sign * bound);
    if (inside && sign * (at - (sign * size) / 2 - lo) >= 0 && sign * (at + (sign * size) / 2 - bound) <= 0) {
      bound = at - sign * (size / 2 + 5);
      shown.push({ i, at });
    }
  }
  return shown.reverse();
}

const reducedMotion = () => typeof window !== "undefined" && Boolean(window.matchMedia?.("(prefers-reduced-motion: reduce)").matches);
const r3 = (n: number) => Math.round(n * 1000) / 1000;
const r4 = (n: number) => Math.round(n * 10000) / 10000;

// ---------- d3-shape curveMonotoneX (d3-path rounds to 3 digits, as in Recharts) ----------
function monotonePath(pts: { x: number; y: number }[]): string {
  const n = pts.length;
  if (n === 0) return "";
  if (n === 1) return `M${r3(pts[0]!.x)},${r3(pts[0]!.y)}`;
  if (n === 2) return `M${r3(pts[0]!.x)},${r3(pts[0]!.y)}L${r3(pts[1]!.x)},${r3(pts[1]!.y)}`;
  const sign = (v: number) => (v < 0 ? -1 : 1);
  const slope3 = (x0: number, y0: number, x1: number, y1: number, x2: number, y2: number) => {
    const h0 = x1 - x0;
    const h1 = x2 - x1;
    const s0 = (y1 - y0) / (h0 || (h1 < 0 ? -0 : 0));
    const s1 = (y2 - y1) / (h1 || (h0 < 0 ? -0 : 0));
    const p = (s0 * h1 + s1 * h0) / (h0 + h1);
    return (sign(s0) + sign(s1)) * Math.min(Math.abs(s0), Math.abs(s1), 0.5 * Math.abs(p)) || 0;
  };
  const slope2 = (x0: number, y0: number, x1: number, y1: number, t: number) => {
    const h = x1 - x0;
    return h ? ((3 * (y1 - y0)) / h - t) / 2 : t;
  };
  const t: number[] = new Array(n);
  for (let i = 1; i < n - 1; i++) t[i] = slope3(pts[i - 1]!.x, pts[i - 1]!.y, pts[i]!.x, pts[i]!.y, pts[i + 1]!.x, pts[i + 1]!.y);
  t[0] = slope2(pts[0]!.x, pts[0]!.y, pts[1]!.x, pts[1]!.y, t[1]!);
  t[n - 1] = slope2(pts[n - 2]!.x, pts[n - 2]!.y, pts[n - 1]!.x, pts[n - 1]!.y, t[n - 2]!);
  let d = `M${r3(pts[0]!.x)},${r3(pts[0]!.y)}`;
  for (let i = 0; i < n - 1; i++) {
    const a = pts[i]!;
    const b = pts[i + 1]!;
    const dx = (b.x - a.x) / 3;
    d += `C${r3(a.x + dx)},${r3(a.y + dx * t[i]!)},${r3(b.x - dx)},${r3(b.y - dx * t[i + 1]!)},${r3(b.x)},${r3(b.y)}`;
  }
  return d;
}

// ---------- Animation (Recharts default: 'ease' over animationDuration) ----------
function cubicBezier(x1: number, y1: number, x2: number, y2: number) {
  const cx = 3 * x1, bx = 3 * (x2 - x1) - cx, ax = 1 - cx - bx;
  const cy = 3 * y1, by = 3 * (y2 - y1) - cy, ay = 1 - cy - by;
  const sx = (t: number) => ((ax * t + bx) * t + cx) * t;
  const sy = (t: number) => ((ay * t + by) * t + cy) * t;
  const dsx = (t: number) => (3 * ax * t + 2 * bx) * t + cx;
  return (x: number) => {
    let t = x;
    for (let i = 0; i < 8; i++) {
      const err = sx(t) - x;
      const d = dsx(t);
      if (Math.abs(err) < 1e-6 || Math.abs(d) < 1e-6) break;
      t -= err / d;
    }
    return sy(Math.min(1, Math.max(0, t)));
  };
}
const ease = cubicBezier(0.25, 0.1, 0.25, 1);
function useProgress(duration: number, active = true): number {
  const reduced = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
  const [p, setP] = useState(reduced ? 1 : 0);
  useEffect(() => {
    if (reduced || !active) return;
    let raf = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const k = Math.min(1, (now - start) / duration);
      setP(ease(k));
      if (k < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [duration, reduced, active]);
  return p;
}

function topRoundedRect(x: number, y: number, w: number, h: number, r: number): string {
  if (h <= 0 || w <= 0) return "";
  const rr = Math.min(r, w / 2, h);
  [x, y, w, h] = [r4(x), r4(y), r4(w), r4(h)];
  return `M${x},${y + rr}A${rr},${rr},0,0,1,${x + rr},${y}L${x + w - rr},${y}A${rr},${rr},0,0,1,${x + w},${y + rr}L${x + w},${y + h}L${x},${y + h}Z`;
}

// ---------- Shared chart frame ----------
interface Frame {
  left: number;
  top: number;
  width: number;
  height: number;
}

function useChart(kind: "bar" | "area", props: ChartProps) {
  const { data, width = 0, height = 0 } = props;
  const margin: Margin = { top: 5, right: 5, left: 5, bottom: 5, ...props.margin };
  const items = flatten(props.children);
  const x = find<AxisProps>(items, XAxis) ?? {};
  const y = find<AxisProps>(items, YAxis) ?? {};
  const keys = (kind === "bar" ? all<BarProps>(items, Bar) : all<AreaProps>(items, Area)).map((s) => s.dataKey);
  const yWidth = y.width ?? 60;
  const xHeight = x.height ?? 30;
  const frame: Frame = {
    left: margin.left + yWidth,
    top: margin.top,
    width: Math.max(0, width - margin.left - margin.right - yWidth),
    height: Math.max(0, height - margin.top - margin.bottom - xHeight),
  };
  const max = Math.max(0, ...data.flatMap((r) => keys.map((k) => Number(r[k]) || 0)));
  const ticks = niceTicks(max);
  const top = ticks[ticks.length - 1] || 1;
  const yOf = (v: number) => frame.top + frame.height - (v / top) * frame.height;
  const n = data.length;
  const band = n ? frame.width / n : 0;
  const xOf = (i: number) => (kind === "bar" ? frame.left + band * i + band / 2 : frame.left + (n > 1 ? (frame.width * i) / (n - 1) : frame.width / 2));
  return { items, x, y, frame, ticks, yOf, xOf, band, n };
}

type Chart = ReturnType<typeof useChart>;

/** Horizontal grid lines at the y ticks (Recharts z-index layer -100). */
function Grid({ chart, draw = 1 }: { chart: Chart; draw?: number }) {
  const { frame, ticks, yOf, items } = chart;
  const grid = find<GridProps>(items, CartesianGrid);
  if (!grid) return null;
  return (
    <g className="recharts-cartesian-grid">
      <g className="recharts-cartesian-grid-horizontal">
        {ticks.map((t) => (
          <line key={t} stroke={grid.stroke ?? "#ccc"} fill="none" x1={frame.left} y1={yOf(t)} x2={frame.left + frame.width * draw} y2={yOf(t)} />
        ))}
      </g>
    </g>
  );
}

/** The x-axis line (layer 500, above areas and bars). */
function AxisLine({ chart }: { chart: Chart }) {
  const { x, frame } = chart;
  if (x.axisLine === false) return null;
  const stroke = (typeof x.axisLine === "object" ? x.axisLine.stroke : undefined) ?? x.stroke ?? "#666";
  const y = frame.top + frame.height;
  return (
    <g className="recharts-layer recharts-cartesian-axis recharts-xAxis xAxis">
      <line className="recharts-cartesian-axis-line" stroke={stroke} fill="none" x1={frame.left} y1={y} x2={frame.left + frame.width} y2={y} />
    </g>
  );
}

/** Tick labels of both axes (layer 2000, on top of everything). */
function TickLabels({ chart, labels, width, height }: { chart: Chart; labels: string[]; width: number; height: number }) {
  const { x, y, frame, ticks, yOf, xOf, n } = chart;
  const fmt = y.tickFormatter ?? ((v: number) => String(v));
  const yLabels = ticks.map((t) => fmt(t));
  const xShown = preserveEnd(
    Array.from({ length: n }, (_, i) => xOf(i)),
    labels.map((l) => textSize(l).width),
    0,
    width,
  );
  const yShown = preserveEnd(
    ticks.map((t) => yOf(t)),
    yLabels.map((l) => textSize(l).height),
    0,
    height,
  );
  const xTop = frame.top + frame.height + 8;
  return (
    <>
      <g className="recharts-layer recharts-cartesian-axis-tick-labels recharts-xAxis-tick-labels">
        {xShown.map(({ i, at }) => (
          <text key={i} className="recharts-text recharts-cartesian-axis-tick-value" x={at} y={xTop} textAnchor="middle" fontSize={x.fontSize} fill={x.stroke ?? "#666"} stroke="none">
            <tspan x={at} dy="0.71em">{labels[i]}</tspan>
          </text>
        ))}
      </g>
      <g className="recharts-layer recharts-cartesian-axis-tick-labels recharts-yAxis-tick-labels">
        {yShown.map(({ i, at }) => (
          <text key={i} className="recharts-text recharts-cartesian-axis-tick-value" x={frame.left - 8} y={at} textAnchor="end" fontSize={y.fontSize} fill={y.stroke ?? "#666"} stroke="none">
            <tspan x={frame.left - 8} dy="0.355em">{yLabels[i]}</tspan>
          </text>
        ))}
      </g>
    </>
  );
}

interface TipEntry {
  name: string;
  value: unknown;
}
function TooltipBox({ tip, frame, at, label, entries }: { tip: TooltipProps; frame: Frame; at: { x: number; y: number } | null; label: unknown; entries: TipEntry[] }) {
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null);
  useLayoutEffect(() => {
    if (!at || !ref.current) return;
    const { width: w, height: h } = ref.current.getBoundingClientRect();
    const place = (c: number, size: number, start: number, extent: number) => {
      const positive = c + 10;
      if (positive + size > start + extent) return Math.max(c - 10 - size, start);
      return Math.max(positive, start);
    };
    setPos({ x: place(at.x, w, frame.left, frame.width), y: place(at.y, h, frame.top, frame.height) });
  }, [at, frame.left, frame.top, frame.width, frame.height, label]);
  const fmt = tip.formatter ?? ((v: unknown, n: unknown) => [String(v), String(n)] as [string, string]);
  return (
    <div
      className="recharts-tooltip-wrapper"
      style={{
        visibility: at && pos ? "visible" : "hidden",
        pointerEvents: "none",
        position: "absolute",
        top: 0,
        left: 0,
        outline: "none",
        transform: pos ? `translate(${pos.x}px, ${pos.y}px)` : undefined,
        // Recharts animates the tooltip while it is shown, unless the viewer prefers reduced motion.
        transition: at && pos && !reducedMotion() ? "transform 400ms ease" : undefined,
      }}
    >
      <div ref={ref} className="recharts-default-tooltip" role="status" aria-live="assertive" style={{ margin: 0, padding: 10, backgroundColor: "#fff", border: "1px solid #ccc", whiteSpace: "nowrap", ...tip.contentStyle }}>
        <p className="recharts-tooltip-label" style={{ margin: 0, ...tip.labelStyle }}>
          {tip.labelFormatter ? tip.labelFormatter(label) : String(label)}
        </p>
        <ul className="recharts-tooltip-item-list" style={{ padding: 0, margin: 0 }}>
          {entries.map((e) => {
            const [value, name] = fmt(e.value, e.name);
            return (
              <li key={e.name} className="recharts-tooltip-item" style={{ display: "block", paddingTop: 4, paddingBottom: 4, ...tip.itemStyle }}>
                <span className="recharts-tooltip-item-name">{name}</span>
                <span className="recharts-tooltip-item-separator"> : </span>
                <span className="recharts-tooltip-item-value">{value}</span>
                <span className="recharts-tooltip-item-unit"></span>
              </li>
            );
          })}
        </ul>
      </div>
    </div>
  );
}

function useHover(chart: ReturnType<typeof useChart>, kind: "bar" | "area") {
  const [hover, setHover] = useState<{ i: number; y: number } | null>(null);
  const onMove = (e: MouseEvent<SVGSVGElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    const mx = e.clientX - r.left;
    const my = e.clientY - r.top;
    const { frame, n, band } = chart;
    if (!n || mx < frame.left || mx > frame.left + frame.width || my < frame.top || my > frame.top + frame.height) {
      setHover(null);
      return;
    }
    const i =
      kind === "bar"
        ? Math.min(n - 1, Math.floor((mx - frame.left) / band))
        : Math.round(((mx - frame.left) / (frame.width || 1)) * (n - 1));
    setHover({ i: Math.max(0, i), y: my });
  };
  return { hover, onMove, onLeave: () => setHover(null) };
}

function Wrapper({ width, height, children, svg }: { width: number; height: number; children?: ReactNode; svg: ReactElement }) {
  return (
    <div className="recharts-wrapper" style={{ position: "relative", cursor: "default", width, height }}>
      {children}
      {svg}
    </div>
  );
}

export function BarChart(props: ChartProps) {
  const chart = useChart("bar", props);
  const { items, frame, yOf, band, n, x } = chart;
  const bars = all<BarProps>(items, Bar);
  const tip = find<TooltipProps>(items, Tooltip);
  // Entrance: each year grows from 0 with an ease-out curve, a little after the one before it.
  // Gridlines draw in first (500ms), then each year grows over 1s, 140ms after the previous year;
  // a second series starts 110ms after the first within its year.
  const gridMs = 500;
  const growMs = 1000;
  const staggerMs = 140;
  const seriesMs = 110;
  const elapsed = useElapsed(props.active ?? true, gridMs + growMs + staggerMs * Math.max(0, chart.n - 1) + seriesMs * 2);
  const gridDraw = easeOut(Math.min(1, elapsed / gridMs));
  const grown = (i: number, si = 0) => easeOut(Math.max(0, Math.min(1, (elapsed - gridMs * 0.6 - i * staggerMs - si * seriesMs) / growMs)));
  const { hover, onMove, onLeave } = useHover(chart, "bar");
  const { data, width = 0, height = 0, barGap = 4 } = props;
  const labels = data.map((r) => String(r[x.dataKey ?? ""] ?? ""));

  // Recharts 3 combineAllBarPositions with a percentage barCategoryGap and maxBarSize.
  const gapPct = typeof props.barCategoryGap === "string" ? parseFloat(props.barCategoryGap) / 100 : (props.barCategoryGap ?? 0.1 * band) / (band || 1);
  const offset = band * gapPct;
  let gap = barGap;
  if (band - 2 * offset - (bars.length - 1) * gap <= 0) gap = 0;
  let original = (band - 2 * offset - (bars.length - 1) * gap) / Math.max(1, bars.length);
  if (original > 1) original = Math.round(original);
  const size = Math.min(original, bars[0]?.maxBarSize ?? Infinity);
  const base = frame.top + frame.height;

  const svg = (
    <svg className="recharts-surface" width={width} height={height} viewBox={`0 0 ${width} ${height}`} style={{ width: "100%", height: "100%", display: "block" }} onMouseMove={onMove} onMouseLeave={onLeave}>
      <Grid chart={chart} draw={gridDraw} />
      {tip && hover && (
        <rect className="recharts-tooltip-cursor" x={frame.left + band * hover.i} y={frame.top} width={band} height={frame.height} fill={tip.cursor?.fill ?? "#ccc"} stroke="none" pointerEvents="none" />
      )}
      {bars.map((b, bi) => (
        <g key={b.dataKey} className="recharts-layer recharts-bar">
          {data.map((row, i) => {
            const v = Number(row[b.dataKey]) || 0;
            const h = (base - yOf(v)) * grown(i, bi);
            const bx = frame.left + band * i + offset + (bars.length * (original - size)) / 2 + (size + gap) * bi;
            // On hover the other years soften slightly so the hovered one stands out.
            const dim = hover && hover.i !== i;
            return (
              <path
                key={i}
                className="recharts-rectangle"
                fill={b.fill}
                fillOpacity={dim ? 0.55 : 1}
                style={{ transition: "fill-opacity 160ms ease" }}
                d={topRoundedRect(bx, base - h, size, h, b.radius?.[0] ?? 0)}
              />
            );
          })}
        </g>
      ))}
      <AxisLine chart={chart} />
      <TickLabels chart={chart} labels={labels} width={width} height={height} />
    </svg>
  );
  return (
    <Wrapper width={width} height={height} svg={svg}>
      {tip && n > 0 && (
        <TooltipBox
          tip={tip}
          frame={frame}
          at={hover ? { x: chart.xOf(hover.i), y: hover.y } : null}
          label={hover ? labels[hover.i] : ""}
          entries={hover ? bars.map((b) => ({ name: b.name ?? b.dataKey, value: data[hover.i]![b.dataKey] })) : []}
        />
      )}
    </Wrapper>
  );
}

let clipSeq = 0;
export function AreaChart(props: ChartProps) {
  const chart = useChart("area", props);
  const { items, frame, yOf, xOf, n, x } = chart;
  const areas = all<AreaProps>(items, Area);
  const tip = find<TooltipProps>(items, Tooltip);
  const defs = items.filter((c) => c.type === "defs");
  const progress = useProgress(areas[0]?.animationDuration ?? 1500, props.active ?? true);
  const { hover, onMove, onLeave } = useHover(chart, "area");
  const [clipId] = useState(() => `eos-area-clip-${++clipSeq}`);
  const { data, width = 0, height = 0 } = props;
  const labels = data.map((r) => String(r[x.dataKey ?? ""] ?? ""));
  const base = frame.top + frame.height;

  const svg = (
    <svg className="recharts-surface" width={width} height={height} viewBox={`0 0 ${width} ${height}`} style={{ width: "100%", height: "100%", display: "block" }} onMouseMove={onMove} onMouseLeave={onLeave}>
      {defs}
      <defs>
        <clipPath id={clipId}>
          <rect x={frame.left} y={0} width={(frame.width + 1) * progress} height={height} />
        </clipPath>
      </defs>
      <Grid chart={chart} />
      {areas.map((a) => {
        const pts = data.map((row, i) => ({ x: xOf(i), y: yOf(Number(row[a.dataKey]) || 0) }));
        const line = monotonePath(pts);
        // Like Recharts: back along the baseline with the same curve, then close.
        const back = monotonePath(pts.map((pt) => ({ x: pt.x, y: base })).reverse());
        const fill = pts.length ? `${line}L${back.slice(1)}Z` : "";
        return (
          <g key={a.dataKey} className="recharts-layer recharts-area" clipPath={progress < 1 ? `url(#${clipId})` : undefined}>
            <path className="recharts-curve recharts-area-area" d={fill} fill={a.fill} stroke="none" fillOpacity={0.6} />
            <path className="recharts-curve recharts-area-curve" d={line} stroke={a.stroke} strokeWidth={a.strokeWidth ?? 1} fill="none" />
          </g>
        );
      })}
      <AxisLine chart={chart} />
      {tip && hover && (
        <path className="recharts-curve recharts-tooltip-cursor" stroke={tip.cursor?.stroke ?? "#ccc"} strokeWidth={1} fill="none" pointerEvents="none" d={`M${xOf(hover.i)},${frame.top}L${xOf(hover.i)},${base}`} />
      )}
      {hover &&
        areas.map((a) => (
          <circle
            key={a.dataKey}
            className="recharts-dot"
            cx={xOf(hover.i)}
            cy={yOf(Number(data[hover.i]![a.dataKey]) || 0)}
            r={a.activeDot?.r ?? 4}
            fill={a.stroke}
            strokeWidth={a.activeDot?.strokeWidth ?? 2}
            stroke={a.activeDot?.stroke ?? "#fff"}
          />
        ))}
      <TickLabels chart={chart} labels={labels} width={width} height={height} />
    </svg>
  );
  return (
    <Wrapper width={width} height={height} svg={svg}>
      {tip && n > 0 && (
        <TooltipBox
          tip={tip}
          frame={frame}
          at={hover ? { x: xOf(hover.i), y: hover.y } : null}
          label={hover ? labels[hover.i] : ""}
          entries={hover ? areas.map((a) => ({ name: a.name ?? a.dataKey, value: data[hover.i]![a.dataKey] })) : []}
        />
      )}
    </Wrapper>
  );
}
