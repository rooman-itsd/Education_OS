import type { BadgeTone, PageTheme } from "@eos/ui-kit";

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

/** Where "Sign in" hands off to — the role-dashboard app, served at /app (apps/frontend/src/main.tsx). */
export const APP_URL = "/app";

/**
 * The app's own organisation sign-up (apps/frontend/src/auth/SignUp.tsx): the main app opens it when
 * it loads at `#signup` with nobody signed in. It creates the organisation and administrator account
 * and verifies the email; the public site only shows the plans and hands off to it.
 */
export const ORG_SIGNUP_URL = "/app#signup";

/**
 * The public site's palette: warm cream canvas, the admin sidebar's navy (#2a254e) as ink, and one
 * chromatic accent taken from the logo's own "OS" orange for primary actions and highlights. The accent
 * token here is the deeper orange (#c2410c) so text, badges and white-on-orange buttons pass AA; the
 * bright logo orange is used only for marks and highlights in public.css.
 */
export const PUBLIC_THEME: PageTheme = {
  accent: "#c2410c",
  tint: "#fde4d3",
  ring: "#f6c3a1",
  gradient: "#c2410c",
  series: ["#c2410c", "#2a254e", "#1f9d5c"],
  bar: "#c2410c",
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
 * Placeholder destination for footer links whose real URL is not decided yet (company pages, help,
 * legal, contact, social profiles). They render as links so the footer is complete, but clicking one
 * does nothing. Grep for FOOTER_TODO_HREF and replace each with its real URL before launch.
 */
export const FOOTER_TODO_HREF = "#";

/** Footer link columns, the minimum set a SaaS footer carries: product, company, contact. */
export const FOOTER: FooterColumn[] = [
  {
    heading: "Product",
    links: [
      { label: "Features", route: "features" },
      { label: "Plans & pricing", route: "signup" },
      { label: "Start free trial", route: "signup" },
      { label: "Sign in", href: APP_URL },
    ],
  },
  {
    heading: "Company",
    links: [
      { label: "About us", href: FOOTER_TODO_HREF },
      { label: "Careers", href: FOOTER_TODO_HREF },
      { label: "News", href: FOOTER_TODO_HREF },
      { label: "Partners", href: FOOTER_TODO_HREF },
    ],
  },
  {
    heading: "Contact",
    links: [
      { label: "Contact sales", href: FOOTER_TODO_HREF, icon: "Mail" },
      { label: "Email support", href: FOOTER_TODO_HREF, icon: "LifeBuoy" },
      { label: "Call us", href: FOOTER_TODO_HREF, icon: "Phone" },
      { label: "Find our office", href: FOOTER_TODO_HREF, icon: "MapPin" },
    ],
  },
];

/** Legal links on the footer's bottom line. */
export const FOOTER_LEGAL: FooterLink[] = [
  { label: "Privacy policy", href: FOOTER_TODO_HREF },
  { label: "Terms of service", href: FOOTER_TODO_HREF },
  { label: "Cookie policy", href: FOOTER_TODO_HREF },
  { label: "Accessibility", href: FOOTER_TODO_HREF },
];

/** Social profiles shown as marks in the footer (components/SocialIcons.tsx draws them). */
export const FOOTER_SOCIAL: { network: "linkedin" | "x" | "instagram" | "youtube" | "facebook"; label: string; href: string }[] = [
  { network: "linkedin", label: "LinkedIn", href: FOOTER_TODO_HREF },
  { network: "x", label: "X (Twitter)", href: FOOTER_TODO_HREF },
  { network: "instagram", label: "Instagram", href: FOOTER_TODO_HREF },
  { network: "youtube", label: "YouTube", href: FOOTER_TODO_HREF },
  { network: "facebook", label: "Facebook", href: FOOTER_TODO_HREF },
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
  partial: "info",
  specified: "accent",
  scaffold: "warning",
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
  | "Phone"
  | "MapPin"
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

// ---- Home page content (sourced from docs/features.md; honest about what is live) ----

export const HOME_HERO = {
  /** The stacked name on the first screen: two lines, two inks. */
  name: ["Education", "OS"],
  statement: "Run your whole institution on one platform.",
  subtitle:
    "Education OS unifies admissions, academics, examinations, finance, campus life, governance and " +
    "support — configured for the way your field teaches, trains and manages its students.",
} as const;

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

/**
 * The four onboarding stages written as clauses for the home page's stepped sequence (the order is in
 * the words, not in numbers). The detail sentence under each is HOME_ONBOARDING's own text.
 */
export const HOME_ONBOARDING_LINES = [
  "First, register your institution.",
  "Then confirm your email.",
  "We review and approve it.",
  "Then you sign in.",
] as const;

export const HOME_ONBOARDING_NOTE = "Every organisation starts on a free 30-day trial.";

/**
 * Each academy type's own words for the shared field patterns, copied from the institution profiles in
 * platform/identity/config/profiles/*.yaml (their `title` and `vocabulary` keys). `generic` is the
 * pattern's platform-wide name; `word` is what that field calls it. Keep in sync with the profiles.
 */
export interface FieldTerm {
  generic: string;
  word: string;
}

export interface FieldVocabulary {
  id: string;
  /** Short name for the picker. */
  label: string;
  /** The profile's title. */
  title: string;
  terms: FieldTerm[];
}

export const FIELD_VOCAB: FieldVocabulary[] = [
  {
    id: "music-academy",
    label: "Music",
    title: "Music Academy / Conservatory",
    terms: [
      { generic: "Selection", word: "Audition" },
      { generic: "Production", word: "Recital / concert" },
      { generic: "Portfolio item", word: "Repertoire piece" },
      { generic: "Resource", word: "Practice room" },
      { generic: "Inventory item", word: "Instrument" },
      { generic: "Skill assessment", word: "Grade exam" },
    ],
  },
  {
    id: "sports-college",
    label: "Sports",
    title: "Sports University / Sports College",
    terms: [
      { generic: "Event", word: "Tournament" },
      { generic: "Resource", word: "Facility" },
      { generic: "Inventory item", word: "Equipment" },
    ],
  },
  {
    id: "arts-academy",
    label: "Arts",
    title: "Arts Academy / Fine Arts College",
    terms: [
      { generic: "Production", word: "Exhibition" },
      { generic: "Portfolio item", word: "Artwork" },
      { generic: "Selection", word: "Critique / jury" },
      { generic: "Project", word: "Artwork project" },
      { generic: "Resource", word: "Studio" },
      { generic: "Inventory item", word: "Material" },
    ],
  },
  {
    id: "design-fashion-institute",
    label: "Design & fashion",
    title: "Design / Fashion Institute",
    terms: [
      { generic: "Production", word: "Show" },
      { generic: "Portfolio item", word: "Collection" },
      { generic: "Selection", word: "Critique" },
      { generic: "Project", word: "Collection / industry project" },
      { generic: "Resource", word: "Studio" },
      { generic: "Placement", word: "Internship" },
    ],
  },
  {
    id: "dance-academy",
    label: "Dance",
    title: "Dance / Performing Arts Academy",
    terms: [
      { generic: "Production", word: "Performance" },
      { generic: "Selection", word: "Audition" },
      { generic: "Resource", word: "Practice studio" },
      { generic: "Inventory item", word: "Costume / prop" },
      { generic: "Skill assessment", word: "Technique assessment" },
    ],
  },
  {
    id: "theatre-academy",
    label: "Theatre",
    title: "Theatre / Drama Academy",
    terms: [
      { generic: "Selection", word: "Casting call" },
      { generic: "Production", word: "Production" },
      { generic: "Project", word: "Script" },
      { generic: "Resource", word: "Rehearsal space / venue" },
      { generic: "Inventory item", word: "Costume / prop" },
    ],
  },
  {
    id: "film-media-institute",
    label: "Film & media",
    title: "Film / Media / Animation Institute",
    terms: [
      { generic: "Portfolio item", word: "Showreel" },
      { generic: "Production", word: "Screening / festival" },
      { generic: "Project", word: "Film project" },
      { generic: "Resource", word: "Edit suite / studio" },
      { generic: "Inventory item", word: "Equipment" },
    ],
  },
  {
    id: "medical-college",
    label: "Medical",
    title: "Medical / Health Sciences College",
    terms: [
      { generic: "Placement", word: "Clinical rotation" },
      { generic: "Skill assessment", word: "Skills assessment" },
      { generic: "Resource", word: "Lab / skills room" },
      { generic: "Project", word: "Research project" },
    ],
  },
  {
    id: "law-college",
    label: "Law",
    title: "Law College / Law University",
    terms: [
      { generic: "Selection", word: "Moot court selection" },
      { generic: "Production", word: "Competition / debate" },
      { generic: "Placement", word: "Legal internship / clinic" },
      { generic: "Project", word: "Case research" },
    ],
  },
  {
    id: "engineering-college",
    label: "Engineering",
    title: "Engineering / Technology College",
    terms: [
      { generic: "Project", word: "Capstone / project" },
      { generic: "Resource", word: "Laboratory" },
      { generic: "Production", word: "Hackathon / tech event" },
      { generic: "Placement", word: "Industrial training" },
      { generic: "Inventory item", word: "Lab equipment" },
    ],
  },
  {
    id: "management-institute",
    label: "Management",
    title: "Management / Business School",
    terms: [
      { generic: "Project", word: "Live project" },
      { generic: "Production", word: "Case competition / industry event" },
      { generic: "Placement", word: "Internship" },
      { generic: "Selection", word: "Competition selection" },
    ],
  },
  {
    id: "agriculture-college",
    label: "Agriculture",
    title: "Agriculture / Veterinary / Field Sciences",
    terms: [
      { generic: "Placement", word: "Farm / practical rotation" },
      { generic: "Project", word: "Research trial" },
      { generic: "Resource", word: "Farm plot / lab" },
      { generic: "Production", word: "Extension activity" },
    ],
  },
  {
    id: "hospitality-institute",
    label: "Hospitality",
    title: "Hospitality / Hotel Management",
    terms: [
      { generic: "Placement", word: "Industry internship" },
      { generic: "Resource", word: "Training kitchen / lab" },
      { generic: "Production", word: "Banquet / event" },
      { generic: "Skill assessment", word: "Practical assessment" },
    ],
  },
  {
    id: "teacher-education-college",
    label: "Teacher education",
    title: "Teacher Education / B.Ed.",
    terms: [
      { generic: "Placement", word: "School internship" },
      { generic: "Project", word: "Lesson plan" },
      { generic: "Portfolio item", word: "Teaching portfolio" },
      { generic: "Skill assessment", word: "Practicum assessment" },
    ],
  },
  {
    id: "research-university",
    label: "Research",
    title: "Research / Doctoral University",
    terms: [
      { generic: "Project", word: "Research project" },
      { generic: "Portfolio item", word: "Publication" },
      { generic: "Production", word: "Conference" },
      { generic: "Selection", word: "Supervisor allocation / viva" },
      { generic: "Project milestone", word: "Thesis milestone" },
    ],
  },
];
