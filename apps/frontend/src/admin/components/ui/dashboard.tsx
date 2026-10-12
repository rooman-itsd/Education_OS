// Shared page building blocks in the Dashboard's visual language, so every page
// in the sidebar renders its header, stat cards, panels and buttons the same way.

import React from 'react';
import { Link } from '../../lib/router';

export type Tone = 'up' | 'alert' | 'muted';

export interface Stat {
  label: string;
  value: React.ReactNode;
  icon: React.ComponentType<{ className?: string }>;
  /** Small figure under the value, e.g. "+4.8%" or "12 urgent". */
  delta?: React.ReactNode;
  deltaTone?: Tone;
  /** Supporting text after the delta, e.g. "vs. last session". */
  note?: React.ReactNode;
  /** Icon-chip colour; defaults from position and delta tone. */
  accent?: Accent;
  /** Makes the card a link to the page behind the number. */
  to?: string;
  /** Small indicator at the bottom of the card (sparkline, ring, bar). */
  viz?: React.ReactNode;
}

/** A card's restrained accent (top line, indicator) and its pastel icon chip; the card stays white. */
export interface CardPalette {
  accent: string;
  chipBg: string;
  chipFg: string;
  /** Very soft card background and border in the card's colour. */
  tint: string;
  border: string;
}

/** Order matches the Dashboard KPIs: students, athletes, approvals, fees, faculty, tickets. */
export const CARD_PALETTES: CardPalette[] = [
  { accent: '#315EA8', chipBg: '#FFFFFF', chipFg: '#315EA8', tint: '#F3F7FD', border: '#DCE5F3' }, // blue
  { accent: '#159A72', chipBg: '#FFFFFF', chipFg: '#127F5E', tint: '#F1FAF6', border: '#D3EEE4' }, // emerald
  { accent: '#E45B67', chipBg: '#FFFFFF', chipFg: '#C9414E', tint: '#FEF5F6', border: '#F7DCDF' }, // coral
  { accent: '#22A06B', chipBg: '#FFFFFF', chipFg: '#1B8458', tint: '#F2FAF6', border: '#D4EEE2' }, // green
  { accent: '#6256C9', chipBg: '#FFFFFF', chipFg: '#5247B5', tint: '#F6F5FD', border: '#E1DEF6' }, // indigo
  { accent: '#E89A35', chipBg: '#FFFFFF', chipFg: '#B8721A', tint: '#FEF9F2', border: '#F6E6CD' } // amber
];

const DELTA_TONE: Record<Tone, string> = {
  up: 'text-[#126B3D]',
  alert: 'text-[#B91C1C]',
  muted: 'text-[#475569]'
};

/**
 * Icon-chip accents from the brand palette. Cards stay white; only the small chip
 * carries colour, and the colour has a meaning: navy primary, green growth,
 * orange attention, coral urgent.
 */
export type Accent = 'navy' | 'green' | 'orange' | 'coral';
const ACCENTS: Record<Accent, string> = {
  // navy = the page's own accent (brand purple, or the suite colour inside a suite)
  navy: 'bg-[var(--accent-tint)] text-[var(--accent)] ring-[var(--accent-ring)]',
  green: 'bg-[#EEF7F1] text-[#126B3D] ring-[#CDE8D8]',
  orange: 'bg-[#FFF8EC] text-[#A35F00] ring-[#FBE3BD]',
  coral: 'bg-[#FEF2F2] text-[#B91C1C] ring-[#FECACA]'
};
/** Default accent: the first card is the primary KPI; others follow their delta. */
const accentFor = (index: number, tone: Tone): Accent => (index === 0 ? 'navy' : tone === 'alert' ? 'orange' : tone === 'up' ? 'green' : 'navy');

/**
 * KPI card: white, light border, a small tinted icon chip; status colour is kept for
 * the delta line. The card itself never moves: numbers count up, the small indicator
 * loops quietly, and on hover the border and shadow take the card colour and the chip fills in.
 * With `to`, the card opens its page.
 */
export const StatCard: React.FC<Stat & { index?: number; palette?: CardPalette }> = ({
  label,
  value,
  icon: Icon,
  delta,
  deltaTone = 'up',
  note,
  index = 0,
  accent,
  to,
  palette,
  viz
}) => {
  const body = (
    <>
      <div className="flex items-start justify-between gap-2">
        <span className="text-[13px] font-medium leading-snug text-[#5B6B82]">{label}</span>
        {palette ? (
          <span
            className="w-9 h-9 rounded-[10px] flex items-center justify-center flex-shrink-0 shadow-[0_1px_3px_rgba(16,24,40,0.08)] transition-colors duration-200 bg-[var(--chip-bg)] text-[var(--chip-fg)] group-hover:bg-[var(--chip-fg)] group-hover:text-white"
          >
            <Icon className="w-4 h-4" />
          </span>
        ) : (
          <span
            className={`w-8 h-8 rounded-lg ring-1 flex items-center justify-center flex-shrink-0 ${ACCENTS[accent ?? accentFor(index, deltaTone)]}`}
          >
            <Icon className="w-4 h-4" />
          </span>
        )}
      </div>
      <div className="mt-auto pt-3 flex items-end justify-between gap-4">
        <div className="min-w-0">
          <div className="text-[30px] leading-none font-extrabold tracking-[-0.02em] text-[#12233F] tabular-nums break-words">{value}</div>
          {(delta || note) && (
            <div className="mt-2 text-[12px] leading-snug">
              {delta && (
                <span className={`inline-flex items-center gap-1 font-semibold ${DELTA_TONE[deltaTone]}`}>
                  {deltaTone === 'alert' && (
                    <span className="w-1.5 h-1.5 rounded-full bg-[#DC2626]" />
                  )}
                  {delta}
                </span>
              )}
              {delta && note && <span className="text-[#CBD5E1]"> · </span>}
              {note && <span className="text-[#64748B]">{note}</span>}
            </div>
          )}
        </div>
        {viz && <div className="flex-shrink-0 w-24 h-[30px] flex items-end justify-end pb-1">{viz}</div>}
      </div>
    </>
  );
  const cls =
    'group relative flex flex-col h-full min-h-[150px] overflow-hidden rounded-[14px] border border-[#E4E8EF] bg-white px-6 pt-5 pb-5 min-w-0 shadow-[0_1px_2px_rgba(16,24,40,0.03)] transition-[box-shadow,border-color] duration-200 ease-out hover:border-[var(--card-ring)] hover:shadow-[0_10px_24px_-14px_var(--card-shadow)]';
  const style = {
    animationDelay: `${index * 60}ms`,
    '--card-ring': palette ? `${palette.accent}55` : 'var(--accent-ring)',
    '--card-shadow': palette ? `${palette.accent}55` : 'rgba(15,23,42,0.25)',
    ...(palette
      ? { '--chip-bg': palette.chipBg, '--chip-fg': palette.chipFg, backgroundColor: palette.tint, borderColor: palette.border }
      : {})
  } as React.CSSProperties;
  return to ? (
    <Link to={to} className={`${cls} focus:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)]`} style={style}>
      {body}
    </Link>
  ) : (
    <div className={cls} style={style}>
      {body}
    </div>
  );
};

