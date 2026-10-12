import type { ComponentType } from "react";

export type NavIcon = ComponentType<{ className?: string }>;

/** A leaf in the sidebar: a page the viewer can open. */
export interface NavLeaf {
  id: string;
  label: string;
  href: string;
  icon?: NavIcon;
  /** Count shown on the right, e.g. pending approvals. */
  badge?: number;
  /** Not available to this organisation or not built yet; shown muted with a lock. */
  locked?: boolean;
}

/** A sidebar group that folds: a suite with its modules. */
export interface NavGroup {
  id: string;
  label: string;
  icon?: NavIcon;
  /** Accent for the icon, chevron and active marker; defaults to the brand accent. */
  color?: string;
  items: NavLeaf[];
}

export type NavEntry = NavLeaf | NavGroup;

export const isNavGroup = (e: NavEntry): e is NavGroup => "items" in e;

/** A labelled section of the sidebar, e.g. "Education OS" and "Administration". */
export interface NavSection {
  label?: string;
  entries: NavEntry[];
}

export interface Crumb {
  label: string;
  href?: string;
}

export interface SearchResult {
  label: string;
  hint?: string;
  href: string;
  /** Short tag such as NAV or MOD. */
  tag?: string;
}

export interface ShellUser {
  name: string;
  /** Second line under the name, e.g. the role. */
  role?: string;
  email?: string;
  /** Initials shown in the avatar when there is no photo. */
  initials?: string;
  photo?: string;
}

export interface ShellOrganisation {
  name: string;
  /** Academy type and plan, or the super admin scope. */
  detail?: string;
  /** True when a live API answers. */
  connected?: boolean;
}
