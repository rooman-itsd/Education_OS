// Dashboard panels shared by the main Dashboard and every module dashboard:
// histogram, breakdown bars, action-required lists, upcoming events and recent activity.

import React, { useRef, useState } from 'react';
import { useInView } from '../../lib/motion';
import { CountUp } from './CountUp';
import { ArrowRight, Activity, CheckCircle2, AlertTriangle, XCircle, IndianRupee, FileCheck2, ShieldCheck, Trophy, LifeBuoy, BookOpen, Scale, Building2, Cpu } from '../../lib/icons';
import { BarChart, Bar, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from '../../lib/charts';
import { PANEL, PanelHeader } from './dashboard';
import { usePageTheme } from './theme';

/** Brand series (purple, cyan, coral). Pages inside a suite use that suite's series from its theme. */
export const SERIES_COLORS = ['#9333EA', '#0EA5E9', '#F65B66'] as const;

export interface Series {
  key: string;
  name: string;
}

type Row = Record<string, string | number>;

const TOOLTIP_STYLE = {
  contentStyle: {
    backgroundColor: '#FFFFFF',
    border: '1px solid #E2E8F0',
    borderRadius: '8px',
    fontSize: '12px',
    color: '#12233F',
    boxShadow: '0 4px 12px rgba(15, 23, 42, 0.08)'
  },
  itemStyle: { color: '#334155' },
  labelStyle: { color: '#12233F', fontWeight: 600 }
};

/** A small text link for panel headers, e.g. "View admissions →". */
export const PanelLink: React.FC<{ onClick: () => void; children: React.ReactNode }> = ({ onClick, children }) => (
  <button onClick={onClick} className="inline-flex items-center gap-1 text-xs font-medium text-[var(--accent)] hover:opacity-80 pt-0.5 whitespace-nowrap">
    {children}
    <ArrowRight className="w-3.5 h-3.5" />
  </button>
);

export const HistogramPanel: React.FC<{
  title: string;
  subtitle?: string;
  data: Row[];
  /** Field holding the x-axis label. */
  xKey: string;
  /** Up to three series, drawn as grouped bars (or lines in the Trend view). */
  series: Series[];
  tooltipLabel?: (x: string) => string;
  footer?: React.ReactNode;
  className?: string;
  /** Plot height in px. */
  height?: number;
}> = ({ title, subtitle, data, xKey, series, tooltipLabel, footer, className = '', height = 300 }) => {
  const [view, setView] = useState<'trend' | 'bars'>('bars');
  const ref = useRef<HTMLElement>(null);
  const inView = useInView(ref);
  const colors = usePageTheme().series;
  const gid = (k: string) => `g-${title.replace(/\W+/g, '-')}-${k}`;
  const fmtLabel = (x: unknown) => (tooltipLabel ? tooltipLabel(String(x)) : String(x));
  const fmtValue = (v: unknown, n: unknown) => [Number(v).toLocaleString('en-IN'), String(n)] as [string, string];

  const axes = (
    <>
      <CartesianGrid stroke="#F1F5F9" vertical={false} />
      <XAxis dataKey={xKey} stroke="#64748B" fontSize={12} tickLine={false} axisLine={{ stroke: '#E2E8F0' }} />
      <YAxis stroke="#64748B" fontSize={12} tickLine={false} axisLine={false} width={48} tickFormatter={(v: number) => v.toLocaleString('en-IN')} />
    </>
  );

  return (
    <section ref={ref} className={`${PANEL} flex flex-col eos-enter ${inView ? 'is-in' : ''} ${className}`}>
      <PanelHeader
        title={title}
        subtitle={subtitle}
        action={
          <div className="flex items-center gap-1 rounded-lg bg-[#F1F5F9] p-0.5 text-xs" role="tablist" aria-label="Chart view">
            {(['bars', 'trend'] as const).map((v) => (
              <button
                key={v}
                role="tab"
                aria-selected={view === v}
                onClick={() => setView(v)}
                className={`px-2.5 py-1 rounded-md font-medium capitalize transition-colors ${
                  view === v ? 'bg-white text-[#12233F] shadow-[0_1px_2px_rgba(15,23,42,0.08)]' : 'text-[#64748B] hover:text-[#12233F]'
                }`}
              >
                {v}
              </button>
            ))}
          </div>
        }
      />
      {series.length > 1 && (
        <div className="px-5 flex flex-wrap items-center gap-4 text-[12px] text-[#475569]">
          {series.map((s, i) => (
            <span key={s.key} className="inline-flex items-center gap-1.5">
              <span className="w-2.5 h-2.5 rounded-sm" style={{ background: colors[i] }} />
              {s.name}
            </span>
          ))}
        </div>
      )}
      <div className="px-5 pt-3 pb-4 flex-1">
        <div className="w-full" style={{ height }} role="img" aria-label={`${view === 'bars' ? 'Bar chart' : 'Trend'}: ${title}`}>
          <ResponsiveContainer width="100%" height="100%">
            {view === 'bars' ? (
              <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }} barCategoryGap="28%" barGap={4}>
                {axes}
                <Tooltip cursor={{ fill: 'rgba(148, 163, 184, 0.08)' }} formatter={fmtValue} labelFormatter={fmtLabel} {...TOOLTIP_STYLE} />
                {series.map((s, i) => (
                  <Bar key={s.key} dataKey={s.key} name={s.name} fill={colors[i]} radius={[4, 4, 0, 0]} maxBarSize={40} animationDuration={700} />
                ))}
              </BarChart>
            ) : (
              <AreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                <defs>
                  {series.map((s, i) => (
                    <linearGradient key={s.key} id={gid(s.key)} x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor={colors[i]} stopOpacity={0.16} />
                      <stop offset="100%" stopColor={colors[i]} stopOpacity={0} />
                    </linearGradient>
                  ))}
                </defs>
                {axes}
                <Tooltip formatter={fmtValue} labelFormatter={fmtLabel} {...TOOLTIP_STYLE} />
                {series.map((s, i) => (
                  <Area
                    key={s.key}
                    type="monotone"
                    dataKey={s.key}
                    name={s.name}
                    stroke={colors[i]}
                    strokeWidth={2}
                    fill={`url(#${gid(s.key)})`}
                    activeDot={{ r: 5, strokeWidth: 2, stroke: '#FFFFFF' }}
                    animationDuration={700}
                  />
                ))}
              </AreaChart>
            )}
          </ResponsiveContainer>
        </div>
      </div>
      {footer}
    </section>
  );
};

