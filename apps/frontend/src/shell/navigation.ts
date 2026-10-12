import type { NavIcon, NavSection, SearchResult } from "@eos/ui-kit";
import { Icons } from "@eos/ui-kit";
import type { AcademyProfile, Entitlement } from "../tenant/entitlements";

/** Suite labels, icons and accents, in catalogue order (docs/architecture/ARCHITECTURE.md). */
export const SUITES: { id: string; label: string; icon: NavIcon; color: string }[] = [
  { id: "student-lifecycle", label: "A · Student Lifecycle", icon: Icons.GraduationCap, color: "#60a5fa" },
  { id: "academics", label: "B · Academics", icon: Icons.BookOpen, color: "#a78bfa" },
  { id: "practice", label: "Practice", icon: Icons.Presentation, color: "#2dd4bf" },
  { id: "sports", label: "C · Sports", icon: Icons.Trophy, color: "#34d399" },
  { id: "facilities", label: "D · Facilities", icon: Icons.Building2, color: "#fbbf24" },
  { id: "finance-operations", label: "E · Finance & Operations", icon: Icons.Wallet, color: "#5eead4" },
  { id: "campus-life", label: "F · Campus Life", icon: Icons.Home, color: "#f472b6" },
  { id: "governance", label: "G · Governance", icon: Icons.Scale, color: "#e879f9" },
  { id: "support", label: "Global Support", icon: Icons.LifeBuoy, color: "#cbd5e1" },
];

/** Short names for module ids; anything missing falls back to the id in title case. */
const MODULE_LABELS: Record<string, string> = {
  admissions: "Admissions",
  "student-information": "Students",
  "enrolment-registration": "Enrolment & Registration",
  "web-portal-cms": "Web Portal & CMS",
  "academic-management": "Academic Management",
  lms: "Learning (LMS)",
  examinations: "Examinations",
  "timetable-attendance": "Timetable & Attendance",
  portfolio: "Portfolio",
  projects: "Projects",
  "selection-process": "Selection Process",
  productions: "Productions",
  "field-training": "Field Training",
  "skill-progress": "Skill Progress",
  "athlete-performance": "Athletes",
  "training-video-analysis": "Training & Video",
  "sports-nutrition-health": "Nutrition & Health",
  "tournament-events": "Tournaments",
  "sports-facilities": "Sports Facilities",
  "facility-booking": "Bookings",
  "inventory-equipment": "Inventory",
  "asset-management": "Assets",
  maintenance: "Maintenance",
  "fees-accounts": "Fees & Payments",
  "budget-grants": "Budget & Grants",
  procurement: "Procurement",
  "hr-payroll": "HR & Payroll",
  "e-office": "E-Office",
  hostel: "Hostel",
  transport: "Transport",
  library: "Library",
  "placement-career": "Placement & Career",
  alumni: "Alumni",
  grievance: "Grievance",
  rti: "RTI",
  "iqac-accreditation": "IQAC / Accreditation",
  "regulatory-reports": "Compliance & Reports",
  helpdesk: "Helpdesk",
  "sla-management": "SLA Management",
  "knowledge-base": "Knowledge Base",
  "incident-management": "Incidents",
  "amc-vendor-support": "AMC & Vendors",
};

export const moduleLabel = (id: string) => MODULE_LABELS[id] ?? id.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

/** Where a module's page lives in the role app. Pages come as modules ship their frontends. */
export const moduleHref = (domain: string, id: string) => `#/modules/${domain}/${id}`;

/**
 * The sidebar for a role: the dashboard, then one group per suite in the academy profile with
 * the profile's modules, marking the ones outside the plan as locked.
 */
export function buildSections(profile: AcademyProfile | undefined, entitlement: Entitlement | undefined): NavSection[] {
  const top: NavSection = { entries: [{ id: "dashboard", label: "Dashboard", href: "#/", icon: Icons.LayoutDashboard }] };
  if (!profile) return [top];
  const byDomain = new Map<string, string[]>();
  for (const path of profile.modules) {
    const [domain, id] = path.split("/");
    if (!domain || !id) continue;
    byDomain.set(domain, [...(byDomain.get(domain) ?? []), id]);
  }
  const groups = SUITES.filter((s) => byDomain.has(s.id)).map((s) => ({
    id: s.id,
    label: s.label,
    icon: s.icon,
    color: s.color,
    items: (byDomain.get(s.id) ?? []).map((id) => ({
      id,
      label: moduleLabel(id),
      href: moduleHref(s.id, id),
      locked: entitlement ? !entitlement.modules.has(`${s.id}/${id}`) : false,
    })),
  }));
  return [top, { label: "Education OS", entries: groups }];
}

/** Search results for the top bar: the dashboard and every module in the profile. */
export function buildSearch(profile: AcademyProfile | undefined): SearchResult[] {
  const results: SearchResult[] = [{ label: "Dashboard", hint: "home overview", href: "#/", tag: "NAV" }];
  for (const path of profile?.modules ?? []) {
    const [domain, id] = path.split("/");
    if (domain && id) results.push({ label: moduleLabel(id), hint: id, href: moduleHref(domain, id), tag: "MOD" });
  }
  return results;
}
