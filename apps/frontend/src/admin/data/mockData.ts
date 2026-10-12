import {
  User,
  AdmissionApplication,
  AuditLog,
  ActionRequiredItem,
  AlertNotification,
  UniversityEvent
} from '../types';

export const MOCK_USERS: User[] = [
  {
    id: 'USR-1001',
    name: 'Dr. A. Sharma',
    email: 'a.sharma@example.edu',
    role: 'org-admin',
    department: 'Central Administration',
    status: 'Active',
    lastLogin: 'Today, 09:40 AM',
    dataScope: 'Institution',
    employeeId: 'ADM-2018-001',
    phone: '+91 98140 23891',
    twoFactorEnabled: true
  },
  {
    id: 'USR-1002',
    name: 'P. Singh, CA',
    email: 'p.singh@example.edu',
    role: 'finance-staff',
    department: 'Finance & Accounts',
    status: 'Active',
    lastLogin: 'Today, 10:42 AM',
    dataScope: 'Department',
    employeeId: 'FIN-2019-014',
    phone: '+91 98722 84910',
    twoFactorEnabled: true
  },
  {
    id: 'USR-1003',
    name: 'Dr. R. Kaur',
    email: 'r.kaur@example.edu',
    role: 'faculty',
    department: 'Computer Science & AI',
    status: 'Active',
    lastLogin: 'Yesterday, 04:15 PM',
    dataScope: 'Assigned Records',
    employeeId: 'FAC-2020-045',
    phone: '+91 94178 30129',
    twoFactorEnabled: true
  },
  {
    id: 'USR-1004',
    name: 'Col. Gurmeet Dhillon (Retd.)',
    email: 'g.dhillon@example.edu',
    role: 'department-admin',
    department: 'Sports Science & Athletics',
    status: 'Active',
    lastLogin: 'Today, 10:04 AM',
    dataScope: 'Department',
    employeeId: 'SPT-2019-003',
    phone: '+91 98150 99421',
    twoFactorEnabled: true
  },
  {
    id: 'USR-1005',
    name: 'Dr. Vikram Malhotra',
    email: 'v.malhotra@example.edu',
    role: 'examination-staff',
    department: 'Controller of Examinations',
    status: 'Active',
    lastLogin: 'Today, 10:35 AM',
    dataScope: 'Institution',
    employeeId: 'EXM-2021-008',
    phone: '+91 98881 77312',
    twoFactorEnabled: true
  },
  {
    id: 'USR-1006',
    name: 'Rajinder Kumar',
    email: 'r.kumar@example.edu',
    role: 'coach',
    department: 'Athletics & Track',
    status: 'Active',
    lastLogin: 'Yesterday, 06:20 PM',
    dataScope: 'Assigned Records',
    employeeId: 'CCH-2022-019',
    phone: '+91 97790 41203',
    twoFactorEnabled: false
  },
  {
    id: 'USR-1007',
    name: 'Manpreet Sandhu',
    email: 'm.sandhu@example.edu',
    role: 'department-admin',
    department: 'Physical Education',
    status: 'Pending',
    lastLogin: '04 Oct 2026, 11:10 AM',
    dataScope: 'Department',
    employeeId: 'DPA-2024-032',
    phone: '+91 98144 55928',
    twoFactorEnabled: false
  },
  {
    id: 'USR-1008',
    name: 'Sunita Verma',
    email: 's.verma@example.edu',
    role: 'support-staff',
    department: 'Student Support Center',
    status: 'Active',
    lastLogin: 'Today, 08:30 AM',
    dataScope: 'Assigned Records',
    employeeId: 'HLP-2023-011',
    phone: '+91 99148 66201',
    twoFactorEnabled: true
  },
  {
    id: 'USR-1009',
    name: 'Harbhajan Chahal',
    email: 'h.chahal@example.gov',
    role: 'governance',
    department: 'State Internal Audit Bureau',
    status: 'Suspended',
    lastLogin: '28 Sep 2026, 02:45 PM',
    dataScope: 'Institution',
    employeeId: 'EXT-2022-004',
    phone: '+91 98765 43210',
    twoFactorEnabled: true
  }
];

