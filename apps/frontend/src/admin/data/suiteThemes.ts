// Per-suite colour themes, so each suite's pages have their own inner colours
// (hero gradient, icon chips, chart series, progress bars, links). Status colours
// (green / amber / red) are shared and never themed. Chart pairs are validated for
// colour-blind separation; gradient stops keep white text at AA contrast.

import { findModule } from './architecture';

export interface PageTheme {
  /** Accent for text and icons on white (AA). */
  accent: string;
  /** Soft background for chips and tiles. */
  tint: string;
  /** Hairline ring/border around chips. */
  ring: string;
  /** Page hero background. */
  gradient: string;
  /** Chart series, in order. */
  series: [string, string, string];
  /** Progress-bar fill. */
  bar: string;
}

/** Brand theme: Dashboard, admin screens, platform services and integrations. */
export const BRAND_THEME: PageTheme = {
  accent: '#4338CA',
  tint: '#EEEEFD',
  ring: '#DCDCFB',
  gradient: 'linear-gradient(100deg, #8A1170 0%, #5B21B6 55%, #3730A3 100%)',
  series: ['#4338CA', '#059669', '#DB2777'],
  bar: 'linear-gradient(90deg, #3730A3, #4F46E5)'
};

export const SUITE_THEMES: Record<string, PageTheme> = {
  // A · Student Lifecycle — violet
  'student-lifecycle': {
    accent: '#6D28D9',
    tint: '#F3EEFF',
    ring: '#E4D8FD',
    gradient: 'linear-gradient(100deg, #6D28D9 0%, #5B21B6 50%, #4338CA 100%)',
    series: ['#7C3AED', '#F59E0B', '#0EA5E9'],
    bar: 'linear-gradient(90deg, #6D28D9, #8B5CF6)'
  },
  // B · Academics — royal blue
  academics: {
    accent: '#1D4ED8',
    tint: '#EEF4FF',
    ring: '#D6E4FF',
    gradient: 'linear-gradient(100deg, #1E40AF 0%, #1D4ED8 50%, #0E7490 100%)',
    series: ['#2563EB', '#F59E0B', '#14B8A6'],
    bar: 'linear-gradient(90deg, #1D4ED8, #3B82F6)'
  },
  // C · Sports — energetic orange-red
  sports: {
    accent: '#C2410C',
    tint: '#FFF3EC',
    ring: '#FEDDC8',
    gradient: 'linear-gradient(100deg, #C2410C 0%, #B91C1C 55%, #9D174D 100%)',
    series: ['#EA580C', '#0EA5E9', '#7C3AED'],
    bar: 'linear-gradient(90deg, #C2410C, #F97316)'
  },
  // D · Facilities — teal
  facilities: {
    accent: '#0F766E',
    tint: '#ECFAF8',
    ring: '#C9F0EA',
    gradient: 'linear-gradient(100deg, #0F766E 0%, #0E7490 55%, #1E40AF 100%)',
    series: ['#0D9488', '#F59E0B', '#6366F1'],
    bar: 'linear-gradient(90deg, #0F766E, #14B8A6)'
  },
  // E · Finance & Operations — emerald
  'finance-operations': {
    accent: '#047857',
    tint: '#ECFDF5',
    ring: '#C9F2DF',
    gradient: 'linear-gradient(100deg, #065F46 0%, #047857 50%, #0F766E 100%)',
    series: ['#059669', '#8B5CF6', '#F59E0B'],
    bar: 'linear-gradient(90deg, #047857, #10B981)'
  },
  // F · Campus Life — warm amber to rose
  'campus-life': {
    accent: '#B45309',
    tint: '#FFF8EB',
    ring: '#FCE7C3',
    gradient: 'linear-gradient(100deg, #B45309 0%, #C2410C 50%, #BE185D 100%)',
    series: ['#D97706', '#6366F1', '#0EA5E9'],
    bar: 'linear-gradient(90deg, #B45309, #F59E0B)'
  },
  // G · Governance — deep indigo
  governance: {
    accent: '#3730A3',
    tint: '#EEF0FF',
    ring: '#DADDFE',
    gradient: 'linear-gradient(100deg, #312E81 0%, #3730A3 50%, #4C1D95 100%)',
    series: ['#4F46E5', '#14B8A6', '#F59E0B'],
    bar: 'linear-gradient(90deg, #3730A3, #6366F1)'
  },
  // Global Support — sky
  support: {
    accent: '#0369A1',
    tint: '#EEF8FE',
    ring: '#CDEBFB',
    gradient: 'linear-gradient(100deg, #075985 0%, #0369A1 50%, #0E7490 100%)',
    series: ['#0284C7', '#F97316', '#8B5CF6'],
    bar: 'linear-gradient(90deg, #0369A1, #0EA5E9)'
  }
};

export const themeForSuite = (suiteId?: string): PageTheme => (suiteId && SUITE_THEMES[suiteId]) || BRAND_THEME;

export const themeForModule = (moduleId?: string): PageTheme => themeForSuite(moduleId ? findModule(moduleId)?.suiteId : undefined);
