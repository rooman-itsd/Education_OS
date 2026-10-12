// Page theme scope: gives a page its suite colours through React context (for charts)
// and CSS variables (for Tailwind classes such as bg-[var(--accent-tint)]).

import React, { createContext, useContext } from 'react';
import { BRAND_THEME, type PageTheme } from '../../data/suiteThemes';

const ThemeContext = createContext<PageTheme>(BRAND_THEME);

export const usePageTheme = () => useContext(ThemeContext);

export const ThemeScope: React.FC<{ theme: PageTheme; children: React.ReactNode; className?: string }> = ({ theme, children, className }) => (
  <ThemeContext.Provider value={theme}>
    <div
      className={className}
      style={
        {
          '--accent': theme.accent,
          '--accent-tint': theme.tint,
          '--accent-ring': theme.ring,
          '--hero-gradient': theme.gradient,
          '--accent-bar': theme.bar
        } as React.CSSProperties
      }
    >
      {children}
    </div>
  </ThemeContext.Provider>
);
