import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Icons, prefersReducedMotion } from "@eos/ui-kit";
import { STATUS_LABEL, type IconName, type ImplStatus } from "../content";

export interface WallModule {
  name: string;
  icon: IconName;
  status: ImplStatus;
}

/** Cell pitch (tile + gap) in px; smaller on phones. */
const CELL_WIDE = 58;
const CELL_NARROW = 46;
/** How far from the pointer tiles still lift, in px. */
const REACH = 170;

/** A fixed shuffle so the wall looks the same on every visit (and on the server, if ever rendered there). */
function scatter(count: number, seed: number): number[] {
  const order = Array.from({ length: count }, (_, i) => i);
  let s = seed;
  for (let i = count - 1; i > 0; i--) {
    s = (s * 1103515245 + 12345) % 2147483648;
    const j = s % (i + 1);
    [order[i], order[j]] = [order[j] as number, order[i] as number];
  }
  return order;
}

/**
 * Features-page hero background: the catalogue as a wall of tiles. Every module in the catalogue is one
 * tile, drawn with its product area's icon and coloured by its real status (solid orange = implemented,
 * soft orange = partially implemented, white = specified, dashed = scaffold), scattered among empty
 * cells. Tiles near the pointer lift towards it and a tile under the pointer names its module; on touch
 * screens a slow wave runs across the wall instead. `highlight` dims every tile not in that set (used by
 * the hero's counts). Decorative: hidden from assistive technology, the same facts are in the page.
 */
export function ModuleWall({
  modules,
  highlight,
}: {
  modules: WallModule[];
  highlight: "code" | "modules" | null;
}) {
  const rootRef = useRef<HTMLDivElement>(null);
  const [grid, setGrid] = useState({ cols: 0, rows: 0, cell: CELL_WIDE });

  // Size the grid to the hero.
  useLayoutEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    const measure = () => {
      const { width, height } = root.getBoundingClientRect();
      const cell = width < 640 ? CELL_NARROW : CELL_WIDE;
      const cols = Math.ceil(width / cell) + 1;
      const rows = Math.ceil(height / cell) + 1;
      setGrid((g) => (g.cols === cols && g.rows === rows && g.cell === cell ? g : { cols, rows, cell }));
    };
    measure();
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(measure);
    ro.observe(root);
    return () => ro.disconnect();
  }, []);

  // Lift tiles near the pointer (mouse only; one update per frame).
  useEffect(() => {
    const root = rootRef.current;
    const host = root?.parentElement;
    if (!root || !host || prefersReducedMotion()) return;
    const tiles: HTMLElement[] = Array.from(root.querySelectorAll<HTMLElement>(".wpc-mw__cell"));
    let frame = 0;
    let px = -1e4;
    let py = -1e4;
    const lifted = new Set<HTMLElement>();
    const paint = () => {
      frame = 0;
      const box = root.getBoundingClientRect();
      for (const tile of tiles) {
        const cx = tile.offsetLeft + tile.offsetWidth / 2;
        const cy = tile.offsetTop + tile.offsetHeight / 2;
        const d = Math.hypot(px - box.left - cx, py - box.top - cy);
        const lift = d < REACH ? 1 - d / REACH : 0;
        if (lift > 0) {
          tile.style.setProperty("--lift", lift.toFixed(2));
          lifted.add(tile);
        } else if (lifted.has(tile)) {
          tile.style.removeProperty("--lift");
          lifted.delete(tile);
        }
      }
    };
    const onMove = (e: PointerEvent) => {
      if (e.pointerType !== "mouse") return;
      px = e.clientX;
      py = e.clientY;
      if (!frame) frame = requestAnimationFrame(paint);
    };
    const onLeave = () => {
      px = py = -1e4;
      if (!frame) frame = requestAnimationFrame(paint);
    };
    host.addEventListener("pointermove", onMove);
    host.addEventListener("pointerleave", onLeave);
    return () => {
      host.removeEventListener("pointermove", onMove);
      host.removeEventListener("pointerleave", onLeave);
      if (frame) cancelAnimationFrame(frame);
    };
  }, [grid]);

  const total = grid.cols * grid.rows;
  // Place module tiles in the shuffled cells, keeping the top row free so names have room above.
  const slots = new Map<number, WallModule>();
  if (total > 0) {
    const order = scatter(total, 7).filter((i) => i >= grid.cols);
    modules.forEach((m, k) => {
      const at = order[k];
      if (at !== undefined) slots.set(at, m);
    });
  }

  return (
    <div
      ref={rootRef}
      className={highlight ? `wpc-mw is-${highlight}` : "wpc-mw"}
      style={{ ["--cell" as string]: `${grid.cell}px`, ["--cols" as string]: grid.cols }}
      aria-hidden
    >
      {Array.from({ length: total }, (_, i) => {
        const m = slots.get(i);
        const wave = { ["--d" as string]: (i % grid.cols) + Math.floor(i / grid.cols) };
        if (!m) return <span key={i} className="wpc-mw__cell" style={wave} />;
        const Icon = Icons[m.icon];
        const code = m.status === "implemented" || m.status === "partial";
        return (
          <span
            key={i}
            className={`wpc-mw__cell wpc-mw__tile is-${m.status}${code ? " has-code" : ""}`}
            style={wave}
          >
            <Icon size={18} aria-hidden />
            <span className="wpc-mw__tip">
              {m.name}
              <em>{STATUS_LABEL[m.status]}</em>
            </span>
          </span>
        );
      })}
    </div>
  );
}