export const MOCK_APPLICATIONS: AdmissionApplication[] = [
  {
    id: 'ADM-1024',
    applicant: 'Harpreet Singh',
    programme: 'B.Tech CSE (Sports Analytics)',
    category: 'General',
    status: 'Under Review',
    submitted: '05 Oct 2026',
    email: 'h.singh2004@gmail.com',
    phone: '+91 98141 88204',
    meritRank: 42,
    sportsDiscipline: 'Athletics (400m Sprint)',
    notes: 'National School Games Silver Medalist. 10+2 Aggregate: 91.4%',
    documents: [
      { id: 'DOC-1', name: 'Aadhaar Card (UIDAI Verified)', verified: true, type: 'PDF', fileSize: '1.2 MB' },
      { id: 'DOC-2', name: 'Class 12th Senior Secondary Marks Card', verified: true, type: 'PDF', fileSize: '2.4 MB' },
      { id: 'DOC-3', name: 'Passport Size Photograph & Signature', verified: true, type: 'JPG', fileSize: '480 KB' },
      { id: 'DOC-4', name: 'National Sports Merit Certificate', verified: false, type: 'PDF', fileSize: '3.1 MB' }
    ],
    timeline: [
      { step: 'Application Submitted', status: 'completed', timestamp: '05 Oct 2026, 09:14 AM', note: 'Application fee ₹1,500 settled via HDFC Gateway' },
      { step: 'Documents Uploaded', status: 'completed', timestamp: '05 Oct 2026, 09:40 AM', note: 'All 4 statutory credentials uploaded' },
      { step: 'Document Verification', status: 'in-progress', timestamp: '05 Oct 2026, 02:30 PM', note: 'Awaiting sports certificate validation from Dean Sports' },
      { step: 'Counselling & Seat Allotment', status: 'pending', timestamp: 'Scheduled for 12 Oct 2026' },
      { step: 'Confirmation & Registration', status: 'pending', timestamp: 'Pending fee deposit' }
    ]
  },
  {
    id: 'ADM-1025',
    applicant: 'Simran Kaur',
    programme: 'B.Sc Sports Science & Biomechanics',
    category: 'OBC',
    status: 'Shortlisted',
    submitted: '05 Oct 2026',
    email: 'simran.kaur.sprt@outlook.com',
    phone: '+91 97792 10492',
    meritRank: 18,
    sportsDiscipline: 'Shooting (10m Air Rifle)',
    notes: 'Khelo India University Games Gold medalist. State quota eligible.',
    documents: [
      { id: 'DOC-1', name: 'Aadhaar Card', verified: true, type: 'PDF', fileSize: '1.1 MB' },
      { id: 'DOC-2', name: '10+2 Science Board Marks Card', verified: true, type: 'PDF', fileSize: '2.8 MB' },
      { id: 'DOC-3', name: 'OBC Non-Creamy Layer Certificate', verified: true, type: 'PDF', fileSize: '1.9 MB' },
      { id: 'DOC-4', name: 'Recent Photograph', verified: true, type: 'PNG', fileSize: '650 KB' }
    ],
    timeline: [
      { step: 'Application Submitted', status: 'completed', timestamp: '05 Oct 2026, 08:30 AM' },
      { step: 'Documents Uploaded', status: 'completed', timestamp: '05 Oct 2026, 08:45 AM' },
      { step: 'Document Verification', status: 'completed', timestamp: '05 Oct 2026, 04:15 PM', note: 'Verified by Prof. S. Dhillon' },
      { step: 'Counselling & Seat Allotment', status: 'in-progress', timestamp: 'Round 1 counselling call issued' },
      { step: 'Confirmation & Registration', status: 'pending', timestamp: 'Awaiting candidate acceptance' }
    ]
  },
  {
    id: 'ADM-1026',
    applicant: 'Arjun Sharma',
    programme: 'BBA Sports Management',
    category: 'General',
    status: 'Confirmed',
    submitted: '04 Oct 2026',
    email: 'arjun.sharma.mgt@yahoo.in',
    phone: '+91 98884 55301',
    meritRank: 5,
    sportsDiscipline: 'Cricket (State U-19)',
    notes: 'Seat confirmed in Merit List 1. Semester tuition fee received in full.',
    documents: [
      { id: 'DOC-1', name: 'Aadhaar Card', verified: true, type: 'PDF', fileSize: '1.0 MB' },
      { id: 'DOC-2', name: 'Class 12th Commerce Board Certificate', verified: true, type: 'PDF', fileSize: '3.0 MB' },
      { id: 'DOC-3', name: 'Photograph & Specimen Signature', verified: true, type: 'JPG', fileSize: '520 KB' },
      { id: 'DOC-4', name: 'Migration Certificate', verified: true, type: 'PDF', fileSize: '1.4 MB' }
    ],
    timeline: [
      { step: 'Application Submitted', status: 'completed', timestamp: '04 Oct 2026, 11:20 AM' },
      { step: 'Documents Uploaded', status: 'completed', timestamp: '04 Oct 2026, 11:40 AM' },
      { step: 'Document Verification', status: 'completed', timestamp: '04 Oct 2026, 03:00 PM' },
      { step: 'Counselling & Seat Allotment', status: 'completed', timestamp: '05 Oct 2026, 10:00 AM' },
      { step: 'Confirmation & Registration', status: 'completed', timestamp: '05 Oct 2026, 02:40 PM', note: 'Fee receipt REC-99214 generated' }
    ]
  },
  {
    id: 'ADM-1027',
    applicant: 'Navneet Sandhu',
    programme: 'M.P.Ed (Physical Education)',
    category: 'Sports Quota',
    status: 'Under Review',
    submitted: '03 Oct 2026',
    email: 'n.sandhu.track@gmail.com',
    phone: '+91 94170 82910',
    meritRank: 12,
    sportsDiscipline: 'Wrestling (Freestyle 74kg)',
    notes: 'All India Inter-University Bronze Medalist.',
    documents: [
      { id: 'DOC-1', name: 'Aadhaar Card', verified: true, type: 'PDF', fileSize: '1.3 MB' },
      { id: 'DOC-2', name: 'B.P.Ed Degree Transcript', verified: true, type: 'PDF', fileSize: '4.2 MB' },
      { id: 'DOC-3', name: 'Sports Performance Affidavit', verified: false, type: 'PDF', fileSize: '1.8 MB' }
    ],
    timeline: [
      { step: 'Application Submitted', status: 'completed', timestamp: '03 Oct 2026, 02:15 PM' },
      { step: 'Documents Uploaded', status: 'completed', timestamp: '03 Oct 2026, 02:35 PM' },
      { step: 'Document Verification', status: 'in-progress', timestamp: 'Pending trial fitness certificate' },
      { step: 'Counselling & Seat Allotment', status: 'pending', timestamp: 'Pending' },
      { step: 'Confirmation & Registration', status: 'pending', timestamp: 'Pending' }
    ]
  },
  {
    id: 'ADM-1028',
    applicant: 'Bhavna Rathore',
    programme: 'B.Sc Sports Science & Biomechanics',
    category: 'Defence',
    status: 'Shortlisted',
    submitted: '03 Oct 2026',
    email: 'bhavna.r.defence@gmail.com',
    phone: '+91 99150 49182',
    meritRank: 24,
    sportsDiscipline: 'Swimming (200m Breaststroke)',
    documents: [
      { id: 'DOC-1', name: 'Aadhaar Card', verified: true, type: 'PDF', fileSize: '1.0 MB' },
      { id: 'DOC-2', name: 'Class 12th Marks Sheet', verified: true, type: 'PDF', fileSize: '2.5 MB' },
      { id: 'DOC-3', name: 'Priority V Defence Personnel Ward Certificate', verified: true, type: 'PDF', fileSize: '1.5 MB' }
    ],
    timeline: [
      { step: 'Application Submitted', status: 'completed', timestamp: '03 Oct 2026, 10:05 AM' },
      { step: 'Documents Uploaded', status: 'completed', timestamp: '03 Oct 2026, 10:25 AM' },
      { step: 'Document Verification', status: 'completed', timestamp: '04 Oct 2026, 11:30 AM' },
      { step: 'Counselling & Seat Allotment', status: 'in-progress', timestamp: 'Allotted Priority 1 seat' },
      { step: 'Confirmation & Registration', status: 'pending', timestamp: 'Pending' }
    ]
  },
  {
    id: 'ADM-1029',
    applicant: 'Taranjeet Singh',
    programme: 'B.Tech CSE (Sports Analytics)',
    category: 'SC/ST',
    status: 'Confirmed',
    submitted: '02 Oct 2026',
    email: 't.singh.tech@example.gov',
    phone: '+91 98155 33019',
    meritRank: 8,
    sportsDiscipline: 'Badminton',
    documents: [
      { id: 'DOC-1', name: 'Aadhaar Card', verified: true, type: 'PDF', fileSize: '1.1 MB' },
      { id: 'DOC-2', name: 'Class 12th Non-Medical Transcript', verified: true, type: 'PDF', fileSize: '2.1 MB' },
      { id: 'DOC-3', name: 'SC Certificate issued by Tehsildar', verified: true, type: 'PDF', fileSize: '1.4 MB' }
    ],
    timeline: [
      { step: 'Application Submitted', status: 'completed', timestamp: '02 Oct 2026, 04:00 PM' },
      { step: 'Documents Uploaded', status: 'completed', timestamp: '02 Oct 2026, 04:20 PM' },
      { step: 'Document Verification', status: 'completed', timestamp: '03 Oct 2026, 11:00 AM' },
      { step: 'Counselling & Seat Allotment', status: 'completed', timestamp: '04 Oct 2026, 09:30 AM' },
      { step: 'Confirmation & Registration', status: 'completed', timestamp: '04 Oct 2026, 03:00 PM' }
    ]
  }
];