/** A row of stat cards: four across; six fill three columns on laptops and one row on wide screens. */
export const StatGrid: React.FC<{ stats: Stat[]; label?: string; /** Give each card its own muted icon colour. */ colorful?: boolean }> = ({
  stats,
  label = 'Key metrics',
  colorful = false
}) => (
  <section
    aria-label={label}
    className={`grid gap-5 grid-cols-1 min-[420px]:grid-cols-2 ${stats.length > 4 ? 'md:grid-cols-3 2xl:grid-cols-6' : 'lg:grid-cols-4'}`}
  >
    {stats.map((s, i) => (
      <StatCard key={s.label} index={i} palette={colorful ? CARD_PALETTES[i % CARD_PALETTES.length] : undefined} {...s} />
    ))}
  </section>
);

export const PageHeader: React.FC<{
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  /** Small line above the title, e.g. the suite a module belongs to. */
  eyebrow?: React.ReactNode;
  actions?: React.ReactNode;
  /** Background photo/art behind the hero. With art, the hero is taller and the actions sit under the text. */
  art?: React.ReactNode;
}> = ({ title, subtitle, eyebrow, actions, art }) =>
  art ? (
    <header className="eos-hero relative overflow-visible rounded-xl text-white min-h-[200px] md:min-h-[240px] flex items-end">
      <div aria-hidden className="pointer-events-none absolute inset-0 overflow-hidden rounded-xl">
        {art}
      </div>
      <div className="relative z-10 px-6 py-7 sm:px-9 max-w-[560px]">
        {eyebrow && <div className="eos-hero-sub text-[12px] font-medium mb-1.5">{eyebrow}</div>}
        <h1 className="text-[32px] leading-tight font-bold tracking-[-0.02em] text-white">{title}</h1>
        {subtitle && <div className="eos-hero-sub text-[14px] mt-1.5">{subtitle}</div>}
        {actions && <div className="mt-5 flex flex-wrap items-center gap-2.5">{actions}</div>}
      </div>
    </header>
  ) : (
  <header className="eos-hero relative rounded-xl px-6 py-7 sm:px-8 flex flex-col md:flex-row md:items-end md:justify-between gap-5 text-white">
    <div className="relative z-10 min-w-0">
      {eyebrow && <div className="eos-hero-sub text-[12px] font-medium mb-1.5">{eyebrow}</div>}
      <h1 className="text-[30px] leading-tight font-bold tracking-[-0.02em] text-white">{title}</h1>
      {subtitle && <div className="eos-hero-sub text-sm mt-1.5">{subtitle}</div>}
    </div>
    {actions && <div className="relative z-10 flex flex-wrap items-center gap-2">{actions}</div>}
  </header>
);

export const BTN_PRIMARY =
  'inline-flex items-center gap-1.5 h-9 px-4 rounded-lg bg-[#F65B66] text-white text-[13px] font-semibold hover:bg-[#E9505C] transition-colors eos-btn-primary';
export const BTN_SECONDARY =
  'inline-flex items-center gap-1.5 h-9 px-4 rounded-lg bg-white border border-[#E2E8F0] text-xs font-semibold text-[#12233F] hover:border-[#CBD5E1] hover:bg-[#F6F8FB] transition-colors eos-btn-secondary';
/** Kept for existing callers; neutral so that only one coloured button shows at a time. */
export const BTN_ACCENT = BTN_SECONDARY;
/** Destructive or urgent action. */
export const BTN_DANGER =
  'inline-flex items-center gap-1.5 h-9 px-4 rounded-lg bg-white border border-[#FECACA] text-xs font-semibold text-[#B91C1C] hover:bg-[#FEF2F2] transition-colors';

export const PANEL = 'bg-white border border-[#E2E8F0] rounded-xl';

export const PanelHeader: React.FC<{ title: React.ReactNode; subtitle?: React.ReactNode; action?: React.ReactNode }> = ({
  title,
  subtitle,
  action
}) => (
  <div className="flex items-start justify-between gap-4 px-5 pt-4 pb-3">
    <div className="min-w-0">
      <h2 className="text-[15px] font-semibold text-[#12233F]">{title}</h2>
      {subtitle && <p className="text-xs text-[#64748B] mt-0.5">{subtitle}</p>}
    </div>
    {action}
  </div>
);
