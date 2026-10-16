import type { BadgeTone, PageTheme } from "@eos/ui-kit";
import { FEATURE_CATEGORIES } from "./features-data";

/**
 * Static content and shared types for the public website.
 *
 * Copy is sourced from modules/student-lifecycle/web-portal-cms/docs/features.md. Status flags keep
 * the site honest: nothing Specified/Planned is presented as a live feature (features.md §G, §I).
 * Pages (home, features, sign-up) fill in their own detailed content in later phases; Phase 1 keeps
 * only what the shared shell (header, footer, routing) needs.
 */

/** The three public routes, carried in the URL hash: `#/`, `#/features`, `#/signup`. */
export type PublicRoute = "home" | "features" | "signup";

/** Where "Sign in" hands off to — the role-dashboard app (apps/frontend index.html). */
export const APP_URL = "/";

/**
 * The app's own organisation sign-up (apps/frontend/src/auth/SignUp.tsx): the main app opens it when
 * it loads at `#signup` with nobody signed in. It creates the organisation and administrator account
 * and verifies the email; the public site only shows the plans and hands off to it.
 */
export const ORG_SIGNUP_URL = "/#signup";

/**
 * The public site's brand colours, from the Rooman logo (full palette and roles: the `.wpc` tokens at
 * the top of public.css). Primary is Rooman navy, the wordmark's navy moved off indigo to a true deep
 * blue so it stays distinct from the admin console's sidebar navy; series and bar add the logo's
 * "Empower" green and "Integrate" saffron. Solid colours only: no gradients.
 */
export const PUBLIC_THEME: PageTheme = {
  accent: "#1b3a7a",
  tint: "#e3e9f4",
  ring: "#d5ddec",
  gradient: "#0d1e44",
  series: ["#1b3a7a", "#2e7d32", "#f2941f"],
  bar: "#1b3a7a",
};

export const BRAND = {
  name: "Education OS",
  /** Owning organisation (per the team brief). */
  parent: "Rooman",
  tagline: "The operating system for modern institutions.",
  intro:
    "One configurable, multi-tenant platform for colleges and academies — from admissions to alumni, " +
    "studios to stadiums.",
} as const;

export interface NavItem {
  route: PublicRoute;
  label: string;
  href: string;
}

export const NAV: NavItem[] = [
  { route: "home", label: "Home", href: "#/" },
  { route: "features", label: "Features", href: "#/features" },
];

export interface FooterLink {
  label: string;
  /** Either an in-site route or an external href (not both). */
  route?: PublicRoute;
  href?: string;
  /** Small ui-kit icon shown beside the label. */
  icon?: IconName;
}

export interface FooterColumn {
  heading: string;
  links: FooterLink[];
}

/**
 * Placeholder destination for footer links whose pages don't exist yet. Grep for FOOTER_TODO_HREF to
 * find them; replace it with the real URL (or a `route`) when the page ships. Links using it are kept
 * out of the rendered footer until then, so visitors never land on a dead link.
 */
export const FOOTER_TODO_HREF = "#TODO";

export const FOOTER: FooterColumn[] = [
  {
    heading: "Product",
    links: [
      { label: "Features", route: "features", icon: "LayoutGrid" },
      { label: "Get started", route: "signup", icon: "UserPlus" },
    ],
  },
  {
    heading: "Platform",
    links: [
      { label: "Sign in", href: APP_URL, icon: "KeyRound" },
      // Future Platform links — set the real URL, then they appear automatically:
      // { label: "Help centre", href: FOOTER_TODO_HREF, icon: "LifeBuoy" },
      // { label: "Contact", href: FOOTER_TODO_HREF, icon: "Mail" },
    ],
  },
];

/**
 * Implementation status, used to badge modules/features on the site so unbuilt capabilities are never
 * advertised as available. The five labels are exactly those in features.md §I.
 */
export type ImplStatus = "implemented" | "partial" | "specified" | "scaffold" | "planned";

export const STATUS_LABEL: Record<ImplStatus, string> = {
  implemented: "Implemented",
  partial: "Partially implemented",
  specified: "Specified",
  scaffold: "Scaffold",
  planned: "Planned",
};

/** One-line meaning of each status, shown in the Features-page legend. */
export const STATUS_HINT: Record<ImplStatus, string> = {
  implemented: "Working code on the platform today.",
  partial: "Some working code; not yet end to end.",
  specified: "Full contracts and a PRD; implementation pending.",
  scaffold: "Placeholder module; contracts not yet written.",
  planned: "On the roadmap; no module yet.",
};

/** Maps a status to a ui-kit Badge tone. */
export const STATUS_TONE: Record<ImplStatus, BadgeTone> = {
  implemented: "success",
  partial: "warning",
  specified: "accent",
  scaffold: "neutral",
  planned: "neutral",
};

/**
 * Icons used on the public pages, by their @eos/ui-kit name. Kept as a narrow union so a typo is a
 * type error and pages can render `Icons[name]` safely.
 */
export type IconName =
  | "Layers"
  | "GraduationCap"
  | "LayoutDashboard"
  | "ShieldCheck"
  | "BookOpen"
  | "Palette"
  | "Building2"
  | "CalendarCheck2"
  | "Wallet"
  | "Scale"
  | "LifeBuoy"
  | "Trophy"
  | "UserPlus"
  | "LayoutGrid"
  | "Mail"
  | "Clock"
  | "KeyRound"
  | "Users"
  | "ClipboardList"
  | "CalendarRange"
  | "TrendingUp";

export interface IconItem {
  icon: IconName;
  title: string;
  text: string;
}

export interface TickerItem {
  icon: IconName;
  label: string;
}

// ---- Home page content (sourced from docs/features.md; honest about what is live) ----