export const MOCK_ACTION_REQUIRED: ActionRequiredItem[] = [
  {
    id: 'ACT-01',
    type: 'Payment Request',
    referenceCode: 'PAY-20481',
    title: 'Vendor Payment for Athletic Track Maintenance',
    description: 'Awaiting financial concurrence and Vice-Chancellor sanction (₹14,50,000)',
    urgency: 'Pending',
    time: '24 mins ago',
    linkTo: '/audit-logs'
  },
  {
    id: 'ACT-02',
    type: 'Admission Application',
    referenceCode: 'ADM-1024',
    title: 'Harpreet Singh — B.Tech CSE (Sports Analytics)',
    description: 'Document verification required for National Merit certificate',
    urgency: 'Urgent',
    time: '45 mins ago',
    linkTo: '/admissions'
  },
  {
    id: 'ACT-03',
    type: 'Examination Results',
    referenceCode: 'EXM-238',
    title: 'End-Semester B.Sc Sports Science Batch 2025',
    description: 'Tabulation sheet pending controller final sign-off before gazette publication',
    urgency: 'Pending',
    time: '1 hr ago',
    linkTo: '/audit-logs'
  },
  {
    id: 'ACT-04',
    type: 'Procurement Request',
    referenceCode: 'PR-882',
    title: 'Biomechanics High-Speed Infrared Cameras (x6)',
    description: 'GeM portal tender evaluation bids awaiting administrative clearance',
    urgency: 'Review',
    time: '2 hrs ago',
    linkTo: '/audit-logs'
  },
  {
    id: 'ACT-05',
    type: 'RTI Application',
    referenceCode: 'RTI-104',
    title: 'Information Request regarding Sports Hostel Allotments',
    description: 'Statutory 30-day compliance deadline approaching in 48 hours',
    urgency: 'Urgent',
    time: '3 hrs ago',
    linkTo: '/audit-logs'
  }
];