export interface BreakdownItem {
  label: string;
  count: number;
  /** Bar colour for this row; defaults to the page accent. */
  color?: string;
}

/** Horizontal bars, each relative to the largest item (like the admissions funnel). */
export const BreakdownPanel: React.FC<{
  title: string;
  subtitle?: string;
  items: BreakdownItem[];
  action?: React.ReactNode;
  footer?: { label: string; value: string };
  /** Show each bar's share of the first item instead of the largest. */
  relativeToFirst?: boolean;
  /** Suffix for each value, e.g. "%". */
  unit?: string;
  className?: string;
}> = ({ title, subtitle, items, action, footer, relativeToFirst, unit = '', className = '' }) => {
  const max = relativeToFirst ? items[0]?.count || 1 : Math.max(1, ...items.map((i) => i.count));
  const ref = useRef<HTMLElement>(null);
  const inView = useInView(ref);
  return (
    <section ref={ref} className={`${PANEL} flex flex-col eos-enter ${inView ? 'is-in' : ''} ${className}`} style={{ '--enter-delay': '120ms' } as React.CSSProperties}>
      <PanelHeader title={title} subtitle={subtitle} action={action} />
      <div className="px-5 pt-1 pb-4 space-y-4 flex-1">
        {items.map((it, i) => {
          const pct = Math.round((it.count / max) * 1000) / 10;
          const delay = 250 + i * 160;
          return (
            <div key={it.label} className="space-y-1.5">
              <div className="flex items-center justify-between text-[13px] gap-3">
                <span className="text-[#334155] truncate inline-flex items-center gap-2">
                  {it.color && <span className="w-2 h-2 rounded-full flex-shrink-0" style={{ background: it.color }} aria-hidden />}
                  {it.label}
                </span>
                <span className="whitespace-nowrap">
                  <span className="font-semibold text-[#12233F] tabular-nums">
                    <CountUp end={it.count} active={inView} duration={1000} delay={delay} />
                    {unit}
                  </span>
                  {relativeToFirst && (
                    <span className="text-[11px] text-[#64748B] ml-1.5 tabular-nums" style={{ opacity: inView ? 1 : 0, transition: `opacity 400ms ease ${delay + 300}ms` }}>
                      {pct}%
                    </span>
                  )}
                </span>
              </div>
              <div className="w-full h-1.5 bg-[#F1F5F9] rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full eos-fill eos-sheen ${inView ? 'is-in' : ''}`}
                  style={{ width: inView ? `${pct}%` : 0, backgroundImage: it.color ? `linear-gradient(90deg, ${it.color}99, ${it.color})` : 'var(--accent-bar)', transitionDelay: `${delay}ms`, '--sheen-delay': `${delay + 900}ms` } as React.CSSProperties}
                />
              </div>
            </div>
          );
        })}
      </div>
      {footer && (
        <div className="px-5 py-3 border-t border-[#F1F5F9] flex items-center justify-between text-xs">
          <span className="text-[#475569]">{footer.label}</span>
          <span className="font-semibold text-[#12233F]">{footer.value}</span>
        </div>
      )}
    </section>
  );
};

