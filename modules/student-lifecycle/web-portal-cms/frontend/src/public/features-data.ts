/**
 * The Features-page catalogue, compiled from modules/student-lifecycle/web-portal-cms/docs/features.md
 * (sections B, C and F). Every status is taken from that document's evidence-based classification — so
 * nothing Specified/Scaffold/Planned is ever presented as live. Keep this in sync with features.md if
 * that document changes; it is the source of truth.
 */

import type { IconName, ImplStatus } from "./content";

export interface FeatureModule {
  name: string;
  description: string;
  /** Representative roles, kept short. */
  roles: string[];
  status: ImplStatus;
}

export interface FeatureCategory {
  /** Stable id for in-page anchor navigation. */
  id: string;
  icon: IconName;
  title: string;
  /** One-line framing for the category. */
  summary: string;
  modules: FeatureModule[];
}

export const FEATURE_CATEGORIES: FeatureCategory[] = [
  {
    id: "student-lifecycle",
    icon: "GraduationCap",
    title: "Student Lifecycle",
    summary: "The journey from first visit to enrolled student — and the public front door.",
    modules: [
      {
        name: "Web Portal & CMS",
        description: "Public website, CMS pages, announcements, and the public organisation sign-up page.",
        roles: ["Visitor", "CMS editor", "Org admin"],
        status: "specified",
      },
      {
        name: "Admissions",
        description: "Application intake, screening, offers and acceptance. Applications are anonymous.",
        roles: ["Applicant", "Admissions staff"],
        status: "specified",
      },
      {
        name: "Student Information",
        description: "The Person system of record — canonical student and people records used across modules.",
        roles: ["Records staff"],
        status: "specified",
      },
      {
        name: "Enrolment & Registration",
        description: "Enrolling admitted applicants and registering them into programmes and courses each term.",
        roles: ["Registrar", "Student"],
        status: "specified",
      },
    ],
  },
  {
    id: "academics",
    icon: "BookOpen",
    title: "Teaching & Learning",
    summary: "Programmes and curriculum, learning, assessment and attendance.",
    modules: [
      {
        name: "Academic Management",
        description: "Terms, programmes, curriculum versions, course catalogue, offerings and faculty assignments.",
        roles: ["Admin", "Department head", "Faculty"],
        status: "specified",
      },
      {
        name: "LMS",
        description: "Course spaces, materials, assignments, quizzes, discussions and grading.",
        roles: ["Instructor", "Student"],
        status: "specified",
      },
      {
        name: "Examinations",
        description: "Exam cycles and sessions, eligibility, hall tickets, invigilation, results and transcripts.",
        roles: ["Controller", "Faculty", "Student"],
        status: "specified",
      },
      {
        name: "Timetable & Attendance",
        description: "Timetable generation, scheduled classes, attendance capture and exam-eligibility.",
        roles: ["Admin", "Faculty", "Student"],
        status: "specified",
      },
    ],
  },
  {
    id: "practice",
    icon: "Palette",
    title: "Practice & Portfolios",
    summary: "The cross-field suite every academy gets, named in your field's vocabulary.",
    modules: [
      {
        name: "Portfolio",
        description: "Learner portfolios — artworks, repertoire, showreels, designs, teaching and research portfolios.",
        roles: ["Learner", "Reviewer", "Manager"],
        status: "specified",
      },
      {
        name: "Selection Process",
        description: "Auditions, casting, squad selection, jury rounds and supervisor allocation.",
        roles: ["Panelist", "Coordinator"],
        status: "specified",
      },
      {
        name: "Projects",
        description: "Projects with milestones, teams and reviews — capstone, film, research, artwork.",
        roles: ["Coordinator", "Guide", "Member"],
        status: "specified",
      },
      {
        name: "Field Training",
        description: "Placements — clinical rotations, teaching practice, internships, court visits.",
        roles: ["Coordinator", "Supervisor", "Trainee"],
        status: "specified",
      },
      {
        name: "Skill Progress",
        description: "Skill frameworks, rubrics, assessments and progression over time.",
        roles: ["Evaluator"],
        status: "specified",
      },
      {
        name: "Productions",
        description: "Performances, exhibitions, recitals, screenings, hackathons and competitions.",
        roles: [],
        status: "scaffold",
      },
    ],
  },
  {
    id: "campus-life",
    icon: "Building2",
    title: "Campus Life",
    summary: "Residential and student services beyond the classroom.",
    modules: [
      {
        name: "Hostel",
        description: "Room allocation, mess, visitors, discipline, gate pass and fee linkage.",
        roles: ["Warden", "Security", "Resident"],
        status: "specified",
      },
      {
        name: "Library",
        description: "Catalogue, circulation, digital library, fines and reservations.",
        roles: ["Librarian", "Member"],
        status: "specified",
      },
      {
        name: "Transport",
        description: "Routes, vehicles, passes, driver management and trip tracking.",
        roles: ["Driver", "Rider"],
        status: "specified",
      },
      {
        name: "Placement & Career",
        description: "Placement drives, companies, applications, offers and career services.",
        roles: [],
        status: "scaffold",
      },
      {
        name: "Alumni",
        description: "Alumni directory, events, donations and engagement campaigns.",
        roles: [],
        status: "scaffold",
      },
    ],
  },
  {
    id: "facilities",
    icon: "CalendarCheck2",
    title: "Facilities & Resources",
    summary: "Bookable spaces, inventory, assets and maintenance.",
    modules: [
      {
        name: "Facility Booking",
        description: "Generic resource booking — resources, availability, bookings with optional approval, check-in.",
        roles: ["User", "Approver", "Manager"],
        status: "partial",
      },
      {
        name: "Inventory & Equipment",
        description: "Generic inventory — catalogue, units, store locations, stock ledger and loans.",
        roles: ["Borrower", "Approver", "Manager"],
        status: "specified",
      },
      {
        name: "Asset Management",
        description: "Fixed-asset register — tagging, transfers, verification, depreciation and disposal.",
        roles: ["Custodian", "Verifier", "Finance"],
        status: "specified",
      },
      {
        name: "Maintenance",
        description: "Fault tickets and work orders, technician and vendor assignment, SLA and preventive schedules.",
        roles: ["Reporter", "Technician", "Manager"],
        status: "specified",
      },
      {
        name: "Sports Facilities",
        description: "Registry of grounds, courts, pools and gyms, and their usage (sports).",
        roles: ["Admin", "Staff", "Coach"],
        status: "specified",
      },
    ],
  },
  {
    id: "finance-operations",
    icon: "Wallet",
    title: "Finance & Operations",
    summary: "Money, people and administration.",
    modules: [
      {
        name: "Fees & Accounts",
        description: "Fee structures, invoices, online payments, receipts, ledgers, concessions and refunds.",
        roles: ["Student", "Finance staff", "Management"],
        status: "specified",
      },
      {
        name: "Budget & Grants",
        description: "Budget planning, grant tracking and utilisation certificates.",
        roles: ["Finance staff", "Research office"],
        status: "specified",
      },
      {
        name: "Procurement",
        description: "Indents, tenders, purchase orders, goods receipt and vendor management.",
        roles: ["Finance", "Management"],
        status: "specified",
      },
      {
        name: "HR & Payroll",
        description: "Employee master, leave, payroll runs, appraisals and service records.",
        roles: ["HR staff", "Management"],
        status: "specified",
      },
      {
        name: "e-Office",
        description: "File movement, notings, approvals and digital correspondence.",
        roles: ["All staff"],
        status: "specified",
      },
    ],
  },
  {
    id: "governance",
    icon: "Scale",
    title: "Governance & Compliance",
    summary: "Statutory, regulatory and grievance processes.",
    modules: [
      {
        name: "Grievance",
        description: "SGRC, anti-ragging and POSH/ICC complaint intake and resolution.",
        roles: ["Complainant", "Committee member", "Coordinator"],
        status: "specified",
      },
      {
        name: "RTI",
        description: "RTI request intake, assignment, tracking and responses.",
        roles: ["Officer", "Custodian", "Appellate authority"],
        status: "specified",
      },
      {
        name: "IQAC & Accreditation",
        description: "IQAC data collection, NAAC/NBA metrics and an evidence repository.",
        roles: ["Coordinator", "Contributor"],
        status: "specified",
      },
      {
        name: "Regulatory Reports",
        description: "UGC, AISHE, NIRF and other statutory reporting.",
        roles: ["Coordinator", "Preparer"],
        status: "specified",
      },
    ],
  },
  {
    id: "support",
    icon: "LifeBuoy",
    title: "Support & Service Management",
    summary: "An ITSM-style cluster for running the institution's own services.",
    modules: [
      {
        name: "Helpdesk",
        description: "Ticketing with categories and routing for every role.",
        roles: ["Requester", "Agent", "Lead"],
        status: "specified",
      },
      {
        name: "Incident Management",
        description: "Incident and problem records with root-cause analysis.",
        roles: ["Responder", "Problem manager"],
        status: "specified",
      },
      {
        name: "SLA Management",
        description: "SLA definitions, timers, escalation and breach tracking.",
        roles: ["Admin"],
        status: "specified",
      },
      {
        name: "Knowledge Base",
        description: "Articles, FAQs and how-to guides for self-service.",
        roles: ["Reader", "Author", "Editor"],
        status: "specified",
      },
      {
        name: "AMC & Vendor Support",
        description: "AMC contracts, vendor-support engagements and renewals.",
        roles: ["Coordinator", "Contract manager"],
        status: "specified",
      },
    ],
  },
  {
    id: "sports",
    icon: "Trophy",
    title: "Specialized: Sports",
    summary: "The first field suite — the template for other specialized fields.",
    modules: [
      {
        name: "Athlete Performance",
        description: "Athlete profiles, performance metrics, fitness testing, benchmarks and medical clearance.",
        roles: ["Athlete", "Coach", "Medical staff"],
        status: "specified",
      },
      {
        name: "Training & Video Analysis",
        description: "Training plans and sessions, video upload, tagging and annotation.",
        roles: ["Coach", "Athlete"],
        status: "specified",
      },
      {
        name: "Sports Nutrition & Health",
        description: "Diet plans, medical records, injury tracking and physio sessions.",
        roles: ["Nutritionist", "Medical staff", "Athlete"],
        status: "specified",
      },
      {
        name: "Tournament & Events",
        description: "Tournaments, fixtures, results, officials and event logistics.",
        roles: ["Admin", "Official"],
        status: "specified",
      },
    ],
  },
  {
    id: "platform",
    icon: "ShieldCheck",
    title: "Platform & Shared Services",
    summary: "The core every deployment runs. This is where most of today's working code lives.",
    modules: [
      {
        name: "Organisation & Tenancy",
        description: "Self-service registration, academy type, verification, approval lifecycle, entitlements and overrides.",
        roles: ["Super admin", "Org admin"],
        status: "implemented",
      },
      {
        name: "Billing & Plans",
        description: "Plan catalogue, subscriptions, trial start, upgrade, cancel, payment webhook and trial expiry.",
        roles: ["Org admin", "Super admin"],
        status: "implemented",
      },
      {
        name: "Identity & Access",
        description: "Password login, JWT and role-based permissions, with login gated on an active organisation. SSO and MFA are designed, not yet built.",
        roles: ["All roles"],
        status: "partial",
      },
      {
        name: "Dashboards & Widgets",
        description: "One dashboard page renders any role's layout from configuration; each module supplies its own widgets.",
        roles: ["All roles"],
        status: "partial",
      },
      {
        name: "Entitlements",
        description: "Effective access = academy profile ∩ plan ∪ overrides, enforced on every request.",
        roles: ["Super admin"],
        status: "implemented",
      },
      {
        name: "Payments (SBIePay)",
        description: "SBIePay gateway adapter — initiate, callback, reconcile and refunds.",
        roles: ["Finance"],
        status: "implemented",
      },
      {
        name: "Notifications",
        description: "Email, SMS, WhatsApp, push and in-app messaging with templates. Email delivery is stubbed today.",
        roles: ["All roles"],
        status: "specified",
      },
      {
        name: "Audit, Workflow, Documents, Search, Reporting, Scheduler, Gateway, Event bus",
        description: "The remaining shared platform services — contracts defined, implementation mostly pending.",
        roles: ["Platform"],
        status: "specified",
      },
    ],
  },
];