export const MOCK_ALERTS: AlertNotification[] = [
  {
    id: 'ALT-01',
    title: 'RTI deadline approaching',
    subtitle: '3 applications require immediate statutory PIO response within 48h',
    category: 'Compliance',
    severity: 'critical',
    timestamp: '10 mins ago'
  },
  {
    id: 'ALT-02',
    title: 'Inventory below reorder level',
    subtitle: '5 items in Sports Physiotherapy Clinic require restocking PO',
    category: 'Inventory',
    severity: 'warning',
    timestamp: '35 mins ago'
  },
  {
    id: 'ALT-03',
    title: 'Grievance case pending',
    subtitle: '2 student grievance tickets escalated to Proctorial Committee',
    category: 'Grievance',
    severity: 'warning',
    timestamp: '1 hour ago'
  },
  {
    id: 'ALT-04',
    title: 'Payment reconciliation completed',
    subtitle: 'SBI e-Pay portal reconciled ₹1.28 Cr admission receipts for Batch 2026',
    category: 'Finance',
    severity: 'success',
    timestamp: '2 hours ago'
  },
  {
    id: 'ALT-05',
    title: 'System backup completed successfully',
    subtitle: 'Daily snapshot of Oracle ERP Database archived to Disaster Recovery node',
    category: 'System',
    severity: 'info',
    timestamp: '03:00 AM'
  }
];

export const MOCK_CALENDAR_EVENTS: UniversityEvent[] = [
  {
    id: 'EV-01',
    day: '06',
    month: 'OCT',
    title: 'Academic Council Meeting (Quarterly Review)',
    time: '11:00 AM – 01:30 PM',
    category: 'Governance',
    location: 'Senate Hall, Administrative Block',
    filter: 'today'
  },
  {
    id: 'EV-02',
    day: '08',
    month: 'OCT',
    title: 'Mid-Term Examination Commences',
    time: '09:30 AM',
    category: 'Exam',
    location: 'Examination Complex A & B',
    filter: 'week'
  },
  {
    id: 'EV-03',
    day: '11',
    month: 'OCT',
    title: 'Inter-University Athletics Championship Trial',
    time: '07:00 AM',
    category: 'Sports',
    location: 'Synthetic Athletic Stadium',
    filter: 'week'
  },
  {
    id: 'EV-04',
    day: '14',
    month: 'OCT',
    title: 'Autumn Semester Fee Payment Deadline (Without Fine)',
    time: '05:00 PM',
    category: 'Finance',
    location: 'Online Edu OS Portal & Accounts Branch',
    filter: 'month'
  },
  {
    id: 'EV-05',
    day: '18',
    month: 'OCT',
    title: 'IQAC NAAC Accreditation Preparedness Review',
    time: '02:00 PM',
    category: 'Academic',
    location: 'Board Room, VC Secretariat',
    filter: 'month'
  }
];