export const HOME_HERO = {
  eyebrow: "Education OS",
  title: "Run your whole institution on one platform.",
  subtitle:
    "Education OS unifies admissions, academics, examinations, finance, campus life, governance and " +
    "support — configured for the way your field teaches, trains and manages its students.",
  /** Short, factual trust points (features.md §A). */
  trust: ["Multi-tenant SaaS", "Free 30-day trial", "15 academy types"],
} as const;

export const HOME_BENEFITS: IconItem[] = [
  {
    icon: "Layers",
    title: "Configured for your field",
    text: "Fifteen academy types from one platform — your suites, roles and vocabulary, not a generic ERP.",
  },
  {
    icon: "GraduationCap",
    title: "One record, every stage",
    text: "A connected student lifecycle from application to alumni, linked by events — not spreadsheets.",
  },
  {
    icon: "LayoutDashboard",
    title: "Role-based dashboards",
    text: "Every person sees the widgets for their job, driven by configuration rather than custom builds.",
  },
  {
    icon: "ShieldCheck",
    title: "Secure by design",
    text: "Per-organisation isolation with row-level security, audit trails and governed activation.",
  },
];

/** The main product categories — one line each. Detail lives on the Features page. */
export const HOME_CATEGORIES: IconItem[] = [
  { icon: "GraduationCap", title: "Student Lifecycle", text: "Public site & sign-up, admissions, student records, enrolment." },
  { icon: "BookOpen", title: "Teaching & Learning", text: "Programmes, curriculum, LMS, examinations, timetable & attendance." },
  { icon: "Palette", title: "Practice & Experiential", text: "Portfolios, projects, selection, productions, field training, skills." },
  { icon: "Building2", title: "Campus Life", text: "Hostel, library, transport, placements and alumni." },
  { icon: "CalendarCheck2", title: "Facilities & Resources", text: "Booking, inventory & equipment, assets and maintenance." },
  { icon: "Wallet", title: "Finance & Operations", text: "Fees & payments, budgets & grants, procurement, HR & payroll, e-office." },
  { icon: "Scale", title: "Governance & Compliance", text: "Grievance, RTI, IQAC/accreditation and statutory reports." },
  { icon: "LifeBuoy", title: "Support", text: "Helpdesk, incidents, SLAs, knowledge base and vendor contracts." },
  { icon: "Trophy", title: "Specialized suites", text: "Field-specific solutions — sports first, with more fields by design." },
];

/**
 * Capability pills for the homepage's scrolling ticker — real product capabilities named in the module
 * catalogue (docs/features.md), used to give a sense of the platform's breadth. The ticker makes no
 * implementation-status claim; the Features page is where availability is shown.
 */
export const HOME_TICKER: TickerItem[] = [
  { icon: "UserPlus", label: "Admissions" },
  { icon: "Users", label: "Student Records" },
  { icon: "BookOpen", label: "Academic Management" },
  { icon: "CalendarCheck2", label: "Attendance" },
  { icon: "ClipboardList", label: "Assessments & Results" },
  { icon: "CalendarRange", label: "Timetable Management" },
  { icon: "Wallet", label: "Fee Management" },
  { icon: "LayoutDashboard", label: "Role-Based Dashboards" },
  { icon: "Building2", label: "Campus Operations" },
  { icon: "Scale", label: "Governance & Approvals" },
  { icon: "GraduationCap", label: "Student Lifecycle" },
  { icon: "TrendingUp", label: "Analytics & Reports" },
];

export interface ShowcaseItem extends IconItem {
  /** A one-line framing for the suite — each suite's own `summary` in the Features-page catalogue. */
  headline: string;
}

/**
 * Suite-level cards for the homepage's product showcase. Built from HOME_CATEGORIES (icon, title, short
 * module list) plus, for the longer headline, each suite's `summary` from features-data.ts — both lists
 * are kept in the same nine-suite order as docs/features.md, so this reuses existing, already-approved
 * copy rather than inventing new marketing text.
 */
export const HOME_SHOWCASE: ShowcaseItem[] = HOME_CATEGORIES.map((item, i) => ({
  ...item,
  headline: FEATURE_CATEGORIES[i]?.summary ?? item.text,
}));

export const HOME_ADAPT = {
  eyebrow: "One platform, many fields",
  title: "Configured for the way your field works",
  lead:
    "Every institution runs the common platform. Field needs are met by eight reusable patterns — " +
    "resource booking, portfolios, selection, productions, projects, field training, skill progress and " +
    "specialized inventory — named in your field's own vocabulary. Only genuinely field-specific " +
    "behaviour becomes a specialized module.",
  /** Academy types defined as profiles (features.md §F). Sports is the first specialized suite. */
  academies: [
    "Sports",
    "Arts",
    "Design & fashion",
    "Music",
    "Dance",
    "Theatre",
    "Film & media",
    "Medical",
    "Law",
    "Engineering",
    "Management",
    "Agriculture",
    "Hospitality",
    "Teacher education",
    "Research",
  ],
  note:
    "Whatever your discipline, Education OS shapes itself around the way your institution teaches, " +
    "assesses and grows — configured for you, not the other way round.",
} as const;

export const HOME_ONBOARDING: IconItem[] = [
  { icon: "UserPlus", title: "Register", text: "Create your organisation and admin account, and choose your academy type." },
  { icon: "Mail", title: "Verify email", text: "Confirm your email address to move into the approval queue." },
  { icon: "Clock", title: "Await approval", text: "A platform administrator approves your academic package." },
  { icon: "KeyRound", title: "Sign in", text: "Once approved, sign in and land on your organisation's dashboard." },
];

export const HOME_ONBOARDING_NOTE = "Every organisation starts on a free 30-day trial.";
