// The module catalogue: modules/<domain>/<module>, platform/<service> and integrations/<adapter>.
// Suites and their order follow docs/architecture/ARCHITECTURE.md ("Domain grouping of feature
// modules"). Display names are the admin's labels; description, status and tier come from each
// module's own module.yaml (see ./repo.ts), so they always match the repository.

import { MANIFESTS } from './repo';

export type ModuleKind = 'feature' | 'platform' | 'integration';
export type ModuleStatus = 'planned' | 'in-progress' | 'stable' | 'deprecated';

export interface ModuleInfo {
  id: string;
  name: string;
  description: string;
  kind: ModuleKind;
  /** Suite id for feature modules, 'platform' or 'integrations' otherwise. */
  suiteId: string;
  /** `status:` in module.yaml. */
  status: ModuleStatus;
  /** `tier:` in module.yaml: core, common or specialized. */
  tier: string;
  /** `field:` in module.yaml for specialized modules. */
  field?: string;
  /** Backend code exists (ARCHITECTURE.md, "What is built"). */
  implemented: boolean;
  /** The admin screen for this module, when the admin has one. */
  route?: string;
}

export interface Suite {
  id: string;
  /** Diagram suite letter (A–G), '' for suites the diagram does not letter. */
  letter: string;
  /** How ARCHITECTURE.md labels the suite: "Suite A", "Global", or none for new suites. */
  diagram?: string;
  name: string;
  /** Domain folder under modules/. */
  domain: string;
  color: string;
  modules: ModuleInfo[];
}

/** Backends that exist today (ARCHITECTURE.md, "What is built"). Every feature module is "Not yet". */
const IMPLEMENTED = new Set(['identity', 'tenancy', 'billing']);

function info(id: string, name: string, kind: ModuleKind, suiteId: string, route?: string): ModuleInfo {
  const m = MANIFESTS[id];
  return {
    id,
    name,
    kind,
    suiteId,
    description: m?.description ?? '',
    status: (m?.status as ModuleStatus | undefined) ?? 'planned',
    tier: m?.tier ?? '',
    field: m?.field,
    implemented: IMPLEMENTED.has(id),
    route
  };
}

const feature = (suiteId: string, id: string, name: string, route?: string) => info(id, name, 'feature', suiteId, route);

const suite = (id: string, letter: string, diagram: string | undefined, name: string, modules: [string, string, string?][]): Suite => ({
  id,
  letter,
  diagram,
  name,
  domain: id,
  color: '#7E22CE',
  modules: modules.map(([mid, mname, route]) => feature(id, mid, mname, route))
});

export const SUITES: Suite[] = [
  suite('student-lifecycle', 'A', 'Suite A', 'Pre-Admission & Student Information', [
    ['web-portal-cms', 'Web Portal & CMS'],
    ['admissions', 'Admission & Application', '/admissions'],
    ['student-information', 'Student Information (SIS)'],
    ['enrolment-registration', 'Enrolment & Registration']
  ]),
  suite('academics', 'B', 'Suite B', 'Academic & Learning Management', [
    ['academic-management', 'Academic Management'],
    ['lms', 'Learning Management (LMS)'],
    ['examinations', 'Examination Management'],
    ['timetable-attendance', 'Timetable & Attendance']
  ]),
  suite('practice', '', undefined, 'Practice', [
    ['portfolio', 'Portfolio'],
    ['projects', 'Projects'],
    ['selection-process', 'Selection Process'],
    ['productions', 'Productions'],
    ['field-training', 'Field Training'],
    ['skill-progress', 'Skill Progress']
  ]),
  suite('sports', 'C', 'Suite C', 'Sports & Athlete Performance', [
    ['athlete-performance', 'Athlete Performance'],
    ['training-video-analysis', 'Training & Video Analysis'],
    ['sports-nutrition-health', 'Sports Nutrition & Health'],
    ['tournament-events', 'Tournament & Events']
  ]),
  suite('facilities', 'D', 'Suite D', 'Facility & Resource Management', [
    ['sports-facilities', 'Sports Facilities'],
    ['facility-booking', 'Facility Booking'],
    ['inventory-equipment', 'Inventory & Equipment'],
    ['asset-management', 'Asset Management'],
    ['maintenance', 'Maintenance']
  ]),
  suite('finance-operations', 'E', 'Suite E', 'Finance & Institutional Operations', [
    ['fees-accounts', 'Fees & Accounts'],
    ['budget-grants', 'Budget & Grants'],
    ['procurement', 'Procurement'],
    ['hr-payroll', 'HR & Payroll'],
    ['e-office', 'E-Office & Files']
  ]),
  suite('campus-life', 'F', 'Suite F', 'Campus Life & Student Services', [
    ['hostel', 'Hostel Management'],
    ['transport', 'Transport Management'],
    ['library', 'Library Management'],
    ['placement-career', 'Placement & Career'],
    ['alumni', 'Alumni Management']
  ]),
  suite('governance', 'G', 'Suite G', 'Governance, Grievance & Compliance', [
    ['grievance', 'Grievance (SGRC / POSH)'],
    ['rti', 'RTI Management'],
    ['iqac-accreditation', 'IQAC / Accreditation'],
    ['regulatory-reports', 'Regulatory Reports']
  ]),
  suite('support', '•', 'Global', 'Global Support Systems', [
    ['helpdesk', 'Helpdesk & Ticketing'],
    ['sla-management', 'SLA Management'],
    ['knowledge-base', 'Knowledge Base'],
    ['incident-management', 'Incident & Problem'],
    ['amc-vendor-support', 'User Support & AMC']
  ])
];