/** Sample audit events. Actions are event names from the repo's contracts and backends. */
export const MOCK_AUDIT_LOGS: AuditLog[] = [
  {
    id: 'AUD-901',
    timestamp: '10:42 AM',
    user: 'Demo organisation admin',
    role: 'org-admin',
    action: 'tenancy.organisation.registered',
    resource: 'org: demo-sports-college',
    status: 'Success',
    ipAddress: '172.16.2.45'
  },
  {
    id: 'AUD-902',
    timestamp: '10:44 AM',
    user: 'System',
    role: 'system',
    action: 'billing.subscription.started',
    resource: 'plan: trial',
    status: 'Success',
    ipAddress: '127.0.0.1'
  },
  {
    id: 'AUD-903',
    timestamp: '10:51 AM',
    user: 'Demo organisation admin',
    role: 'org-admin',
    action: 'tenancy.organisation.verified',
    resource: 'org: demo-sports-college',
    status: 'Success',
    ipAddress: '172.16.2.45'
  },
  {
    id: 'AUD-904',
    timestamp: '10:51 AM',
    user: 'System',
    role: 'system',
    action: 'tenancy.package.requested',
    resource: 'kind: registration',
    status: 'Warning',
    ipAddress: '127.0.0.1'
  },
  {
    id: 'AUD-905',
    timestamp: '11:20 AM',
    user: 'Platform operator',
    role: 'super-admin',
    action: 'tenancy.organisation.approved',
    resource: 'org: demo-sports-college',
    status: 'Success',
    ipAddress: '10.0.0.12'
  },
  {
    id: 'AUD-906',
    timestamp: '11:20 AM',
    user: 'System',
    role: 'system',
    action: 'tenancy.organisation.activated',
    resource: 'org: demo-sports-college',
    status: 'Success',
    ipAddress: '127.0.0.1'
  },
  {
    id: 'AUD-907',
    timestamp: '11:34 AM',
    user: 'Demo organisation admin',
    role: 'org-admin',
    action: 'identity.user.created',
    resource: 'role: faculty',
    status: 'Success',
    ipAddress: '172.16.2.45'
  },
  {
    id: 'AUD-908',
    timestamp: '11:52 AM',
    user: 'Demo organisation admin',
    role: 'org-admin',
    action: 'tenancy.entitlement.changed',
    resource: 'module toggled: academics/lms',
    status: 'Success',
    ipAddress: '172.16.2.45'
  },
  {
    id: 'AUD-909',
    timestamp: 'Yesterday, 05:22 PM',
    user: 'Platform operator',
    role: 'super-admin',
    action: 'tenancy.impersonation.started',
    resource: 'org: demo-sports-college',
    status: 'Warning',
    ipAddress: '10.0.0.12'
  }
];

export const ENROLLMENT_TREND = [
  { year: '2023', total: 2450, sportsQuota: 280, academics: 2170 },
  { year: '2024', total: 2910, sportsQuota: 330, academics: 2580 },
  { year: '2025', total: 3420, sportsQuota: 395, academics: 3025 },
  { year: '2026', total: 3842, sportsQuota: 428, academics: 3414 }
];

/** One colour per admissions stage: applications, shortlisted, counselling, confirmed. */
export const FUNNEL_COLORS = ['#7E22CE', '#4338CA', '#0369A1', '#15803D'];

export const ADMISSIONS_FUNNEL = [
  { stage: 'Applications', count: 1284, pct: '100%', color: '#9333EA', fill: '#9333EA' },
  { stage: 'Shortlisted', count: 824, pct: '64.2%', color: '#7E22CE', fill: '#7E22CE' },
  { stage: 'Counselling', count: 612, pct: '47.7%', color: '#16834B', fill: '#16834B' },
  { stage: 'Confirmed', count: 486, pct: '37.8%', color: '#F39A19', fill: '#F39A19' }
];