export type Urgency = 'Urgent' | 'Pending' | 'Review' | 'Approved';

const URGENCY_STYLE: Record<Urgency, string> = {
  Urgent: 'text-[#B91C1C]',
  Pending: 'text-[#8A4F00]',
  Review: 'text-[#475569]',
  Approved: 'text-[#126B3D]'
};

export interface ActionItem {
  id: string;
  ref: string;
  type: string;
  title: string;
  description: string;
  urgency: Urgency;
  time: string;
}

/** Detailed queue of individual items (module dashboards). */
export const ActionPanel: React.FC<{ items: ActionItem[]; onOpen: (item: ActionItem) => void }> = ({ items, onOpen }) => (
  <section className={PANEL}>
    <PanelHeader title="Action Required" subtitle={`${items.length} items awaiting your decision`} />
    <ul className="divide-y divide-[#F1F5F9] border-t border-[#F1F5F9]">
      {items.map((item) => (
        <li key={item.id}>
          <button
            onClick={() => onOpen(item)}
            className="w-full text-left px-5 py-3 flex items-start justify-between gap-4 hover:bg-[#F6F8FB] group"
          >
            <div className="min-w-0">
              <div className="flex items-center gap-2 text-[11px]">
                <span className="font-mono text-[#475569]">{item.ref}</span>
                <span className="text-[#CBD5E1]">·</span>
                <span className="text-[#475569]">{item.type}</span>
                <span className={`font-medium ${URGENCY_STYLE[item.urgency]}`}>{item.urgency}</span>
              </div>
              <p className="text-[13px] font-medium text-[#12233F] mt-0.5 truncate">{item.title}</p>
              <p className="text-xs text-[#64748B] truncate">{item.description}</p>
            </div>
            <div className="flex items-center gap-2 flex-shrink-0 pt-0.5">
              <span className="text-[11px] text-[#64748B] whitespace-nowrap">{item.time}</span>
              <ArrowRight className="w-3.5 h-3.5 text-[#64748B] group-hover:text-[#DC3545]" />
            </div>
          </button>
        </li>
      ))}
    </ul>
  </section>
);

export type Level = 'urgent' | 'pending' | 'normal';

/** A soft colour pair from the design palette: text/icon colour and its tint. */
export interface Tone {
  fg: string;
  bg: string;
}

const LEVEL_TONE: Record<Level, Tone> = {
  urgent: { fg: '#B91C1C', bg: '#FEF2F2' },
  pending: { fg: '#8A4F00', bg: '#FEF3E2' },
  normal: { fg: '#475569', bg: '#F1F5F9' }
};
const LEVEL_TEXT: Record<Level, string> = { urgent: 'Urgent', pending: 'Pending', normal: 'Open' };

export interface QueueRow {
  label: string;
  count: number;
  level: Level;
  onOpen: () => void;
  icon?: React.ComponentType<{ className?: string }>;
  tone?: Tone;
}