/** "Suite A · Name", "Global · Name", or just the name for a suite the diagram does not label. */
export const suiteLabel = (s: Suite) => (s.diagram ? `${s.diagram} · ${s.name}` : s.name);

const platform = (id: string, name: string, route?: string) => info(id, name, 'platform', 'platform', route);

export const PLATFORM_SERVICES: ModuleInfo[] = [
  platform('identity', 'Identity & Access', '/users'),
  platform('tenancy', 'Tenancy'),
  platform('billing', 'Billing'),
  platform('workflow', 'Workflow & Approvals'),
  platform('audit', 'Audit Log', '/audit-logs'),
  platform('notification', 'Notifications'),
  platform('documents', 'Documents & Media'),
  platform('reporting', 'Reporting & Analytics'),
  platform('search', 'Global Search'),
  platform('scheduler', 'Scheduler'),
  platform('event-bus', 'Event Bus'),
  platform('integration-hub', 'Integration Hub'),
  platform('api-gateway', 'API Gateway')
];

const integration = (id: string, name: string) => info(id, name, 'integration', 'integrations');

export const INTEGRATIONS: ModuleInfo[] = [
  integration('payment-sbiepay', 'SBIePay'),
  integration('digilocker', 'DigiLocker'),
  integration('nad', 'NAD'),
  integration('government-portals', 'Government Systems'),
  integration('messaging-providers', 'Email / SMS / WhatsApp'),
  integration('video-conferencing', 'Video Conferencing'),
  integration('wearables', 'Wearable Devices'),
  integration('external-university-portals', 'Other University Portals')
];

export const ALL_MODULES: ModuleInfo[] = [
  ...SUITES.flatMap((s) => s.modules),
  ...PLATFORM_SERVICES,
  ...INTEGRATIONS
];

const MODULE_INDEX = new Map(ALL_MODULES.map((m) => [m.id, m]));

export const findModule = (id: string) => MODULE_INDEX.get(id);

export const findSuite = (id: string) => SUITES.find((s) => s.id === id);

/** `<domain>/<module>` as profiles, plans and entitlements name feature modules. */
export const modulePath = (m: ModuleInfo) => {
  const s = findSuite(m.suiteId);
  return s ? `${s.domain}/${m.id}` : m.id;
};

/** Colour used for a module's accents: its suite colour, or a fixed one for platform and integrations. */
export const moduleColor = (m: ModuleInfo) =>
  findSuite(m.suiteId)?.color ?? '#7E22CE';

/** Where a module link should go: its admin screen if one exists, else the generic module page. */
export const moduleHref = (m: ModuleInfo) => m.route ?? `/modules/${m.id}`;
