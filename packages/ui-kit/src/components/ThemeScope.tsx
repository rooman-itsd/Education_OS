import type { CSSProperties, ReactNode } from "react";

/** A page accent: a suite's colour for chips, links, progress bars, charts and its hero. */
export interface PageTheme {
  /** Accent for text and icons on white (AA). */
  accent: string;
  /** Soft background for chips and tiles. */
  tint: string;
  /** Hairline ring around chips. */
  ring: string;
  /** Page hero background. */
  gradient: string;
  /** Chart series, in order. */
  series: [string, string, string];
  /** Progress-bar fill. */
  bar: string;
}

/** The brand theme: indigo accent, magenta-to-indigo hero. */
export const BRAND_THEME: PageTheme = {
  accent: "#4338ca",
  tint: "#eeeefd",
  ring: "#dcdcfb",
  gradient: "linear-gradient(100deg, #8a1170 0%, #5b21b6 55%, #3730a3 100%)",
  series: ["#4338ca", "#059669", "#db2777"],
  bar: "linear-gradient(90deg, #3730a3, #4f46e5)",
};

/** One colour per suite so a suite's pages share an accent. Status colours are never themed. */
export const SUITE_THEMES: Record<string, PageTheme> = {
  "student-lifecycle": { accent: "#6d28d9", tint: "#f3eeff", ring: "#e4d8fd", gradient: "linear-gradient(100deg, #6d28d9 0%, #5b21b6 50%, #4338ca 100%)", series: ["#7c3aed", "#f59e0b", "#0ea5e9"], bar: "linear-gradient(90deg, #5b21b6, #7c3aed)" },
  academics: { accent: "#1d4ed8", tint: "#eaf1ff", ring: "#cfdcff", gradient: "linear-gradient(100deg, #1e3a8a 0%, #1d4ed8 55%, #2563eb 100%)", series: ["#2563eb", "#f59e0b", "#10b981"], bar: "linear-gradient(90deg, #1e40af, #3b82f6)" },
  practice: { accent: "#0f766e", tint: "#ecfaf8", ring: "#c5ece6", gradient: "linear-gradient(100deg, #134e4a 0%, #0f766e 55%, #0d9488 100%)", series: ["#0d9488", "#f97316", "#6366f1"], bar: "linear-gradient(90deg, #115e59, #14b8a6)" },
  sports: { accent: "#047857", tint: "#ecfdf5", ring: "#c6efdc", gradient: "linear-gradient(100deg, #064e3b 0%, #047857 55%, #059669 100%)", series: ["#059669", "#f59e0b", "#3b82f6"], bar: "linear-gradient(90deg, #065f46, #10b981)" },
  facilities: { accent: "#b45309", tint: "#fffbeb", ring: "#fde7b3", gradient: "linear-gradient(100deg, #78350f 0%, #b45309 55%, #d97706 100%)", series: ["#d97706", "#2563eb", "#10b981"], bar: "linear-gradient(90deg, #92400e, #f59e0b)" },
  "finance-operations": { accent: "#0f766e", tint: "#f0fdfa", ring: "#bfe9e3", gradient: "linear-gradient(100deg, #134e4a 0%, #0f9f8a 55%, #14b8a6 100%)", series: ["#0f9f8a", "#f59e0b", "#6366f1"], bar: "linear-gradient(90deg, #0f766e, #2dd4bf)" },
  "campus-life": { accent: "#be185d", tint: "#fff1f5", ring: "#fbd0e0", gradient: "linear-gradient(100deg, #831843 0%, #be185d 55%, #e45a8a 100%)", series: ["#e45a8a", "#0ea5e9", "#f59e0b"], bar: "linear-gradient(90deg, #9d174d, #ec4899)" },
  governance: { accent: "#a21caf", tint: "#fdf4ff", ring: "#f3d2fa", gradient: "linear-gradient(100deg, #701a75 0%, #a21caf 55%, #c026d3 100%)", series: ["#c026d3", "#0ea5e9", "#f59e0b"], bar: "linear-gradient(90deg, #86198f, #d946ef)" },
  support: { accent: "#334155", tint: "#f1f5f9", ring: "#dbe2ea", gradient: "linear-gradient(100deg, #1e293b 0%, #334155 55%, #475569 100%)", series: ["#64748b", "#0ea5e9", "#f59e0b"], bar: "linear-gradient(90deg, #334155, #64748b)" },
};

export const themeForSuite = (suite?: string): PageTheme => (suite && SUITE_THEMES[suite]) || BRAND_THEME;

/** Scopes a page accent to its children through CSS variables. */
export function ThemeScope({ theme, children, className, style }: { theme: PageTheme; children: ReactNode; className?: string; style?: CSSProperties }) {
  return (
    <div
      className={className}
      style={{
        "--accent": theme.accent,
        "--accent-tint": theme.tint,
        "--accent-ring": theme.ring,
        "--accent-bar": theme.bar,
        "--hero-gradient": theme.gradient,
        "--eos-chart-1": theme.series[0],
        "--eos-chart-2": theme.series[1],
        "--eos-chart-3": theme.series[2],
        ...style,
      } as CSSProperties}
    >
      {children}
    </div>
  );
}