/** Segmented control in the style of the chart's Bars / Trend switch. */
function Segmented<T extends string>({ value, options, onChange, label }: { value: T; options: [T, string][]; onChange: (v: T) => void; label: string }) {
  return (
    <div className="flex items-center gap-1 rounded-lg bg-[#F1F5F9] p-0.5 text-xs" role="tablist" aria-label={label}>
      {options.map(([v, text]) => (
        <button
          key={v}
          role="tab"
          aria-selected={value === v}
          onClick={() => onChange(v)}
          className={`px-2.5 py-1 rounded-md font-medium capitalize transition-colors ${
            value === v ? 'bg-white text-[#12233F] shadow-[0_1px_2px_rgba(15,23,42,0.08)]' : 'text-[#64748B] hover:text-[#12233F]'
          }`}
        >
          {text}
        </button>
      ))}
    </div>
  );
}

/** Approval queues: one coloured row per queue, filterable by urgency, with each queue's share of the total. */
export const ActionSummaryPanel: React.FC<{ rows: QueueRow[]; action?: React.ReactNode; className?: string }> = ({ rows, action, className = '' }) => {
  const [filter, setFilter] = useState<'all' | 'urgent' | 'pending'>('all');
  const ref = useRef<HTMLElement>(null);
  const inView = useInView(ref);
  const visible = rows.filter((r) => filter === 'all' || r.level === filter);
  const total = rows.reduce((n, r) => n + r.count, 0);
  const shown = visible.reduce((n, r) => n + r.count, 0);
  const max = Math.max(1, ...rows.map((r) => r.count));
  return (
    <section ref={ref} className={`${PANEL} flex flex-col eos-enter ${inView ? 'is-in' : ''} ${className}`}>
      <PanelHeader
        title="Action Required"
        subtitle={filter === 'all' ? `${total} items awaiting decision` : `${shown} of ${total} items · ${filter}`}
        action={
          action ?? (
            <Segmented
              label="Filter queues"
              value={filter}
              onChange={setFilter}
              options={[['all', 'All'], ['urgent', 'Urgent'], ['pending', 'Pending']]}
            />
          )
        }
      />
      <ul className={`px-2 pb-2 flex-1 eos-reveal ${inView ? 'is-in' : ''}`} key={filter}>
        {visible.map((r, idx) => {
          const tone = r.tone ?? LEVEL_TONE[r.level];
          const level = LEVEL_TONE[r.level];
          const Icon = r.icon ?? ArrowRight;
          return (
            <li key={r.label} style={{ '--i': idx } as React.CSSProperties}>
              <button onClick={r.onOpen} className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left hover:bg-[#F6F8FB] group">
                <span className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 eos-pop-in" style={{ background: tone.bg, color: tone.fg }} aria-hidden>
                  <Icon className="w-4 h-4" />
                </span>
                <span className="flex-1 min-w-0">
                  <span className="block text-[13px] text-[#12233F] truncate">{r.label}</span>
                  <span className="block mt-1 h-1.5 w-full bg-[#F1F5F9] rounded-full overflow-hidden">
                    <span
                      className="block h-full rounded-full eos-fill"
                      style={{ width: inView ? `${(r.count / max) * 100}%` : 0, background: tone.fg, transitionDelay: `${350 + idx * 110}ms` }}
                    />
                  </span>
                </span>
                <span className="text-[11px] font-medium px-2 py-0.5 rounded-full" style={{ background: level.bg, color: level.fg }}>
                  {LEVEL_TEXT[r.level]}
                </span>
                <span className="w-8 text-right text-[14px] font-semibold text-[#12233F] tabular-nums">{r.count}</span>
                <ArrowRight className="w-3.5 h-3.5 text-[#CBD5E1] group-hover:text-[#DC3545]" />
              </button>
            </li>
          );
        })}
        {visible.length === 0 && <li className="px-3 py-8 text-center text-xs text-[#64748B]">Nothing {filter} right now.</li>}
      </ul>
    </section>
  );
};

export interface UpcomingItem {
  /** ISO date, e.g. "2026-10-08". */
  date: string;
  title: string;
  meta: string;
  /** Short category label shown on hover, e.g. "Exam". */
  category?: string;
  tone?: Tone;
  onOpen?: () => void;
}

const DAY_MS = 86_400_000;
const startOfToday = () => {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d;
};
const daysUntil = (iso: string) => Math.round((new Date(`${iso}T00:00:00`).getTime() - startOfToday().getTime()) / DAY_MS);
const relative = (days: number) => (days <= 0 ? 'Today' : days === 1 ? 'Tomorrow' : `In ${days} days`);

/** Dated events and deadlines in the next two weeks, colour-coded by category, with a live countdown. */
export const UpcomingPanel: React.FC<{ items: UpcomingItem[]; className?: string }> = ({ items, className = '' }) => {
  const [filter, setFilter] = useState<'all' | 'week' | 'later'>('all');
  const ref = useRef<HTMLElement>(null);
  const inView = useInView(ref);
  const sorted = [...items].sort((a, b) => a.date.localeCompare(b.date)).filter((it) => daysUntil(it.date) >= 0);
  const visible = sorted.filter((it) => {
    const d = daysUntil(it.date);
    return filter === 'all' || (filter === 'week' ? d <= 7 : d > 7);
  });
  return (
    <section ref={ref} className={`${PANEL} flex flex-col eos-enter ${inView ? 'is-in' : ''} ${className}`} style={{ '--enter-delay': '120ms' } as React.CSSProperties}>
      <PanelHeader
        title="Upcoming"
        subtitle={`Next two weeks · ${sorted.length} scheduled`}
        action={
          <Segmented
            label="Filter upcoming"
            value={filter}
            onChange={setFilter}
            options={[['all', 'All'], ['week', 'This week'], ['later', 'Later']]}
          />
        }
      />
      <ul className={`px-5 pb-3 flex-1 divide-y divide-[#F1F5F9] eos-reveal ${inView ? 'is-in' : ''}`} key={filter}>
        {visible.map((it, idx) => {
          const d = new Date(`${it.date}T00:00:00`);
          const days = daysUntil(it.date);
          const tone = it.tone ?? { fg: 'var(--accent)', bg: 'var(--accent-tint)' };
          const soon = days <= 2;
          const body = (
            <>
              <div className="w-11 flex-shrink-0 text-center rounded-lg py-1" style={{ background: tone.bg, boxShadow: `inset 0 0 0 1px ${tone.fg}33` }}>
                <div className="text-[15px] leading-none font-bold tabular-nums" style={{ color: tone.fg }}>
                  {d.getDate().toString().padStart(2, '0')}
                </div>
                <div className="text-[10px] mt-0.5 font-medium uppercase text-[#64748B]">{d.toLocaleDateString('en-GB', { month: 'short' })}</div>
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-[13px] font-medium text-[#12233F] truncate">{it.title}</p>
                <p className="text-xs text-[#64748B] truncate">{it.meta}</p>
              </div>
              <span
                className="text-[11px] font-medium px-2 py-0.5 rounded-full whitespace-nowrap eos-slide-in"
                style={soon ? { background: '#FEF2F2', color: '#B91C1C' } : { background: tone.bg, color: tone.fg }}
                title={it.category}
              >
                {relative(days)}
              </span>
            </>
          );
          return (
            <li key={it.date + it.title} style={{ '--i': idx } as React.CSSProperties}>
              {it.onOpen ? (
                <button onClick={it.onOpen} className="w-full flex items-center gap-4 py-2.5 text-left rounded-lg hover:bg-[#F6F8FB] group">
                  {body}
                  <ArrowRight className="w-3.5 h-3.5 text-[#CBD5E1] group-hover:text-[#DC3545]" />
                </button>
              ) : (
                <div className="flex items-center gap-4 py-2.5">{body}</div>
              )}
            </li>
          );
        })}
        {visible.length === 0 && <li className="py-8 text-center text-xs text-[#64748B]">Nothing scheduled {filter === 'week' ? 'this week' : 'later'}.</li>}
      </ul>
    </section>
  );
};

type IconType = React.ComponentType<{ className?: string }>;

export interface ActivityTone {
  icon: IconType;
  bg: string;
  fg: string;
}

export interface ActivityItem {
  id: string;
  time: string;
  title: string;
  meta: React.ReactNode;
  status: 'Success' | 'Failed' | 'Warning';
  /** Icon and muted chip colour for the row; defaults to the page accent. */
  tone?: ActivityTone;
}

/** Row icon and colour by the acting role, in the same muted tones as the KPI chips. */
const ROLE_TONES: Record<string, ActivityTone> = {
  'finance-staff': { icon: IndianRupee, bg: '#EAF6EC', fg: '#15803D' },
  'examination-staff': { icon: FileCheck2, bg: '#EEEEFD', fg: '#4338CA' },
  'org-admin': { icon: ShieldCheck, bg: '#F3EEFF', fg: '#6D28D9' },
  'super-admin': { icon: ShieldCheck, bg: '#F3EEFF', fg: '#6D28D9' },
  'department-admin': { icon: Trophy, bg: '#FFF1E6', fg: '#C2410C' },
  coach: { icon: Trophy, bg: '#FFF1E6', fg: '#C2410C' },
  'support-staff': { icon: LifeBuoy, bg: '#E8F4FD', fg: '#0369A1' },
  faculty: { icon: BookOpen, bg: '#EAF1FF', fg: '#1D4ED8' },
  governance: { icon: Scale, bg: '#FDECEC', fg: '#C2353F' },
  facility: { icon: Building2, bg: '#ECFAF8', fg: '#0F766E' },
  system: { icon: Cpu, bg: '#F1F5F9', fg: '#475569' }
};

export const activityToneForRole = (roleId: string): ActivityTone | undefined => ROLE_TONES[roleId];

const STATUS_CHIP: Record<ActivityItem['status'], { cls: string; icon: IconType }> = {
  Success: { cls: 'bg-[#EEF7F1] text-[#126B3D] ring-[#CDE8D8]', icon: CheckCircle2 },
  Warning: { cls: 'bg-[#FEF3E2] text-[#8A4F00] ring-[#FBE3BD]', icon: AlertTriangle },
  Failed: { cls: 'bg-[#FEF2F2] text-[#B91C1C] ring-[#FECACA]', icon: XCircle }
};

/** Audit timeline: coloured role icons on a connecting line, rows slide in one after another. */
export const ActivityPanel: React.FC<{ items: ActivityItem[]; subtitle?: string; action?: React.ReactNode }> = ({
  items,
  subtitle = 'Sample events',
  action
}) => (
  <section className={PANEL}>
    <PanelHeader
      title={
        <span className="inline-flex items-center gap-2.5">
          <span className="w-7 h-7 rounded-lg bg-[var(--accent-tint)] text-[var(--accent)] flex items-center justify-center">
            <Activity className="w-4 h-4" />
          </span>
          Recent Activity
          <span className="inline-flex items-center gap-1.5 rounded-full bg-[#F1F5F9] px-2 py-0.5 text-[10.5px] font-semibold text-[#475569]">
            Sample
          </span>
        </span>
      }
      subtitle={subtitle}
      action={action}
    />
    <ul className="relative px-3 pb-3">
      {items.map((item, i) => {
        const tone = item.tone ?? { icon: Activity, bg: 'var(--accent-tint)', fg: 'var(--accent)' };
        const Icon = tone.icon;
        const status = STATUS_CHIP[item.status];
        const StatusIcon = status.icon;
        const last = i === items.length - 1;
        return (
          <li
            key={item.id}
            className="group relative flex items-center gap-4 rounded-lg px-2 py-2.5 transition-all duration-200 hover:bg-[#F8FAFC] hover:translate-x-0.5 animate-fade-up"
            style={{ animationDelay: `${120 + i * 70}ms` }}
          >
            <span className="hidden sm:block w-20 flex-shrink-0 text-right text-[12px] font-medium text-[#64748B] tabular-nums">{item.time}</span>
            {/* timeline node */}
            <span className="relative flex-shrink-0 self-stretch flex items-center">
              {!last && <span aria-hidden className="absolute left-1/2 top-1/2 h-[calc(100%+20px)] w-px -translate-x-1/2 bg-[#E6EAF0]" />}
              <span
                className="relative z-10 w-8 h-8 rounded-full ring-4 ring-white flex items-center justify-center transition-transform duration-200 group-hover:scale-110"
                style={{ backgroundColor: tone.bg, color: tone.fg }}
              >
                <Icon className="w-4 h-4" />
              </span>
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-[13.5px] font-medium text-[#12233F] truncate">{item.title}</p>
              <p className="text-xs text-[#64748B] truncate">{item.meta}</p>
            </div>
            <span className={`inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-1 rounded-md ring-1 flex-shrink-0 ${status.cls}`}>
              <StatusIcon className="w-3.5 h-3.5" />
              {item.status}
            </span>
          </li>
        );
      })}
    </ul>
  </section>
);
