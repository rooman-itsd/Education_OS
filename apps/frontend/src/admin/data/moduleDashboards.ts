// Demo dashboard content for every module page, in the same shape as the main
// Dashboard: 4 KPIs, a monthly histogram, a breakdown, action items and activity.
// Figures are illustrative until each module's API is built.

import type { Urgency } from '../components/ui/panels';
import type { Tone } from '../components/ui/dashboard';
import { ModuleInfo } from './architecture';

export interface KpiSpec {
  label: string;
  value: string;
  note: string;
  delta?: string;
  tone?: Tone;
}

export interface ModuleDashboard {
  /** Primary header action. */
  action: string;
  kpis: [KpiSpec, KpiSpec, KpiSpec, KpiSpec];
  chart: { title: string; subtitle: string; series: string[]; base: number; split?: number };
  breakdown: { title: string; subtitle: string; items: [string, number][]; footer?: [string, string]; unit?: string };
  actions: { ref: string; type: string; title: string; description: string; urgency: Urgency; time: string }[];
  activity: { time: string; title: string; who: string; ref: string; status?: 'Success' | 'Failed' | 'Warning' }[];
}

const k = (label: string, value: string, note: string, delta?: string, tone?: Tone): KpiSpec => ({ label, value, note, delta, tone });
const a = (ref: string, type: string, title: string, description: string, urgency: Urgency, time: string) => ({ ref, type, title, description, urgency, time });
const l = (time: string, title: string, who: string, ref: string, status?: 'Success' | 'Failed' | 'Warning') => ({ time, title, who, ref, status });

export const MODULE_DASHBOARDS: Record<string, ModuleDashboard> = {
  // ---------------- A · Pre-Admission & Student Information ----------------
  'web-portal-cms': {
    action: 'Publish Notice',
    kpis: [
      k('Page views (30 days)', '1.24 L', 'Public website traffic', '+9.4%'),
      k('Published pages', '342', 'Across 18 sections', '+12'),
      k('Pending approvals', '7', 'Notices awaiting sign-off', '2 urgent', 'alert'),
      k('Uptime', '99.98%', 'Last 30 days', 'SLA met')
    ],
    chart: { title: 'Website Traffic', subtitle: 'Monthly visitors, desktop vs mobile', series: ['Desktop', 'Mobile'], base: 21000, split: 0.42 },
    breakdown: { title: 'Top Sections', subtitle: 'Views in the last 30 days', items: [['Admissions 2026', 48210], ['Notices & Circulars', 26480], ['Sports Programmes', 19340], ['Results', 15620], ['Tenders', 6310]] },
    actions: [
      a('CMS-118', 'Notice', 'Merit List 2 announcement', 'Draft by Admissions Cell, needs Registrar approval', 'Urgent', '20 mins ago'),
      a('CMS-117', 'Page update', 'Hostel fee structure 2026–27', 'Finance revision pending publication', 'Pending', '2 hours ago'),
      a('CMS-115', 'Tender', 'Synthetic track resurfacing tender', 'Legal vetting complete, ready to publish', 'Review', 'Yesterday')
    ],
    activity: [
      l('10:12 AM', 'Published "Inter-University Athletics Meet" notice', 'Web Admin', 'CMS-116'),
      l('09:40 AM', 'Homepage banner rotated', 'Web Admin', 'CMS-BNR-22'),
      l('Yesterday', 'Broken link report generated', 'System', 'CMS-LNK-07', 'Warning')
    ]
  },
  admissions: {
    action: 'Create Admission',
    kpis: [
      k('Total applications', '1,284', 'Undergraduate & Masters', '+11.2%'),
      k('Confirmed', '486', 'Tuition fee paid in full', '37.8%'),
      k('Under review', '86', 'Requires Dean review', 'urgent', 'alert'),
      k('Shortlisted', '824', 'Counselling invitations issued', '64.2%')
    ],
    chart: { title: 'Applications Received', subtitle: 'Monthly, general vs sports quota', series: ['General', 'Sports quota'], base: 210, split: 0.18 },
    breakdown: { title: 'Admissions Funnel', subtitle: 'Batch 2026 conversion', items: [['Applications', 1284], ['Shortlisted', 824], ['Counselling', 612], ['Confirmed', 486]], footer: ['Overall acceptance', '37.8%'] },
    actions: [
      a('ADM-1024', 'Application', 'Harpreet Singh — B.Tech CSE (Sports Analytics)', 'National sports merit certificate unverified', 'Urgent', '45 mins ago'),
      a('ADM-1027', 'Application', 'Navneet Sandhu — M.P.Ed', 'Sports quota trial result awaited', 'Pending', '3 hours ago'),
      a('ADM-ML2', 'Merit list', 'Merit List 2 publication', 'Ready for Dean of Admissions sign-off', 'Review', 'Yesterday')
    ],
    activity: [
      l('10:30 AM', 'Application ADM-1026 confirmed', 'Admissions Cell', 'ADM-1026'),
      l('09:55 AM', 'Counselling slot allotted to 42 candidates', 'Admissions Cell', 'CNS-0610'),
      l('Yesterday', 'Document mismatch flagged', 'DigiLocker sync', 'ADM-1028', 'Warning')
    ]
  },
  'student-information': {
    action: 'Add Student',
    kpis: [
      k('Enrolled students', '3,842', 'Active academic records', '+4.8%'),
      k('Student-athletes', '428', 'Linked athlete profiles', '+8.2%'),
      k('Profile updates pending', '64', 'Awaiting verification', '9 urgent', 'alert'),
      k('ID cards issued', '3,611', 'This academic year', '94%')
    ],
    chart: { title: 'Student Records Updated', subtitle: 'Monthly, by staff vs self-service', series: ['Staff', 'Self-service'], base: 900, split: 0.55 },
    breakdown: { title: 'Students by School', subtitle: 'Current enrolment', items: [['Sports Sciences', 1210], ['Physical Education', 980], ['Management', 702], ['Computer Science & AI', 590], ['Humanities', 360]] },
    actions: [
      a('SIS-2210', 'Name change', 'Gurleen Kaur — name correction', 'Gazette notification attached', 'Pending', '1 hour ago'),
      a('SIS-2207', 'Category update', 'Ravi Kumar — category to SC', 'Certificate needs verification', 'Urgent', '3 hours ago'),
      a('SIS-2199', 'Status', 'Semester break request', 'Medical leave for 1 semester', 'Review', 'Yesterday')
    ],
    activity: [
      l('10:05 AM', 'Bulk ID cards printed (batch 14)', 'SIS Office', 'IDC-B14'),
      l('09:20 AM', 'Guardian contact updated', 'Student (self)', 'SIS-2208'),
      l('Yesterday', 'Duplicate record merged', 'SIS Office', 'SIS-DUP-31')
    ]
  },
  'enrolment-registration': {
    action: 'Open Registration',
    kpis: [
      k('Registered this semester', '3,605', 'Of 3,842 enrolled', '93.8%'),
      k('Electives allotted', '2,940', 'Seat allocation complete', '+210'),
      k('Pending registrations', '237', 'Fee or hold issues', 'action', 'alert'),
      k('Sections formed', '148', 'Across 42 programmes', '+6')
    ],
    chart: { title: 'Registrations', subtitle: 'Monthly, core vs elective', series: ['Core', 'Elective'], base: 520, split: 0.4 },
    breakdown: { title: 'Registration Holds', subtitle: 'Why students are blocked', items: [['Fee due', 112], ['Library dues', 48], ['Document pending', 39], ['Disciplinary', 6]] },
    actions: [
      a('REG-HLD', 'Hold review', '112 students blocked for fee dues', 'Finance confirmation needed to release', 'Urgent', '30 mins ago'),
      a('REG-ELC', 'Elective', 'Sports Psychology elective oversubscribed', '84 requests for 60 seats', 'Pending', '2 hours ago'),
      a('REG-SEC', 'Section', 'New section for B.P.Ed Semester 3', 'Faculty assignment pending', 'Review', 'Yesterday')
    ],
    activity: [
      l('10:18 AM', 'Late registration window opened', 'Registrar', 'REG-WIN-3'),
      l('09:44 AM', 'Elective lottery run for 6 courses', 'System', 'REG-LOT-12'),
      l('Yesterday', 'Registration sync to LMS', 'System', 'REG-SYNC', 'Success')
    ]
  },

  // ---------------- B · Academic & Learning ----------------
  'academic-management': {
    action: 'Add Course',
    kpis: [
      k('Programmes', '42', 'UG, PG and diploma', '+3'),
      k('Active courses', '386', 'This semester', '+18'),
      k('Curriculum revisions', '9', 'Awaiting Board of Studies', 'pending', 'alert'),
      k('Faculty assigned', '96%', 'Course-faculty mapping', '312 faculty')
    ],
    chart: { title: 'Teaching Load', subtitle: 'Credit hours per month, theory vs practical', series: ['Theory', 'Practical'], base: 4200, split: 0.45 },
    breakdown: { title: 'Courses by School', subtitle: 'Running this semester', items: [['Sports Sciences', 118], ['Physical Education', 94], ['Management', 72], ['Computer Science & AI', 64], ['Humanities', 38]] },
    actions: [
      a('BOS-14', 'Curriculum', 'B.Sc Sports Science syllabus revision', 'Board of Studies meeting on 12 Oct', 'Pending', '1 hour ago'),
      a('CRS-302', 'Faculty load', '3 courses without faculty', 'Strength & Conditioning lab sections', 'Urgent', '4 hours ago'),
      a('CRS-288', 'Credit change', 'Sports Nutrition credits 3 → 4', 'Academic Council approval needed', 'Review', 'Yesterday')
    ],
    activity: [
      l('10:02 AM', 'Course outcome mapping updated', 'Dr. R. Kaur', 'CRS-214'),
      l('09:15 AM', 'New elective "Esports Management" created', 'Academic Office', 'CRS-391'),
      l('Yesterday', 'Faculty load report exported', 'HoD, Sports Sciences', 'RPT-FL-10')
    ]
  },
  lms: {
    action: 'Create Course Content',
    kpis: [
      k('Active learners', '3,214', 'Logged in this week', '+6.1%'),
      k('Courses online', '348', 'With published content', '90%'),
      k('Assignments to grade', '412', 'Across all faculty', 'overdue 38', 'alert'),
      k('Avg. completion', '78%', 'Module completion rate', '+3.2%')
    ],
    chart: { title: 'Learning Activity', subtitle: 'Monthly submissions, assignments vs quizzes', series: ['Assignments', 'Quizzes'], base: 6800, split: 0.45 },
    breakdown: { title: 'Engagement by Programme', subtitle: 'Active learners this week', items: [['B.P.Ed', 820], ['B.Sc Sports Science', 760], ['BBA Sports Mgmt', 610], ['B.Tech CSE', 540], ['M.P.Ed', 484]] },
    actions: [
      a('LMS-GR', 'Grading', '38 assignments past grading deadline', 'Biomechanics and Exercise Physiology', 'Urgent', '25 mins ago'),
      a('LMS-PLG', 'Plagiarism', '5 submissions flagged above 40%', 'Research Methods — Section B', 'Review', '2 hours ago'),
      a('LMS-VID', 'Content', 'Lecture video upload failed', 'Sports Psychology week 6', 'Pending', 'Yesterday')
    ],
    activity: [
      l('10:20 AM', 'Quiz "Anatomy Unit 3" published', 'Dr. R. Kaur', 'LMS-Q-884'),
      l('09:48 AM', '142 submissions received', 'System', 'LMS-AS-219'),
      l('Yesterday', 'Discussion forum moderated', 'Faculty', 'LMS-FRM-41')
    ]
  },
  examinations: {
    action: 'Schedule Exam',
    kpis: [
      k('Exams scheduled', '214', 'Mid-semester, October', '+12'),
      k('Hall tickets issued', '3,540', 'Of 3,605 registered', '98.2%'),
      k('Results pending', '12', 'Awaiting moderation', 'urgent', 'alert'),
      k('Pass rate', '91.4%', 'Last semester', '+1.8%')
    ],
    chart: { title: 'Evaluations Completed', subtitle: 'Monthly, internal vs external', series: ['Internal', 'External'], base: 5200, split: 0.35 },
    breakdown: { title: 'Result Processing', subtitle: 'Current exam cycle', items: [['Answer sheets received', 7210], ['Evaluated', 6480], ['Moderated', 5120], ['Published', 4380]], footer: ['Cycle completion', '60.7%'] },
    actions: [
      a('EXM-238', 'Results', 'B.P.Ed Semester 5 results', 'Submitted for moderation by Controller', 'Urgent', '1 hour ago'),
      a('EXM-241', 'Re-evaluation', '27 re-evaluation requests', 'Fee received, evaluator assignment pending', 'Pending', '3 hours ago'),
      a('EXM-244', 'Clash', 'Timetable clash for 14 students', 'Elective exams on same slot', 'Review', 'Yesterday')
    ],
    activity: [
      l('10:35 AM', 'Results submitted for verification', 'Dr. Vikram Malhotra', 'EXM-238'),
      l('09:10 AM', 'Hall tickets generated (batch 4)', 'Exam Cell', 'HT-B4'),
      l('Yesterday', 'Question paper vault accessed', 'Controller of Exams', 'QPV-118', 'Warning')
    ]
  },
  'timetable-attendance': {
    action: 'Generate Timetable',
    kpis: [
      k('Classes today', '286', 'Across 42 programmes', '+4'),
      k('Avg. attendance', '86.4%', 'This week', '+1.2%'),
      k('Below 75%', '214', 'Students at debarment risk', 'alert', 'alert'),
      k('Attendance to mark', '19', 'Sessions not yet marked', 'today', 'muted')
    ],
    chart: { title: 'Attendance Sessions', subtitle: 'Monthly, lectures vs practicals', series: ['Lectures', 'Practicals'], base: 5600, split: 0.4 },
    breakdown: { title: 'Attendance by School', subtitle: 'Average this month', unit: '%', items: [['Sports Sciences', 91], ['Physical Education', 88], ['Management', 85], ['Computer Science & AI', 83], ['Humanities', 80]] },
    actions: [
      a('ATT-DBR', 'Debarment', '214 students below 75%', 'Warning letters to be issued', 'Urgent', '40 mins ago'),
      a('TT-ROOM', 'Room clash', 'Seminar Hall B double-booked', 'Thursday 11:00, two sections', 'Pending', '2 hours ago'),
      a('ATT-COR', 'Correction', '6 attendance correction requests', 'Athletes on tournament duty', 'Review', 'Yesterday')
    ],
    activity: [
      l('10:40 AM', 'Attendance marked for 64 sessions', 'Faculty', 'ATT-0610'),
      l('09:12 AM', 'Trial session roster locked', 'Rajinder Kumar', 'ATT-9041'),
      l('Yesterday', 'Timetable v3 published', 'Academic Office', 'TT-V3')
    ]
  },

  // ---------------- C · Sports & Athlete Performance ----------------
  'athlete-performance': {
    action: 'Add Athlete',
    kpis: [
      k('Active athletes', '428', '16 competitive disciplines', '+8.2%'),
      k('Fitness tests this month', '312', 'Benchmarks recorded', '+46'),
      k('Below benchmark', '37', 'Need intervention plan', 'review', 'alert'),
      k('National-level athletes', '64', 'Representing state or country', '+5')
    ],
    chart: { title: 'Fitness Assessments', subtitle: 'Monthly, field vs lab tests', series: ['Field', 'Lab'], base: 260, split: 0.35 },
    breakdown: { title: 'Athletes by Discipline', subtitle: 'Top disciplines', items: [['Athletics', 96], ['Wrestling', 58], ['Hockey', 52], ['Shooting', 41], ['Boxing', 38]] },
    actions: [
      a('ATH-4091', 'Performance', 'Sprint squad 100m times regressed', '5 athletes slower by 0.2s or more', 'Urgent', '1 hour ago'),
      a('ATH-CLR', 'Clearance', '12 fitness clearances pending', 'Needed before inter-university meet', 'Pending', '3 hours ago'),
      a('ATH-PLN', 'Plan', 'Off-season plan for wrestling squad', 'Coach submitted, HoD review', 'Review', 'Yesterday')
    ],
    activity: [
      l('10:04 AM', 'Athlete performance biometric record updated', 'Col. Gurmeet Dhillon', 'ATH-4091'),
      l('09:30 AM', 'VO2 max results imported', 'Sports Science Lab', 'LAB-0610'),
      l('Yesterday', 'Wearable sync failed for 3 athletes', 'Wearables adapter', 'WRB-ERR-9', 'Warning')
    ]
  },
  'training-video-analysis': {
    action: 'Upload Video',
    kpis: [
      k('Training sessions', '1,146', 'Logged this month', '+12%'),
      k('Videos uploaded', '524', 'Match and training footage', '+88'),
      k('Reviews pending', '43', 'Awaiting coach annotation', 'pending', 'alert'),
      k('Storage used', '2.8 TB', 'Of 5 TB quota', '56%', 'muted')
    ],
    chart: { title: 'Training Sessions', subtitle: 'Monthly, team vs individual', series: ['Team', 'Individual'], base: 980, split: 0.4 },
    breakdown: { title: 'Videos by Sport', subtitle: 'Uploaded this month', items: [['Hockey', 132], ['Athletics', 118], ['Wrestling', 96], ['Boxing', 74], ['Football', 61]] },
    actions: [
      a('VID-773', 'Review', 'Hockey semi-final footage', 'Tactical review requested by head coach', 'Pending', '2 hours ago'),
      a('VID-770', 'Annotation', 'Javelin technique breakdown', '8 clips awaiting biomechanics notes', 'Review', '5 hours ago'),
      a('VID-STR', 'Storage', 'Quota 56% used', 'Archive season 2025 footage', 'Pending', 'Yesterday')
    ],
    activity: [
      l('10:22 AM', 'Session plan "Speed endurance" assigned', 'Coach Rajinder Kumar', 'TRN-552'),
      l('09:35 AM', '24 clips tagged', 'Video Analyst', 'VID-768'),
      l('Yesterday', 'Match video shared with athlete', 'Coach', 'VID-761')
    ]
  },
  'sports-nutrition-health': {
    action: 'New Diet Plan',
    kpis: [
      k('Athletes on diet plans', '286', 'Personalised nutrition', '+14'),
      k('Physio sessions', '418', 'This month', '+9.6%'),
      k('Active injuries', '23', 'Under rehabilitation', '4 severe', 'alert'),
      k('Return-to-play', '17', 'Cleared this month', '+5')
    ],
    chart: { title: 'Clinic Visits', subtitle: 'Monthly, physio vs medical', series: ['Physio', 'Medical'], base: 380, split: 0.38 },
    breakdown: { title: 'Injuries by Type', subtitle: 'Current season', items: [['Hamstring strain', 9], ['Ankle sprain', 7], ['Shoulder', 4], ['Knee ligament', 2], ['Other', 1]] },
    actions: [
      a('MED-881', 'Injury', 'ACL suspected — wrestling athlete', 'MRI referral needs approval', 'Urgent', '35 mins ago'),
      a('NUT-214', 'Plan review', '12 diet plans due for review', 'Pre-competition phase', 'Pending', '3 hours ago'),
      a('MED-874', 'Clearance', 'Return-to-play for 3 athletes', 'Physio sign-off complete', 'Review', 'Yesterday')
    ],
    activity: [
      l('10:28 AM', 'Rehab session logged', 'Physiotherapist', 'PHY-2291'),
      l('09:50 AM', 'Body composition scans uploaded', 'Nutritionist', 'NUT-BCS-14'),
      l('Yesterday', 'Supplement stock below threshold', 'Clinic store', 'NUT-STK-3', 'Warning')
    ]
  },
  'tournament-events': {
    action: 'Create Tournament',
    kpis: [
      k('Upcoming events', '14', 'Next 60 days', '+3'),
      k('Medals this season', '86', 'Gold 29 · Silver 31 · Bronze 26', '+12'),
      k('Entries pending', '9', 'Federation registrations', 'deadline', 'alert'),
      k('Teams travelling', '6', 'This month', '112 athletes', 'muted')
    ],
    chart: { title: 'Medals Won', subtitle: 'Monthly, individual vs team events', series: ['Individual', 'Team'], base: 14, split: 0.3 },
    breakdown: { title: 'Medals by Sport', subtitle: 'This season', items: [['Athletics', 24], ['Wrestling', 18], ['Shooting', 15], ['Boxing', 13], ['Hockey', 6]] },
    actions: [
      a('TRN-AIU', 'Entry', 'AIU Athletics entries close Friday', '9 athletes not yet registered', 'Urgent', '1 hour ago'),
      a('TRN-TRV', 'Travel', 'Hockey team travel to Bhopal', 'Rail tickets and per-diem approval', 'Pending', '4 hours ago'),
      a('TRN-OFF', 'Officials', 'Technical officials for home meet', '6 officials to confirm', 'Review', 'Yesterday')
    ],
    activity: [
      l('10:15 AM', 'Fixture list published', 'Sports Office', 'FIX-1006'),
      l('09:00 AM', 'Results uploaded: State Boxing', 'Event Manager', 'RES-0605'),
      l('Yesterday', 'Accreditation cards printed', 'Sports Office', 'ACC-221')
    ]
  },

  // ---------------- D · Facility & Resource ----------------
  'sports-facilities': {
    action: 'Add Facility',
    kpis: [
      k('Facilities', '38', 'Grounds, courts, pools, gyms', '+2'),
      k('Utilisation', '81%', 'Booked hours this week', '+6%'),
      k('Out of service', '3', 'Under repair', 'alert', 'alert'),
      k('Safety audits due', '5', 'This month', 'scheduled', 'muted')
    ],
    chart: { title: 'Facility Hours Used', subtitle: 'Monthly, training vs events', series: ['Training', 'Events'], base: 3600, split: 0.22 },
    breakdown: { title: 'Utilisation by Facility', subtitle: 'Booked hours this week', items: [['Synthetic Track', 96], ['Hockey Turf', 88], ['Aquatic Centre', 74], ['Wrestling Hall', 70], ['Indoor Stadium', 63]] },
    actions: [
      a('FAC-POOL', 'Repair', 'Aquatic centre filtration pump', 'Vendor quote ₹2.4 L awaiting approval', 'Urgent', '50 mins ago'),
      a('FAC-AUD', 'Safety audit', 'Shooting range annual audit', 'Due by 15 Oct', 'Pending', '3 hours ago'),
      a('FAC-LGT', 'Upgrade', 'LED floodlights for hockey turf', 'Proposal for budget review', 'Review', 'Yesterday')
    ],
    activity: [
      l('10:05 AM', 'Track marked available after resurfacing', 'Facility Manager', 'FAC-TRK'),
      l('09:30 AM', 'Gym equipment inspection logged', 'Facility Staff', 'FAC-GYM-12'),
      l('Yesterday', 'Pool chlorine level alert', 'Sensor', 'FAC-POOL-S2', 'Warning')
    ]
  },
  'facility-booking': {
    action: 'New Booking',
    kpis: [
      k('Bookings today', '64', 'Classrooms, halls, venues', '+8'),
      k('This month', '1,412', 'Confirmed bookings', '+11%'),
      k('Awaiting approval', '18', 'Requests in queue', '5 urgent', 'alert'),
      k('Cancellations', '3.2%', 'This month', '-0.8%', 'muted')
    ],
    chart: { title: 'Bookings', subtitle: 'Monthly, academic vs sports venues', series: ['Academic', 'Sports'], base: 1200, split: 0.45 },
    breakdown: { title: 'Bookings by Venue Type', subtitle: 'This month', items: [['Classrooms', 520], ['Sports venues', 446], ['Seminar halls', 214], ['Labs', 148], ['Auditorium', 84]] },
    actions: [
      a('BKG-3391', 'Approval', 'Auditorium for Alumni Meet', '20 Oct, 600 guests', 'Urgent', '30 mins ago'),
      a('BKG-3388', 'Conflict', 'Indoor stadium double-booked', 'Badminton trials vs convocation rehearsal', 'Pending', '2 hours ago'),
      a('BKG-3380', 'Recurring', 'Semester booking for Yoga Hall', '3 days a week, Physical Education', 'Review', 'Yesterday')
    ],
    activity: [
      l('10:10 AM', '12 bookings auto-approved', 'System', 'BKG-AUTO'),
      l('09:25 AM', 'Seminar Hall A booked', 'HoD, Management', 'BKG-3392'),
      l('Yesterday', 'No-show released 4 slots', 'System', 'BKG-NS-6')
    ]
  },
  'inventory-equipment': {
    action: 'Issue Equipment',
    kpis: [
      k('Items in stock', '12,480', 'Across 9 stores', '+320'),
      k('Issued this month', '1,936', 'Equipment and consumables', '+7%'),
      k('Below reorder level', '5', 'Need purchase indent', 'reorder', 'alert'),
      k('Overdue returns', '42', 'Not returned on time', 'follow up', 'muted')
    ],
    chart: { title: 'Stock Movement', subtitle: 'Monthly, issues vs returns', series: ['Issued', 'Returned'], base: 1700, split: 0.45 },
    breakdown: { title: 'Stock by Category', subtitle: 'Items on hand', items: [['Sports equipment', 4820], ['Lab consumables', 3110], ['Stationery', 2240], ['Medical supplies', 1310], ['IT accessories', 1000]] },
    actions: [
      a('INV-RO', 'Reorder', 'Hockey balls below reorder level', '40 left, reorder level 120', 'Urgent', '1 hour ago'),
      a('INV-OVD', 'Overdue', '42 items overdue for return', 'Mostly athletics spikes and kits', 'Pending', '3 hours ago'),
      a('INV-AUD', 'Stock audit', 'Annual stock verification', 'Central store, 14 Oct', 'Review', 'Yesterday')
    ],
    activity: [
      l('10:00 AM', '24 javelins issued to athletics squad', 'Store Keeper', 'ISS-6610'),
      l('09:20 AM', 'GRN recorded for lab consumables', 'Store Keeper', 'GRN-2281'),
      l('Yesterday', 'Low stock alert: first-aid kits', 'System', 'INV-LS-11', 'Warning')
    ]
  },
  'asset-management': {
    action: 'Register Asset',
    kpis: [
      k('Fixed assets', '6,214', 'Tagged and registered', '+86'),
      k('Asset value', '₹184 Cr', 'Net book value', '+2.1%'),
      k('Audit due', '312', 'Physical verification pending', 'due', 'alert'),
      k('Disposals pending', '27', 'Condemnation committee', 'review', 'muted')
    ],
    chart: { title: 'Assets Added', subtitle: 'Monthly, equipment vs infrastructure', series: ['Equipment', 'Infrastructure'], base: 70, split: 0.25 },
    breakdown: { title: 'Value by Category', subtitle: '₹ crore, net book value', items: [['Buildings', 112], ['Sports infrastructure', 38], ['Lab equipment', 17], ['IT hardware', 11], ['Vehicles', 6]] },
    actions: [
      a('AST-AUD', 'Verification', '312 assets due for verification', 'Block C and Sports Complex', 'Urgent', '2 hours ago'),
      a('AST-DSP', 'Disposal', '27 assets for condemnation', 'Committee meeting on 18 Oct', 'Pending', '5 hours ago'),
      a('AST-TRF', 'Transfer', 'Treadmills moved to new gym', 'Location update approval', 'Review', 'Yesterday')
    ],
    activity: [
      l('10:25 AM', '86 assets tagged with QR labels', 'Asset Officer', 'AST-TAG-9'),
      l('09:15 AM', 'Depreciation run for September', 'System', 'AST-DEP-09'),
      l('Yesterday', 'Missing asset reported', 'Facility Staff', 'AST-MIS-4', 'Warning')
    ]
  },
  maintenance: {
    action: 'Raise Work Order',
    kpis: [
      k('Open work orders', '58', 'Across campus', '-6'),
      k('Completed this month', '214', 'Closed work orders', '+12%'),
      k('Overdue', '11', 'Past target date', 'escalate', 'alert'),
      k('Preventive tasks', '92%', 'On schedule', '+4%')
    ],
    chart: { title: 'Work Orders Closed', subtitle: 'Monthly, corrective vs preventive', series: ['Corrective', 'Preventive'], base: 190, split: 0.4 },
    breakdown: { title: 'Open Orders by Trade', subtitle: 'Current backlog', items: [['Electrical', 19], ['Plumbing', 14], ['Civil', 11], ['HVAC', 8], ['Carpentry', 6]] },
    actions: [
      a('WO-7781', 'Electrical', 'Hostel B power fluctuation', 'Reported by 40 residents', 'Urgent', '20 mins ago'),
      a('WO-7774', 'Plumbing', 'Aquatic centre shower leakage', 'Vendor visit scheduled', 'Pending', '3 hours ago'),
      a('WO-7769', 'AMC', 'Lift AMC renewal', 'Quote from 2 vendors received', 'Review', 'Yesterday')
    ],
    activity: [
      l('10:30 AM', 'Work order WO-7779 closed', 'Maintenance Team', 'WO-7779'),
      l('09:40 AM', 'Preventive check: DG sets', 'Electrical', 'PM-DG-10'),
      l('Yesterday', 'SLA breached on WO-7760', 'System', 'WO-7760', 'Warning')
    ]
  },

  // ---------------- E · Finance & Institutional Operations ----------------
  'fees-accounts': {
    action: 'Generate Invoice',
    kpis: [
      k('Collected this term', '₹8.42 Cr', 'Autumn 2026', '+12.4%'),
      k('Collection rate', '91%', 'Of billed fees', '+3%'),
      k('Outstanding dues', '₹74 L', '312 students', 'follow up', 'alert'),
      k('Reconciled', '₹1.28 Cr', 'SBIePay, this week', 'matched')
    ],
    chart: { title: 'Fee Collection', subtitle: '₹ lakh per month, online vs counter', series: ['Online', 'Counter'], base: 140, split: 0.15 },
    breakdown: { title: 'Collection by Fee Head', subtitle: '₹ lakh, this term', items: [['Tuition', 512], ['Hostel', 168], ['Examination', 74], ['Sports & activity', 52], ['Transport', 36]] },
    actions: [
      a('PAY-20481', 'Payment', 'Vendor payment for athletic track', 'Awaiting financial concurrence', 'Pending', '24 mins ago'),
      a('FEE-REF', 'Refund', '14 refund requests', 'Withdrawn admissions', 'Review', '3 hours ago'),
      a('FEE-REC', 'Reconciliation', '₹3.2 L unmatched in SBIePay', 'Transaction IDs missing', 'Urgent', 'Yesterday')
    ],
    activity: [
      l('10:42 AM', 'Payment request created', 'P. Singh, CA', 'PAY-20481'),
      l('09:30 AM', 'Daily SBIePay settlement imported', 'System', 'SET-0610'),
      l('Yesterday', 'Fee reminder SMS sent to 312 students', 'Notification service', 'NTF-FEE-6')
    ]
  },
  'budget-grants': {
    action: 'New Budget Head',
    kpis: [
      k('Annual budget', '₹96 Cr', 'FY 2026–27', '+8%'),
      k('Utilised', '48%', '₹46 Cr spent', 'on track'),
      k('Grant UCs due', '4', 'Utilisation certificates', 'deadline', 'alert'),
      k('Active grants', '19', 'Khelo India, UGC, state', '+3')
    ],
    chart: { title: 'Expenditure', subtitle: '₹ lakh per month, revenue vs capital', series: ['Revenue', 'Capital'], base: 720, split: 0.35 },
    breakdown: { title: 'Spend by Head', subtitle: '₹ crore, year to date', items: [['Salaries', 21], ['Sports infrastructure', 11], ['Academic', 6], ['Hostels', 5], ['Administration', 3]] },
    actions: [
      a('UC-KI-26', 'Utilisation', 'Khelo India grant UC due', 'Submit by 31 Oct', 'Urgent', '1 hour ago'),
      a('BUD-RE', 'Re-appropriation', '₹40 L from Admin to Sports', 'Finance Committee approval', 'Pending', '4 hours ago'),
      a('GRT-UGC', 'Grant', 'UGC research grant installment', 'Release letter received', 'Review', 'Yesterday')
    ],
    activity: [
      l('10:12 AM', 'Quarterly budget report generated', 'Finance Officer', 'RPT-BUD-Q2'),
      l('09:20 AM', 'Grant ledger updated', 'Accounts', 'GRT-LED-19'),
      l('Yesterday', 'Head overspend warning: Travel', 'System', 'BUD-WRN-4', 'Warning')
    ]
  },
  procurement: {
    action: 'Raise Indent',
    kpis: [
      k('Open indents', '46', 'Department requests', '+9'),
      k('POs issued', '₹3.6 Cr', 'This quarter', '+14%'),
      k('Tenders live', '5', 'On GeM and e-tender', 'closing', 'alert'),
      k('Vendors', '284', 'Empanelled', '+12')
    ],
    chart: { title: 'Purchase Orders', subtitle: 'Monthly count, GeM vs open tender', series: ['GeM', 'Open tender'], base: 60, split: 0.3 },
    breakdown: { title: 'Spend by Category', subtitle: '₹ lakh, this quarter', items: [['Sports equipment', 148], ['Lab equipment', 92], ['IT', 64], ['Furniture', 38], ['Services', 18]] },
    actions: [
      a('TND-112', 'Tender', 'Synthetic track resurfacing', 'Technical evaluation due', 'Urgent', '2 hours ago'),
      a('IND-889', 'Indent', 'Boxing rings ×2', 'Budget availability check', 'Pending', '4 hours ago'),
      a('PO-4410', 'PO', 'Gym equipment PO', 'Ready for Registrar signature', 'Review', 'Yesterday')
    ],
    activity: [
      l('10:08 AM', 'PO issued on GeM', 'Purchase Officer', 'PO-4412'),
      l('09:45 AM', 'Bid opened for tender TND-110', 'Purchase Committee', 'TND-110'),
      l('Yesterday', 'GeM API key regenerated', 'Dr. A. Sharma', 'SEC-KEY-819')
    ]
  },
  'hr-payroll': {
    action: 'Run Payroll',
    kpis: [
      k('Employees', '612', 'Teaching and non-teaching', '+8'),
      k('Payroll (Sept)', '₹4.1 Cr', 'Processed on time', 'paid'),
      k('Leave requests', '23', 'Awaiting approval', 'pending', 'alert'),
      k('Vacancies', '34', 'Sanctioned posts open', 'recruiting', 'muted')
    ],
    chart: { title: 'Payroll Cost', subtitle: '₹ lakh per month, teaching vs non-teaching', series: ['Teaching', 'Non-teaching'], base: 405, split: 0.38 },
    breakdown: { title: 'Staff by Category', subtitle: 'Current headcount', items: [['Faculty', 312], ['Coaches', 42], ['Administrative', 138], ['Technical', 72], ['Support', 48]] },
    actions: [
      a('LV-2291', 'Leave', '23 leave requests pending', '7 earned leave, 16 casual', 'Pending', '30 mins ago'),
      a('PAY-OCT', 'Payroll', 'October payroll draft', 'DA arrears to include', 'Review', '3 hours ago'),
      a('REC-COACH', 'Recruitment', 'Interview panel for 4 coaches', 'Dates to confirm', 'Urgent', 'Yesterday')
    ],
    activity: [
      l('10:20 AM', 'Joining recorded: Assistant Professor', 'HR Office', 'EMP-612'),
      l('09:05 AM', 'Salary slips emailed', 'System', 'PAY-SEP'),
      l('Yesterday', 'Biometric attendance sync delayed', 'System', 'HR-BIO-2', 'Warning')
    ]
  },
  'e-office': {
    action: 'Create File',
    kpis: [
      k('Files in movement', '418', 'Across 26 sections', '+31'),
      k('Closed this month', '296', 'Decisions recorded', '+9%'),
      k('Pending > 7 days', '38', 'Delayed files', 'escalate', 'alert'),
      k('Avg. turnaround', '3.4 days', 'Per file', '-0.6 d')
    ],
    chart: { title: 'Files Processed', subtitle: 'Monthly, created vs closed', series: ['Created', 'Closed'], base: 320, split: 0.47 },
    breakdown: { title: 'Pending by Section', subtitle: 'Files awaiting action', items: [['Registrar', 84], ['Finance', 72], ['Academic', 58], ['Sports', 46], ['Estate', 31]] },
    actions: [
      a('EF-5521', 'File', 'Convocation 2026 arrangements', 'With Registrar for 9 days', 'Urgent', '1 hour ago'),
      a('EF-5514', 'Noting', 'MoU with State Sports Dept.', 'Legal opinion attached', 'Pending', '4 hours ago'),
      a('EF-5509', 'Circular', 'Revised travel allowance rules', 'Draft for VC approval', 'Review', 'Yesterday')
    ],
    activity: [
      l('10:15 AM', 'File EF-5518 forwarded to Finance', 'Section Officer', 'EF-5518'),
      l('09:30 AM', 'Digital signature applied', 'Registrar', 'EF-5502'),
      l('Yesterday', '12 dak entries digitised', 'Dak Section', 'DAK-0605')
    ]
  },

  // ---------------- F · Campus Life & Student Services ----------------
  hostel: {
    action: 'Allot Room',
    kpis: [
      k('Residents', '1,846', 'In 8 hostels', '+42'),
      k('Occupancy', '94%', 'Of 1,960 beds', '+3%'),
      k('Complaints open', '27', 'Maintenance and mess', 'urgent 6', 'alert'),
      k('Mess satisfaction', '4.1 / 5', 'Monthly survey', '+0.2')
    ],
    chart: { title: 'Hostel Complaints', subtitle: 'Monthly, maintenance vs mess', series: ['Maintenance', 'Mess'], base: 70, split: 0.35 },
    breakdown: { title: 'Occupancy by Hostel', subtitle: 'Residents', items: [['Milkha Singh Boys', 420], ['Mary Kom Girls', 360], ['Dhyan Chand Boys', 340], ['P.T. Usha Girls', 310], ['International', 96]] },
    actions: [
      a('HST-B', 'Electrical', 'Hostel B power fluctuation', 'Work order WO-7781 raised', 'Urgent', '20 mins ago'),
      a('HST-ALT', 'Allotment', '18 room change requests', 'Mostly athletes moving to sports block', 'Pending', '3 hours ago'),
      a('HST-MESS', 'Mess', 'Athlete diet menu revision', 'Nutritionist recommendations', 'Review', 'Yesterday')
    ],
    activity: [
      l('10:00 AM', 'Visitor entries logged: 46', 'Hostel Warden', 'VIS-0610'),
      l('09:10 AM', 'Room 214 allotted', 'Hostel Office', 'HST-ALT-88'),
      l('Yesterday', 'Late entry recorded', 'Gate system', 'HST-GATE-12', 'Warning')
    ]
  },
  transport: {
    action: 'Add Route',
    kpis: [
      k('Bus passes', '1,124', 'Students and staff', '+38'),
      k('Routes', '22', '28 vehicles', '+1'),
      k('Vehicles in service', '25', '3 under maintenance', 'check', 'alert'),
      k('On-time trips', '93%', 'This month', '+2%')
    ],
    chart: { title: 'Trips Operated', subtitle: 'Monthly, campus routes vs event travel', series: ['Routes', 'Events'], base: 1300, split: 0.12 },
    breakdown: { title: 'Riders by Route', subtitle: 'Daily average', items: [['Route 1', 386], ['Route 2', 214], ['Route 3', 168], ['Route 4', 142], ['Route 5', 98]] },
    actions: [
      a('TRP-HKY', 'Event travel', 'Bus for hockey team to Ludhiana', 'Departure Saturday 6 AM', 'Urgent', '1 hour ago'),
      a('VEH-12', 'Fitness', 'Vehicle fitness certificate due', 'PB-11-CK-4412', 'Pending', '5 hours ago'),
      a('RTE-NEW', 'Route', 'New route request: Bahadurgarh', '46 students interested', 'Review', 'Yesterday')
    ],
    activity: [
      l('10:05 AM', 'GPS alert cleared on Route 7', 'Transport Office', 'GPS-7'),
      l('09:00 AM', '38 passes issued', 'Transport Office', 'PASS-0610'),
      l('Yesterday', 'Route 3 delayed 25 mins', 'GPS', 'RTE-3-DLY', 'Warning')
    ]
  },
  library: {
    action: 'Issue Book',
    kpis: [
      k('Collection', '48,210', 'Books, journals, e-resources', '+620'),
      k('Loans active', '2,364', 'Currently issued', '+5%'),
      k('Overdue', '186', 'Past due date', 'fines', 'alert'),
      k('E-resource sessions', '9,840', 'This month', '+18%')
    ],
    chart: { title: 'Circulation', subtitle: 'Monthly, print vs digital', series: ['Print', 'Digital'], base: 2900, split: 0.5 },
    breakdown: { title: 'Loans by Subject', subtitle: 'Active loans', items: [['Sports Science', 742], ['Physical Education', 610], ['Management', 412], ['Computer Science', 356], ['Humanities', 244]] },
    actions: [
      a('LIB-OVD', 'Overdue', '186 overdue loans', 'Send reminder and fine notices', 'Pending', '40 mins ago'),
      a('LIB-ACQ', 'Acquisition', '124 titles requested by faculty', 'Budget ₹4.6 L', 'Review', '4 hours ago'),
      a('LIB-SUB', 'Subscription', 'SPORTDiscus renewal', 'Expires 31 Oct', 'Urgent', 'Yesterday')
    ],
    activity: [
      l('10:18 AM', '62 books returned', 'Circulation Desk', 'LIB-RET-0610'),
      l('09:35 AM', 'New arrivals catalogued', 'Librarian', 'LIB-CAT-44'),
      l('Yesterday', 'RFID gate alarm', 'Security gate', 'LIB-GATE-3', 'Warning')
    ]
  },
  'placement-career': {
    action: 'Add Drive',
    kpis: [
      k('Students placed', '312', 'Batch 2026, so far', '+18%'),
      k('Recruiters', '64', 'Visited campus', '+11'),
      k('Offers awaiting response', '27', 'Expire this week', 'follow up', 'alert'),
      k('Median package', '₹5.8 LPA', 'Batch 2026', '+0.6')
    ],
    chart: { title: 'Offers Made', subtitle: 'Monthly, on-campus vs off-campus', series: ['On-campus', 'Off-campus'], base: 48, split: 0.3 },
    breakdown: { title: 'Placements by Sector', subtitle: 'Batch 2026', items: [['Sports management', 98], ['Fitness & wellness', 76], ['Education', 64], ['IT & analytics', 52], ['Government', 22]] },
    actions: [
      a('PLC-DEC', 'Drive', 'Decathlon recruitment drive', 'Confirm venue and shortlist', 'Urgent', '1 hour ago'),
      a('PLC-OFR', 'Offers', '27 offers pending acceptance', 'Deadline Friday', 'Pending', '3 hours ago'),
      a('PLC-INT', 'Internship', 'SAI internship nominations', '15 seats, 48 applicants', 'Review', 'Yesterday')
    ],
    activity: [
      l('10:22 AM', '8 offers released', 'Placement Cell', 'PLC-OFR-41'),
      l('09:15 AM', 'Resume workshop scheduled', 'Career Services', 'PLC-WS-6'),
      l('Yesterday', 'Recruiter registered', 'Recruiter portal', 'PLC-REC-64')
    ]
  },
  alumni: {
    action: 'Create Event',
    kpis: [
      k('Alumni registered', '8,640', 'In the directory', '+214'),
      k('Donations (FY)', '₹62 L', 'Scholarships and facilities', '+22%'),
      k('Profiles to verify', '96', 'New registrations', 'pending', 'alert'),
      k('Event RSVPs', '412', 'Alumni Meet 2026', '+120')
    ],
    chart: { title: 'Alumni Engagement', subtitle: 'Monthly, event attendance vs mentoring', series: ['Events', 'Mentoring'], base: 260, split: 0.4 },
    breakdown: { title: 'Alumni by Sector', subtitle: 'Where they work', items: [['Coaching', 2140], ['Teaching', 1980], ['Armed forces & police', 1420], ['Sports admin', 1180], ['Corporate', 920]] },
    actions: [
      a('ALM-MEET', 'Event', 'Alumni Meet 2026 logistics', 'Auditorium booking BKG-3391', 'Urgent', '30 mins ago'),
      a('ALM-VER', 'Verification', '96 profiles to verify', 'Match with degree records', 'Pending', '4 hours ago'),
      a('ALM-DON', 'Donation', '₹5 L scholarship pledge', 'Receipt and 80G certificate', 'Review', 'Yesterday')
    ],
    activity: [
      l('10:10 AM', 'Newsletter sent to 8,640 alumni', 'Alumni Office', 'ALM-NL-10'),
      l('09:25 AM', 'Donation received ₹50,000', 'Payment gateway', 'DON-2291'),
      l('Yesterday', 'Mentor matched with 12 students', 'Alumni Office', 'ALM-MNT-12')
    ]
  },

  // ---------------- G · Governance, Grievance & Compliance ----------------
  grievance: {
    action: 'Register Grievance',
    kpis: [
      k('Open cases', '14', 'SGRC, anti-ragging, POSH-ICC', '-3'),
      k('Resolved this year', '128', 'Within timeline', '94%'),
      k('Escalated', '2', 'To Proctorial Committee', 'urgent', 'alert'),
      k('Avg. resolution', '9 days', 'Target 15 days', '-2 d')
    ],
    chart: { title: 'Grievances Received', subtitle: 'Monthly, academic vs non-academic', series: ['Academic', 'Non-academic'], base: 14, split: 0.45 },
    breakdown: { title: 'Open Cases by Committee', subtitle: 'Current', items: [['SGRC', 6], ['Hostel', 4], ['Anti-ragging', 2], ['POSH-ICC', 1], ['Examination', 1]] },
    actions: [
      a('GRV-301', 'Escalation', 'Hostel grievance escalated', 'Proctorial Committee hearing', 'Urgent', '1 hour ago'),
      a('GRV-298', 'Hearing', 'SGRC hearing on evaluation', 'Schedule within 7 days', 'Pending', '4 hours ago'),
      a('GRV-294', 'Closure', 'Anti-ragging case closure report', 'Committee sign-off', 'Review', 'Yesterday')
    ],
    activity: [
      l('10:00 AM', 'Case GRV-296 resolved', 'SGRC', 'GRV-296'),
      l('09:20 AM', 'Anti-ragging affidavit drive', 'Dean Students', 'ARG-2026'),
      l('Yesterday', 'Case nearing deadline', 'System', 'GRV-292', 'Warning')
    ]
  },
  rti: {
    action: 'Log RTI Request',
    kpis: [
      k('Requests this year', '64', 'Under RTI Act 2005', '+9'),
      k('Disposed in time', '96%', 'Within 30 days', '+2%'),
      k('Nearing deadline', '3', 'Due within 48 hours', 'urgent', 'alert'),
      k('First appeals', '4', 'Pending with FAA', 'review', 'muted')
    ],
    chart: { title: 'RTI Requests', subtitle: 'Monthly, received vs disposed', series: ['Received', 'Disposed'], base: 6, split: 0.48 },
    breakdown: { title: 'Requests by Topic', subtitle: 'This year', items: [['Admissions', 21], ['Recruitment', 14], ['Finance', 12], ['Examinations', 10], ['Sports', 7]] },
    actions: [
      a('RTI-2611', 'Deadline', 'Recruitment records request', 'Due in 36 hours', 'Urgent', '10 mins ago'),
      a('RTI-2608', 'Transfer', 'Request on state sports policy', 'Transfer to Sports Department', 'Pending', '3 hours ago'),
      a('APL-04', 'First appeal', 'Appeal on admission merit list', 'Hearing with FAA', 'Review', 'Yesterday')
    ],
    activity: [
      l('10:05 AM', 'Reply dispatched for RTI-2604', 'PIO', 'RTI-2604'),
      l('09:40 AM', 'Information sought from Exam Cell', 'APIO', 'RTI-2609'),
      l('Yesterday', 'Quarterly RTI return filed', 'PIO', 'RTI-QR-2')
    ]
  },
  'iqac-accreditation': {
    action: 'Upload Evidence',
    kpis: [
      k('NAAC criteria', '7', 'Self-study report', '82% ready'),
      k('Evidence files', '1,412', 'Uploaded to repository', '+96'),
      k('Action items open', '18', 'From IQAC meetings', 'due', 'alert'),
      k('Feedback collected', '3,120', 'Students and stakeholders', '+640')
    ],
    chart: { title: 'Evidence Uploaded', subtitle: 'Monthly, documents vs data templates', series: ['Documents', 'Templates'], base: 180, split: 0.4 },
    breakdown: { title: 'SSR Readiness by Criterion', subtitle: 'Share complete', unit: '%', items: [['Curricular aspects', 92], ['Teaching-learning', 88], ['Research', 71], ['Infrastructure', 90], ['Student support', 84]] },
    actions: [
      a('IQAC-AI-18', 'Action item', 'Research publication data missing', 'Criterion 3, 4 departments', 'Urgent', '2 hours ago'),
      a('IQAC-AQAR', 'AQAR', 'AQAR 2025–26 draft', 'Review by IQAC coordinator', 'Pending', '5 hours ago'),
      a('IQAC-FB', 'Feedback', 'Employer feedback survey', 'Launch to 64 recruiters', 'Review', 'Yesterday')
    ],
    activity: [
      l('10:30 AM', '96 evidence files uploaded', 'Departments', 'IQAC-EV-96'),
      l('09:10 AM', 'IQAC meeting minutes published', 'IQAC Coordinator', 'IQAC-MOM-9'),
      l('Yesterday', 'Data template rejected', 'IQAC', 'IQAC-TPL-12', 'Warning')
    ]
  },
  'regulatory-reports': {
    action: 'Prepare Report',
    kpis: [
      k('Returns filed', '22', 'UGC, AISHE, NIRF this year', '+4'),
      k('On-time filing', '95%', 'Statutory deadlines', '+5%'),
      k('Due this month', '3', 'AISHE, NIRF, state return', 'deadline', 'alert'),
      k('Data completeness', '88%', 'Fields auto-filled from modules', '+9%')
    ],
    chart: { title: 'Reports Filed', subtitle: 'Monthly, central vs state', series: ['Central', 'State'], base: 4, split: 0.4 },
    breakdown: { title: 'Reports by Regulator', subtitle: 'This year', items: [['UGC', 8], ['AISHE', 4], ['NIRF', 3], ['State Govt.', 5], ['NAAC', 2]] },
    actions: [
      a('AISHE-26', 'Return', 'AISHE 2025–26 data upload', 'Due 20 Oct', 'Urgent', '1 hour ago'),
      a('NIRF-27', 'Ranking', 'NIRF data capture', 'Faculty and research sections', 'Pending', '4 hours ago'),
      a('UGC-SFS', 'Compliance', 'UGC self-financing course return', 'Registrar sign-off', 'Review', 'Yesterday')
    ],
    activity: [
      l('10:10 AM', 'Student data exported for AISHE', 'MIS Cell', 'RPT-AISHE'),
      l('09:30 AM', 'Compliance calendar updated', 'Registrar Office', 'CAL-COMP'),
      l('Yesterday', 'Validation errors in NIRF draft', 'System', 'NIRF-VAL', 'Warning')
    ]
  },

  // ---------------- Global Support ----------------
  helpdesk: {
    action: 'New Ticket',
    kpis: [
      k('Open tickets', '24', 'Hostel, Wi-Fi & LMS', '-5'),
      k('Resolved this week', '186', 'Closed tickets', '+12%'),
      k('High priority', '6', 'Need attention now', 'urgent', 'alert'),
      k('Avg. resolution', '4.2 h', 'This week', '-0.8 h')
    ],
    chart: { title: 'Tickets', subtitle: 'Monthly, raised vs resolved', series: ['Raised', 'Resolved'], base: 820, split: 0.48 },
    breakdown: { title: 'Open Tickets by Category', subtitle: 'Current queue', items: [['Wi-Fi & network', 9], ['Hostel', 6], ['LMS access', 4], ['Fee portal', 3], ['Email', 2]] },
    actions: [
      a('TCK-8830', 'Network', 'Wi-Fi down in Sports Complex', 'Affecting 3 halls', 'Urgent', '15 mins ago'),
      a('TCK-8826', 'LMS', 'Students cannot submit quiz', 'Exercise Physiology, Section A', 'Pending', '1 hour ago'),
      a('TCK-8819', 'Access', 'Email account for new faculty', '8 accounts to create', 'Review', 'Yesterday')
    ],
    activity: [
      l('09:48 AM', 'Ticket closed: Campus Wi-Fi credentials reissued', 'Sunita Verma', 'TCK-8812'),
      l('09:20 AM', '14 tickets auto-assigned', 'System', 'TCK-AUTO'),
      l('Yesterday', 'Ticket reopened by user', 'Student', 'TCK-8794', 'Warning')
    ]
  },
  'sla-management': {
    action: 'Define SLA',
    kpis: [
      k('SLA policies', '18', 'By ticket category', '+2'),
      k('Met this month', '94%', 'Within target time', '+3%'),
      k('Breaches', '11', 'This month', 'review', 'alert'),
      k('At risk now', '4', 'Close to breach', 'watch', 'muted')
    ],
    chart: { title: 'SLA Outcomes', subtitle: 'Monthly, met vs breached', series: ['Met', 'Breached'], base: 780, split: 0.06 },
    breakdown: { title: 'Breaches by Team', subtitle: 'This month', items: [['Network', 4], ['Maintenance', 3], ['Hostel', 2], ['Finance', 1], ['Academic', 1]] },
    actions: [
      a('SLA-NET', 'Breach', 'Network team: 4 breaches', 'Root-cause review', 'Urgent', '1 hour ago'),
      a('SLA-ESC', 'Escalation', 'Escalation matrix update', 'Add hostel wardens', 'Pending', '4 hours ago'),
      a('SLA-NEW', 'Policy', 'SLA for sports equipment requests', 'Proposed 48-hour target', 'Review', 'Yesterday')
    ],
    activity: [
      l('10:00 AM', 'SLA timer paused (awaiting user)', 'System', 'TCK-8826'),
      l('09:15 AM', 'Monthly SLA report generated', 'Support Lead', 'RPT-SLA-09'),
      l('Yesterday', 'SLA breached on WO-7760', 'System', 'WO-7760', 'Warning')
    ]
  },
  'knowledge-base': {
    action: 'Write Article',
    kpis: [
      k('Articles', '214', 'Published', '+9'),
      k('Views this month', '12,480', 'Self-service reads', '+21%'),
      k('Outdated articles', '17', 'Need review', 'update', 'alert'),
      k('Ticket deflection', '31%', 'Solved without a ticket', '+4%')
    ],
    chart: { title: 'Article Views', subtitle: 'Monthly, students vs staff', series: ['Students', 'Staff'], base: 10500, split: 0.3 },
    breakdown: { title: 'Top Articles', subtitle: 'Views this month', items: [['Connect to campus Wi-Fi', 2410], ['Pay fees online', 1980], ['Reset LMS password', 1640], ['Book a sports facility', 1120], ['Apply for hostel', 880]] },
    actions: [
      a('KB-REV', 'Review', '17 articles need review', 'Older than 12 months', 'Pending', '2 hours ago'),
      a('KB-NEW', 'Gap', 'No article for exam re-evaluation', '22 tickets on this topic', 'Urgent', '5 hours ago'),
      a('KB-TRN', 'Translation', 'Regional-language versions of top 10', 'Translator assigned', 'Review', 'Yesterday')
    ],
    activity: [
      l('10:12 AM', 'Article updated: Fee portal guide', 'Support Staff', 'KB-114'),
      l('09:30 AM', 'Article published: Facility booking', 'Support Lead', 'KB-214'),
      l('Yesterday', 'Low rating on Wi-Fi article', 'Users', 'KB-021', 'Warning')
    ]
  },
  'incident-management': {
    action: 'Report Incident',
    kpis: [
      k('Open incidents', '5', 'Under investigation', '-2'),
      k('Resolved this month', '23', 'Closed with RCA', '+4'),
      k('Major incidents', '1', 'Service-wide impact', 'active', 'alert'),
      k('Mean time to restore', '1.8 h', 'This month', '-0.5 h')
    ],
    chart: { title: 'Incidents', subtitle: 'Monthly, minor vs major', series: ['Minor', 'Major'], base: 24, split: 0.12 },
    breakdown: { title: 'Incidents by Service', subtitle: 'This quarter', items: [['Network', 21], ['Power', 12], ['LMS', 8], ['Fee portal', 5], ['Email', 3]] },
    actions: [
      a('INC-114', 'Major', 'Sports Complex network outage', 'Fibre cut, vendor on site', 'Urgent', '15 mins ago'),
      a('PRB-022', 'Problem', 'Recurring LMS slowness', 'RCA due this week', 'Pending', '4 hours ago'),
      a('INC-110', 'Post-mortem', 'Fee portal downtime review', 'Report ready for sign-off', 'Review', 'Yesterday')
    ],
    activity: [
      l('10:05 AM', 'Incident INC-114 declared major', 'Support Lead', 'INC-114'),
      l('09:20 AM', 'Problem record PRB-022 linked', 'Support Staff', 'PRB-022'),
      l('Yesterday', 'Unauthorized download attempt blocked', 'RBAC policy', 'HR-PAYROLL-CONFIDENTIAL', 'Failed')
    ]
  },
  'amc-vendor-support': {
    action: 'Add Contract',
    kpis: [
      k('Active AMCs', '46', 'Equipment and services', '+3'),
      k('Annual value', '₹2.9 Cr', 'AMC spend', '+6%'),
      k('Expiring in 30 days', '5', 'Renewal needed', 'renew', 'alert'),
      k('Vendor SLA met', '91%', 'Service visits on time', '+2%')
    ],
    chart: { title: 'Service Visits', subtitle: 'Monthly, scheduled vs breakdown calls', series: ['Scheduled', 'Breakdown'], base: 120, split: 0.3 },
    breakdown: { title: 'AMC Value by Category', subtitle: '₹ lakh per year', items: [['Sports equipment', 96], ['IT & network', 82], ['Lifts & HVAC', 54], ['Lab equipment', 38], ['Security systems', 20]] },
    actions: [
      a('AMC-LIFT', 'Renewal', 'Lift AMC expires 30 Oct', 'Quotes from 2 vendors received', 'Urgent', '1 hour ago'),
      a('AMC-GYM', 'Service', 'Gym equipment quarterly service', 'Vendor visit to confirm', 'Pending', '5 hours ago'),
      a('AMC-PEN', 'Penalty', 'Penalty for missed visits', 'Network vendor, 3 visits', 'Review', 'Yesterday')
    ],
    activity: [
      l('10:20 AM', 'Service report uploaded', 'Vendor portal', 'AMC-SR-221'),
      l('09:10 AM', 'Contract renewed: CCTV AMC', 'Purchase Officer', 'AMC-CCTV'),
      l('Yesterday', 'Vendor missed scheduled visit', 'System', 'AMC-MISS-3', 'Warning')
    ]
  },

  // ---------------- Practice ----------------
  portfolio: {
    action: 'New Portfolio',
    kpis: [
      k('Active portfolios', '1,126', 'Learners with a live portfolio', '+14%'),
      k('Items added (30 days)', '3,480', 'Artworks, showreels, designs, papers', '+9.2%'),
      k('Awaiting review', '64', 'Submitted to mentors', '18 overdue', 'alert'),
      k('Published', '812', 'Shared on public profile', '72%', 'muted')
    ],
    chart: { title: 'Portfolio Items Added', subtitle: 'Monthly, creative works vs research & teaching', series: ['Creative works', 'Research & teaching'], base: 290, split: 0.35 },
    breakdown: { title: 'Portfolio Types', subtitle: 'Items by type', items: [['Artworks & designs', 1240], ['Showreels & media', 860], ['Repertoire', 540], ['Teaching portfolios', 420], ['Research portfolios', 380]] },
    actions: [
      a('PRT-412', 'Review', 'Final-year design portfolio', 'Mentor review due before jury', 'Urgent', '30 mins ago'),
      a('PRT-409', 'Showreel', 'Film showreel upload too large', 'Re-encode and resubmit requested', 'Pending', '3 hours ago'),
      a('PRT-401', 'Publish', '12 portfolios ready to publish', 'Consent forms received', 'Review', 'Yesterday')
    ],
    activity: [
      l('10:20 AM', 'Showreel added to performing arts portfolio', 'Student', 'PRT-415'),
      l('09:05 AM', 'Mentor feedback posted on design portfolio', 'Faculty', 'PRT-412'),
      l('Yesterday', 'Portfolio published to public profile', 'Student', 'PRT-398')
    ]
  },
  projects: {
    action: 'New Project',
    kpis: [
      k('Active projects', '214', 'Capstone, film, research, live business', '+18'),
      k('Teams', '186', 'Average 3.4 members', '+11'),
      k('Milestones due (7 days)', '42', 'Across all projects', '9 at risk', 'alert'),
      k('Completed this term', '58', 'Final review passed', '+22%')
    ],
    chart: { title: 'Milestones Completed', subtitle: 'Monthly, on time vs late', series: ['On time', 'Late'], base: 120, split: 0.18 },
    breakdown: { title: 'Projects by Type', subtitle: 'Active this term', items: [['Capstone', 72], ['Research', 54], ['Live business', 38], ['Film', 29], ['Artwork', 21]] },
    actions: [
      a('PRJ-221', 'Milestone', 'Capstone mid-term review', '9 teams missing prototype demo', 'Urgent', '1 hour ago'),
      a('PRJ-217', 'Team change', 'Member transfer request', 'Student asked to move between teams', 'Pending', '4 hours ago'),
      a('PRJ-210', 'Final review', 'Live business pitch panel', 'Panel of 3 to be confirmed', 'Review', 'Yesterday')
    ],
    activity: [
      l('10:05 AM', 'Milestone "Prototype" marked complete', 'Team Lead', 'PRJ-219'),
      l('09:30 AM', 'Supervisor feedback added', 'Faculty', 'PRJ-221'),
      l('Yesterday', 'New film project created', 'Student', 'PRJ-224')
    ]
  },
  'selection-process': {
    action: 'Schedule Round',
    kpis: [
      k('Open selections', '12', 'Auditions, squads, jury, moot court', '+3'),
      k('Applicants', '846', 'Across open selections', '+21%'),
      k('Rounds this week', '9', 'Auditions and jury rounds', '3 today', 'muted'),
      k('Selected', '132', 'Final lists published', '15.6%')
    ],
    chart: { title: 'Applicants per Month', subtitle: 'Shortlisted vs not shortlisted', series: ['Shortlisted', 'Not shortlisted'], base: 140, split: 0.55 },
    breakdown: { title: 'Selection Funnel', subtitle: 'Current cycle', items: [['Applications', 846], ['Shortlisted', 384], ['Auditions / jury rounds', 241], ['Team selection', 168], ['Supervisor allocation', 132]], footer: ['Selection rate', '15.6%'] },
    actions: [
      a('SEL-118', 'Jury round', 'Theatre casting panel', 'Two jurors not yet confirmed', 'Urgent', '45 mins ago'),
      a('SEL-115', 'Squad', 'Inter-university football squad', 'Coach shortlist awaits approval', 'Pending', '2 hours ago'),
      a('SEL-111', 'Allocation', 'Research supervisor allocation', '18 students without supervisor', 'Review', 'Yesterday')
    ],
    activity: [
      l('10:15 AM', 'Audition slots published', 'Coordinator', 'SEL-120'),
      l('09:10 AM', 'Moot court team list finalised', 'Faculty', 'SEL-117'),
      l('Yesterday', 'Shortlist exported for jury', 'Coordinator', 'SEL-116')
    ]
  },
  productions: {
    action: 'New Production',
    kpis: [
      k('Upcoming events', '18', 'Next 30 days', '+5'),
      k('Registrations', '2,340', 'Participants and audience', '+26%'),
      k('Venues booked', '11', 'Halls, studios, auditoria', '2 pending', 'alert'),
      k('Completed this term', '34', 'Performances, exhibitions, hackathons', '+8')
    ],
    chart: { title: 'Event Attendance', subtitle: 'Monthly, participants vs audience', series: ['Participants', 'Audience'], base: 900, split: 0.6 },
    breakdown: { title: 'Events by Type', subtitle: 'This academic year', items: [['Performances', 22], ['Exhibitions', 16], ['Competitions', 14], ['Hackathons', 9], ['Screenings', 8], ['Conferences', 6]] },
    actions: [
      a('PRD-061', 'Venue', 'Annual showcase main hall', 'Booking clash with convocation rehearsal', 'Urgent', '1 hour ago'),
      a('PRD-058', 'Budget', 'Hackathon prize budget', 'Finance approval pending', 'Pending', '5 hours ago'),
      a('PRD-055', 'Programme', 'Film screening schedule', 'Final running order to review', 'Review', 'Yesterday')
    ],
    activity: [
      l('10:30 AM', 'Exhibition registrations opened', 'Coordinator', 'PRD-063'),
      l('09:20 AM', 'Recital programme published', 'Faculty', 'PRD-060'),
      l('Yesterday', 'Conference speakers confirmed', 'Coordinator', 'PRD-057')
    ]
  },
  'field-training': {
    action: 'New Placement',
    kpis: [
      k('Learners on placement', '486', 'Clinical, teaching, farm, internships, court', '+12%'),
      k('Host sites', '74', 'Hospitals, schools, farms, firms, courts', '+6'),
      k('Logbooks to verify', '58', 'Supervisor sign-off pending', '14 overdue', 'alert'),
      k('Completed hours', '38,200', 'This term', '+9.8%')
    ],
    chart: { title: 'Placement Hours Logged', subtitle: 'Monthly, verified vs pending', series: ['Verified', 'Pending'], base: 6200, split: 0.22 },
    breakdown: { title: 'Placements by Type', subtitle: 'Current term', items: [['Internships', 162], ['Clinical rotations', 118], ['Teaching practice', 96], ['Farm rotations', 64], ['Court visits', 46]] },
    actions: [
      a('FLD-204', 'Logbook', 'Clinical rotation logbooks', '14 entries past the 7-day window', 'Urgent', '40 mins ago'),
      a('FLD-199', 'Host site', 'New internship partner', 'MoU awaiting signature', 'Pending', '3 hours ago'),
      a('FLD-196', 'Evaluation', 'Teaching practice assessments', 'Mentor scores to review', 'Review', 'Yesterday')
    ],
    activity: [
      l('10:00 AM', 'Placement assigned to host school', 'Coordinator', 'FLD-207'),
      l('08:50 AM', 'Logbook verified by supervisor', 'Faculty', 'FLD-203'),
      l('Yesterday', 'Farm rotation schedule published', 'Coordinator', 'FLD-201')
    ]
  },
  'skill-progress': {
    action: 'New Assessment',
    kpis: [
      k('Learners tracked', '2,140', 'With at least one assessment', '+16%'),
      k('Assessments (30 days)', '5,860', 'Technique, fitness, practicum, competencies', '+11%'),
      k('Improving', '68%', 'Score up since last term', '+4 pts'),
      k('Needs attention', '146', 'Declining two assessments in a row', 'review', 'alert')
    ],
    chart: { title: 'Assessments Recorded', subtitle: 'Monthly, improving vs needs attention', series: ['Improving', 'Needs attention'], base: 820, split: 0.2 },
    breakdown: { title: 'Assessments by Area', subtitle: 'Last 30 days', items: [['Technique', 1980], ['Competencies', 1460], ['Fitness', 1320], ['Practicum', 1100]] },
    actions: [
      a('SKL-330', 'Rubric', 'Competency rubric update', 'New level descriptors need approval', 'Pending', '2 hours ago'),
      a('SKL-326', 'Follow-up', '146 learners declining', 'Assign mentors for follow-up', 'Urgent', '3 hours ago'),
      a('SKL-321', 'Review', 'End-of-term progress reports', 'Ready for faculty review', 'Review', 'Yesterday')
    ],
    activity: [
      l('10:25 AM', 'Fitness test results imported', 'Coach', 'SKL-333'),
      l('09:15 AM', 'Practicum assessment recorded', 'Faculty', 'SKL-331'),
      l('Yesterday', 'Skill framework published', 'Coordinator', 'SKL-328')
    ]
  },

  // ---------------- Shared platform services ----------------
  identity: {
    action: 'Add User',
    kpis: [
      k('User accounts', '4,826', 'Across all roles', '+3.1%'),
      k('Roles in use', '16', 'From the academy profile', 'muted', 'muted'),
      k('Sign-ins (7 days)', '18,420', 'Email and password', '+6.4%'),
      k('Failed sign-ins', '212', 'Last 7 days', 'review', 'alert')
    ],
    chart: { title: 'Sign-ins', subtitle: 'Monthly, successful vs failed', series: ['Successful', 'Failed'], base: 72000, split: 0.03 },
    breakdown: { title: 'Users by Role', subtitle: 'Top roles', items: [['Student', 3414], ['Athlete', 428], ['Faculty / Instructor', 312], ['Coach', 42], ['Finance Staff', 8]] },
    actions: [
      a('IDN-090', 'Accounts', '28 accounts never signed in', 'Invited more than 14 days ago', 'Review', '2 hours ago'),
      a('IDN-087', 'Failed sign-ins', 'Repeated failures on one account', 'Check with the user', 'Urgent', '3 hours ago'),
      a('IDN-084', 'Role change', 'HoD role requested for faculty', 'Organisation admin to confirm', 'Pending', 'Yesterday')
    ],
    activity: [
      l('10:40 AM', 'User account created', 'Organisation Admin', 'IDN-093'),
      l('09:55 AM', 'Role assigned: Coach', 'Organisation Admin', 'IDN-092'),
      l('Yesterday', 'Account signed in for the first time', 'User', 'IDN-089')
    ]
  },
  tenancy: {
    action: 'View Organisation',
    kpis: [
      k('Organisations', '38', 'Registered on the platform', '+4'),
      k('Pending approval', '3', 'Academic packages awaiting super admin', 'review', 'alert'),
      k('Active', '31', 'Can sign in', '81.6%'),
      k('Academy types in use', '9', 'Of 15 profiles', 'muted', 'muted')
    ],
    chart: { title: 'Registrations', subtitle: 'Monthly, approved vs pending', series: ['Approved', 'Pending'], base: 6, split: 0.25 },
    breakdown: { title: 'Organisations by Academy Type', subtitle: 'All organisations', items: [['Sports College', 11], ['Engineering College', 8], ['Arts Academy', 6], ['Law College', 5], ['Medical College', 4]] },
    actions: [
      a('TEN-031', 'Approval', 'Academic package awaiting approval', 'Registered and email verified', 'Urgent', '1 hour ago'),
      a('TEN-028', 'Package change', 'Change of academy type requested', 'Super admin to approve', 'Pending', '6 hours ago'),
      a('TEN-025', 'Override', 'Module outside plan requested', 'Review entitlement override', 'Review', 'Yesterday')
    ],
    activity: [
      l('10:12 AM', 'tenancy.organisation.registered', 'System', 'TEN-033'),
      l('09:40 AM', 'tenancy.organisation.approved', 'Super Admin', 'TEN-030'),
      l('Yesterday', 'tenancy.entitlement.changed', 'Organisation Admin', 'TEN-027')
    ]
  },
  billing: {
    action: 'View Plans',
    kpis: [
      k('Subscriptions', '38', 'One per organisation', '+4'),
      k('On trial', '9', 'Trial plan', '3 ending soon', 'alert'),
      k('Paid plans', '29', 'Standard and premium', '76.3%'),
      k('Upgrades (30 days)', '5', 'Trial to paid', '+2')
    ],
    chart: { title: 'Subscriptions', subtitle: 'Monthly, paid vs trial', series: ['Paid', 'Trial'], base: 30, split: 0.25 },
    breakdown: { title: 'Organisations by Plan', subtitle: 'Current subscriptions', items: [['Standard', 18], ['Premium', 11], ['Trial', 9]] },
    actions: [
      a('BIL-044', 'Trial', '3 trials end this week', 'Reminders sent to organisation admins', 'Urgent', '2 hours ago'),
      a('BIL-041', 'Upgrade', 'Upgrade to premium requested', 'Payment adapter not configured', 'Pending', '5 hours ago'),
      a('BIL-038', 'Plan', 'Standard plan limits update', 'Review student limit', 'Review', 'Yesterday')
    ],
    activity: [
      l('10:05 AM', 'billing.subscription.started', 'System', 'BIL-046'),
      l('09:22 AM', 'billing.subscription.upgraded', 'Organisation Admin', 'BIL-043'),
      l('Yesterday', 'billing.trial.expired', 'System', 'BIL-040', 'Warning')
    ]
  },
  workflow: {
    action: 'New Workflow',
    kpis: [
      k('Active workflows', '24', 'Approval and state machines', '+3'),
      k('Items in flight', '186', 'Awaiting a step', '+12'),
      k('Overdue steps', '17', 'Past their SLA', 'escalate', 'alert'),
      k('Completed (30 days)', '1,420', 'Approvals closed', '+8.6%')
    ],
    chart: { title: 'Approvals Completed', subtitle: 'Monthly, within SLA vs late', series: ['Within SLA', 'Late'], base: 1300, split: 0.08 },
    breakdown: { title: 'Pending by Workflow', subtitle: 'Items awaiting action', items: [['Leave approval', 48], ['Purchase indent', 36], ['Fee waiver', 29], ['Result moderation', 24], ['File movement', 19]] },
    actions: [
      a('WFL-512', 'Escalation', '17 steps past SLA', 'Escalate to next approver', 'Urgent', '20 mins ago'),
      a('WFL-509', 'Delegation', 'HoD on leave for 5 days', 'Delegate approvals', 'Pending', '2 hours ago'),
      a('WFL-503', 'Design', 'New hostel allotment flow', 'Review state machine', 'Review', 'Yesterday')
    ],
    activity: [
      l('10:18 AM', 'Leave request approved', 'Department Admin', 'WFL-515'),
      l('09:44 AM', 'Purchase indent moved to finance', 'System', 'WFL-514'),
      l('Yesterday', 'Workflow version published', 'Admin', 'WFL-506')
    ]
  },
  audit: {
    action: 'Export Audit Log',
    kpis: [
      k('Events (30 days)', '48,200', 'State-changing actions', '+5.2%'),
      k('Modules writing', '6', 'Sending audit events', 'muted', 'muted'),
      k('Admin actions', '312', 'Super admin and org admin', '+18'),
      k('Impersonation sessions', '4', 'All audited', 'review', 'alert')
    ],
    chart: { title: 'Audit Events', subtitle: 'Monthly, user vs system', series: ['User', 'System'], base: 42000, split: 0.3 },
    breakdown: { title: 'Events by Service', subtitle: 'Last 30 days', items: [['identity', 18400], ['tenancy', 9200], ['billing', 6100], ['workflow', 8300], ['documents', 6200]] },
    actions: [
      a('AUD-210', 'Impersonation', 'Super admin session reviewed', 'Confirm reason recorded', 'Review', '1 hour ago'),
      a('AUD-206', 'Retention', 'Retention policy to set', 'Decide retention period per event type', 'Pending', '1 day ago'),
      a('AUD-201', 'Export', 'Quarterly audit export', 'For governance review', 'Pending', '2 days ago')
    ],
    activity: [
      l('10:42 AM', 'tenancy.impersonation.started', 'Super Admin', 'AUD-212'),
      l('10:11 AM', 'identity.user.created', 'Organisation Admin', 'AUD-211'),
      l('Yesterday', 'tenancy.entitlement.changed', 'Organisation Admin', 'AUD-208')
    ]
  },
  notification: {
    action: 'New Template',
    kpis: [
      k('Messages (30 days)', '62,400', 'Email, SMS, WhatsApp, push, in-app', '+12%'),
      k('Delivered', '98.4%', 'Across channels', '+0.6 pts'),
      k('Templates', '84', 'Active templates', '+6'),
      k('Failed', '1,010', 'Bounced or undelivered', 'review', 'alert')
    ],
    chart: { title: 'Messages Sent', subtitle: 'Monthly, delivered vs failed', series: ['Delivered', 'Failed'], base: 58000, split: 0.02 },
    breakdown: { title: 'Messages by Channel', subtitle: 'Last 30 days', items: [['Email', 24800], ['In-app', 16200], ['SMS', 11400], ['WhatsApp', 7600], ['Push', 2400]] },
    actions: [
      a('NTF-140', 'Bounces', 'Email bounces from one domain', '412 bounces since Monday', 'Urgent', '1 hour ago'),
      a('NTF-137', 'Template', 'Fee reminder template', 'Approval of new wording', 'Pending', '4 hours ago'),
      a('NTF-133', 'Opt-outs', 'SMS opt-out requests', '26 requests to process', 'Review', 'Yesterday')
    ],
    activity: [
      l('10:30 AM', 'Trial expiry reminder sent', 'System', 'NTF-143'),
      l('09:15 AM', 'Exam schedule broadcast', 'Examination Staff', 'NTF-142'),
      l('Yesterday', 'Template updated: hostel notice', 'Admin', 'NTF-139')
    ]
  },
  documents: {
    action: 'Upload Document',
    kpis: [
      k('Documents', '1.86 L', 'Stored across modules', '+4.1%'),
      k('Storage used', '612 GB', 'Of plan limit', '61%', 'muted'),
      k('Uploads (30 days)', '9,840', 'New files and versions', '+7.3%'),
      k('Access requests', '23', 'Awaiting owner approval', 'review', 'alert')
    ],
    chart: { title: 'Uploads', subtitle: 'Monthly, new files vs new versions', series: ['New files', 'New versions'], base: 8600, split: 0.3 },
    breakdown: { title: 'Storage by Module', subtitle: 'GB used', items: [['Admissions', 182], ['Training & video', 164], ['Student information', 96], ['E-Office', 88], ['LMS', 82]] },
    actions: [
      a('DOC-301', 'Access', '23 access requests', 'Owners to approve or deny', 'Pending', '2 hours ago'),
      a('DOC-298', 'Storage', 'Video storage growing fast', 'Review retention for raw footage', 'Review', '5 hours ago'),
      a('DOC-294', 'Scan', 'Unreadable scanned certificates', '41 files to re-scan', 'Urgent', 'Yesterday')
    ],
    activity: [
      l('10:22 AM', 'New version of fee circular', 'Finance Staff', 'DOC-304'),
      l('09:48 AM', 'Batch upload: hall tickets', 'Examination Staff', 'DOC-303'),
      l('Yesterday', 'Folder permissions changed', 'Admin', 'DOC-299')
    ]
  },
  reporting: {
    action: 'New Report',
    kpis: [
      k('Reports', '146', 'MIS and dashboards', '+9'),
      k('Runs (30 days)', '4,320', 'Scheduled and on demand', '+14%'),
      k('Scheduled', '38', 'Delivered by email', 'muted', 'muted'),
      k('Failed runs', '12', 'Last 30 days', 'review', 'alert')
    ],
    chart: { title: 'Report Runs', subtitle: 'Monthly, scheduled vs on demand', series: ['Scheduled', 'On demand'], base: 3900, split: 0.45 },
    breakdown: { title: 'Most Used Reports', subtitle: 'Runs in the last 30 days', items: [['Attendance by department', 620], ['Fee collection', 540], ['Results summary', 410], ['Admissions funnel', 380], ['Hostel occupancy', 210]] },
    actions: [
      a('RPT-077', 'Failure', 'Nightly fee report failed', 'Source data late', 'Urgent', '1 hour ago'),
      a('RPT-074', 'Request', 'New NAAC criterion report', 'Requested by IQAC', 'Pending', '6 hours ago'),
      a('RPT-070', 'Schedule', 'Weekly management pack', 'Recipients to confirm', 'Review', 'Yesterday')
    ],
    activity: [
      l('10:01 AM', 'Attendance report generated', 'Department Admin', 'RPT-080'),
      l('08:30 AM', 'Management pack emailed', 'System', 'RPT-079'),
      l('Yesterday', 'Report definition updated', 'Admin', 'RPT-072')
    ]
  },
  search: {
    action: 'Rebuild Index',
    kpis: [
      k('Searches (30 days)', '84,600', 'Across modules', '+18%'),
      k('Indexed records', '6.2 L', 'Students, files, notices, more', '+3.4%'),
      k('Zero-result searches', '4.1%', 'No match found', '-0.8 pts'),
      k('Index lag', '42 s', 'Average time to searchable', 'muted', 'muted')
    ],
    chart: { title: 'Searches', subtitle: 'Monthly, found vs no result', series: ['Found', 'No result'], base: 78000, split: 0.04 },
    breakdown: { title: 'Searches by Area', subtitle: 'Last 30 days', items: [['Students', 31200], ['Documents', 18400], ['Notices', 14600], ['Courses', 11200], ['Staff', 9200]] },
    actions: [
      a('SRC-021', 'Synonyms', 'Top zero-result terms', 'Add synonyms for 14 terms', 'Review', '2 hours ago'),
      a('SRC-019', 'Index', 'Library catalogue not indexed', 'Connect once library is enabled', 'Pending', '1 day ago'),
      a('SRC-016', 'Lag', 'Index lag spike', 'Investigate during peak', 'Urgent', 'Yesterday')
    ],
    activity: [
      l('10:10 AM', 'Notices index refreshed', 'System', 'SRC-024'),
      l('09:00 AM', 'Synonym list updated', 'Admin', 'SRC-022'),
      l('Yesterday', 'Full re-index completed', 'System', 'SRC-018')
    ]
  },
  scheduler: {
    action: 'New Job',
    kpis: [
      k('Scheduled jobs', '64', 'Cron and one-off', '+5'),
      k('Runs (24 hours)', '1,920', 'Jobs executed', '+2.1%'),
      k('Success rate', '99.2%', 'Last 7 days', '+0.3 pts'),
      k('Failed runs', '15', 'Last 7 days', 'review', 'alert')
    ],
    chart: { title: 'Job Runs', subtitle: 'Monthly, succeeded vs failed', series: ['Succeeded', 'Failed'], base: 56000, split: 0.01 },
    breakdown: { title: 'Jobs by Type', subtitle: 'Active jobs', items: [['Reminders', 22], ['Report delivery', 14], ['Data sync', 12], ['Clean-up', 9], ['Alerts', 7]] },
    actions: [
      a('SCH-061', 'Failure', 'Trial expiry job failed twice', 'Check retry settings', 'Urgent', '1 hour ago'),
      a('SCH-058', 'New job', 'Daily attendance alert', 'Approve schedule', 'Pending', '4 hours ago'),
      a('SCH-055', 'Overlap', 'Two jobs at 02:00', 'Stagger to reduce load', 'Review', 'Yesterday')
    ],
    activity: [
      l('10:00 AM', 'Fee reminder job completed', 'System', 'SCH-064'),
      l('06:00 AM', 'Nightly clean-up completed', 'System', 'SCH-063'),
      l('Yesterday', 'Trial expiry job retried', 'System', 'SCH-060', 'Warning')
    ]
  },
  'event-bus': {
    action: 'View Contracts',
    kpis: [
      k('Events (24 hours)', '1.12 L', 'Published between modules', '+6.8%'),
      k('Event types', '29', 'Defined in contracts/events.yaml', '+6'),
      k('Consumers', '11', 'Subscribed modules', 'muted', 'muted'),
      k('Dead letters', '18', 'Failed after retries', 'review', 'alert')
    ],
    chart: { title: 'Events Published', subtitle: 'Monthly, delivered vs retried', series: ['Delivered', 'Retried'], base: 3.2e6, split: 0.02 },
    breakdown: { title: 'Events by Publisher', subtitle: 'Last 24 hours', items: [['identity', 38200], ['tenancy', 24600], ['billing', 18300], ['workflow', 17900], ['notification', 13000]] },
    actions: [
      a('EVB-033', 'Dead letters', '18 events failed delivery', 'Inspect and replay', 'Urgent', '45 mins ago'),
      a('EVB-030', 'Contract', 'New event type proposed', 'training-video-analysis.video.tagged', 'Review', '3 hours ago'),
      a('EVB-027', 'Consumer', 'Slow consumer lag', 'Reporting consumer behind by 4 min', 'Pending', 'Yesterday')
    ],
    activity: [
      l('10:35 AM', 'tenancy.entitlement.changed delivered', 'System', 'EVB-036'),
      l('10:02 AM', 'billing.subscription.started delivered', 'System', 'EVB-035'),
      l('Yesterday', 'Dead-letter replay completed', 'Admin', 'EVB-029')
    ]
  },
  'integration-hub': {
    action: 'Add Adapter',
    kpis: [
      k('Adapters', '8', 'Registered integrations', 'muted', 'muted'),
      k('Exchanges (30 days)', '24,600', 'XML, JSON and CSV files', '+9.5%'),
      k('Webhooks', '14', 'Inbound endpoints', '+2'),
      k('Failed exchanges', '37', 'Retry queue', 'review', 'alert')
    ],
    chart: { title: 'Data Exchanges', subtitle: 'Monthly, succeeded vs retried', series: ['Succeeded', 'Retried'], base: 22000, split: 0.05 },
    breakdown: { title: 'Exchanges by Adapter', subtitle: 'Last 30 days', items: [['Email / SMS / WhatsApp', 11200], ['SBIePay', 5400], ['DigiLocker', 3100], ['Government portals', 2600], ['Video conferencing', 2300]] },
    actions: [
      a('INT-052', 'Retry', '37 exchanges in retry queue', 'Government portal timeouts', 'Urgent', '1 hour ago'),
      a('INT-049', 'Credentials', 'API key rotation due', 'Payment gateway key expires soon', 'Pending', '5 hours ago'),
      a('INT-046', 'Mapping', 'AISHE CSV mapping change', 'Review new column layout', 'Review', 'Yesterday')
    ],
    activity: [
      l('10:20 AM', 'DigiLocker batch exchanged', 'System', 'INT-055'),
      l('09:30 AM', 'Webhook endpoint added', 'Admin', 'INT-054'),
      l('Yesterday', 'Retry batch processed', 'System', 'INT-050', 'Warning')
    ]
  },
  'api-gateway': {
    action: 'View Routes',
    kpis: [
      k('Requests (24 hours)', '3.4 L', 'Through the gateway', '+7.2%'),
      k('Routes', '126', 'Across modules', '+14'),
      k('p95 latency', '186 ms', 'Last 24 hours', '-12 ms'),
      k('Rejected requests', '2,140', 'Outside entitlement or rate limit', 'review', 'alert')
    ],
    chart: { title: 'Requests', subtitle: 'Monthly, allowed vs rejected', series: ['Allowed', 'Rejected'], base: 9.6e6, split: 0.01 },
    breakdown: { title: 'Requests by Service', subtitle: 'Last 24 hours', items: [['identity', 112000], ['tenancy', 64000], ['admissions', 58000], ['lms', 52000], ['billing', 54000]] },
    actions: [
      a('GTW-071', 'Rate limit', 'One client hitting limits', 'Raise limit or contact organisation', 'Review', '1 hour ago'),
      a('GTW-068', 'Route', 'New module routes to publish', 'Skill progress API', 'Pending', '6 hours ago'),
      a('GTW-064', 'Latency', 'p95 spike at 09:00', 'Investigate peak load', 'Urgent', 'Yesterday')
    ],
    activity: [
      l('10:45 AM', 'Route table reloaded', 'System', 'GTW-074'),
      l('09:05 AM', 'Rate limit raised for one organisation', 'Admin', 'GTW-073'),
      l('Yesterday', 'Entitlement rejections reviewed', 'Admin', 'GTW-066')
    ]
  },

  // ---------------- Integrations ----------------
  'payment-sbiepay': {
    action: 'Test Connection',
    kpis: [
      k('Transactions (30 days)', '8,420', 'Initiated through SBIePay', '+11%'),
      k('Collected', '₹4.86 Cr', 'Successful payments', '+9.6%'),
      k('Success rate', '97.8%', 'Paid on first attempt', '+0.4 pts'),
      k('To reconcile', '36', 'Callback without settlement', 'review', 'alert')
    ],
    chart: { title: 'Payments', subtitle: 'Monthly, successful vs failed', series: ['Successful', 'Failed'], base: 7800, split: 0.03 },
    breakdown: { title: 'Payments by Purpose', subtitle: 'Last 30 days', items: [['Tuition fees', 5120], ['Hostel fees', 1640], ['Application fees', 980], ['Event registrations', 480], ['Fines', 200]] },
    actions: [
      a('PAY-301', 'Reconcile', '36 payments not settled', 'Match against settlement file', 'Urgent', '1 hour ago'),
      a('PAY-298', 'Refund', 'Duplicate payment refund', 'Finance approval needed', 'Pending', '4 hours ago'),
      a('PAY-294', 'Config', 'Merchant key rotation', 'Due this month', 'Review', 'Yesterday')
    ],
    activity: [
      l('10:28 AM', 'Payment callback received', 'SBIePay', 'PAY-305'),
      l('06:00 AM', 'Settlement file reconciled', 'System', 'PAY-304'),
      l('Yesterday', 'Payment failed: bank timeout', 'SBIePay', 'PAY-300', 'Failed')
    ]
  },
  digilocker: {
    action: 'Test Connection',
    kpis: [
      k('Certificates issued', '3,260', 'Pushed to DigiLocker', '+18%'),
      k('Verifications', '1,140', 'Documents fetched from students', '+9.2%'),
      k('Pending issue', '84', 'Awaiting signature', 'review', 'alert'),
      k('Success rate', '99.1%', 'Issue and fetch', '+0.2 pts')
    ],
    chart: { title: 'DigiLocker Activity', subtitle: 'Monthly, issued vs verified', series: ['Issued', 'Verified'], base: 820, split: 0.35 },
    breakdown: { title: 'Documents by Type', subtitle: 'This year', items: [['Degree certificates', 1420], ['Marksheets', 1180], ['Migration certificates', 360], ['Transfer certificates', 300]] },
    actions: [
      a('DGL-041', 'Signature', '84 certificates to sign', 'Controller of Examinations', 'Urgent', '2 hours ago'),
      a('DGL-038', 'Mismatch', 'Name mismatch on 6 records', 'Correct before issue', 'Pending', '5 hours ago'),
      a('DGL-035', 'Batch', 'Convocation batch ready', 'Review before push', 'Review', 'Yesterday')
    ],
    activity: [
      l('10:14 AM', 'Marksheets pushed to DigiLocker', 'System', 'DGL-044'),
      l('09:20 AM', 'Applicant document fetched', 'Admissions', 'DGL-043'),
      l('Yesterday', 'Issue failed: invalid Aadhaar link', 'DigiLocker', 'DGL-040', 'Failed')
    ]
  },
  nad: {
    action: 'Test Connection',
    kpis: [
      k('Records lodged', '2,940', 'Academic awards on NAD', '+14%'),
      k('Pending lodging', '128', 'Results not yet sent', 'review', 'alert'),
      k('Verification requests', '410', 'From employers and institutions', '+22%'),
      k('Success rate', '98.6%', 'Lodge and verify', '+0.5 pts')
    ],
    chart: { title: 'NAD Records', subtitle: 'Monthly, lodged vs verified', series: ['Lodged', 'Verified'], base: 620, split: 0.3 },
    breakdown: { title: 'Records by Programme', subtitle: 'This year', items: [['Undergraduate', 1680], ['Postgraduate', 820], ['Diploma', 290], ['Doctoral', 150]] },
    actions: [
      a('NAD-022', 'Lodging', '128 results pending', 'Semester results to lodge', 'Urgent', '3 hours ago'),
      a('NAD-019', 'Correction', 'Record correction request', 'Grade change approved', 'Pending', '1 day ago'),
      a('NAD-016', 'Mapping', 'Programme codes update', 'Match new NAD codes', 'Review', '2 days ago')
    ],
    activity: [
      l('10:00 AM', 'Results batch lodged', 'System', 'NAD-025'),
      l('Yesterday', 'Employer verification answered', 'NAD', 'NAD-024'),
      l('Yesterday', 'Lodging failed: missing roll number', 'NAD', 'NAD-021', 'Failed')
    ]
  },
  'government-portals': {
    action: 'Test Connection',
    kpis: [
      k('Submissions (this year)', '24', 'UGC, AISHE, NAAC and others', '+5'),
      k('Due in 30 days', '4', 'Statutory returns', '1 overdue', 'alert'),
      k('Accepted', '19', 'Acknowledged by portal', '79%'),
      k('Data checks failed', '7', 'Before submission', 'review', 'alert')
    ],
    chart: { title: 'Portal Submissions', subtitle: 'Monthly, accepted vs returned', series: ['Accepted', 'Returned'], base: 4, split: 0.2 },
    breakdown: { title: 'Submissions by Portal', subtitle: 'This year', items: [['AISHE', 6], ['UGC', 7], ['NAAC', 4], ['NIRF', 3], ['State government', 4]] },
    actions: [
      a('GOV-017', 'Overdue', 'AISHE return overdue', 'Faculty data incomplete', 'Urgent', '2 hours ago'),
      a('GOV-014', 'Data check', '7 validation errors', 'Fix before UGC upload', 'Pending', '1 day ago'),
      a('GOV-011', 'NIRF', 'NIRF data capture', 'Review draft figures', 'Review', '2 days ago')
    ],
    activity: [
      l('09:40 AM', 'UGC return acknowledged', 'UGC portal', 'GOV-020'),
      l('Yesterday', 'NAAC data uploaded', 'IQAC', 'GOV-019'),
      l('Yesterday', 'AISHE upload rejected', 'AISHE portal', 'GOV-016', 'Failed')
    ]
  },
  'messaging-providers': {
    action: 'Test Connection',
    kpis: [
      k('Messages (30 days)', '45,200', 'Email, SMS and WhatsApp', '+12%'),
      k('Delivery rate', '98.1%', 'Across providers', '+0.4 pts'),
      k('Providers', '3', 'Email, SMS, WhatsApp', 'muted', 'muted'),
      k('Provider errors', '860', 'Last 30 days', 'review', 'alert')
    ],
    chart: { title: 'Messages Sent', subtitle: 'Monthly, delivered vs failed', series: ['Delivered', 'Failed'], base: 42000, split: 0.02 },
    breakdown: { title: 'Messages by Provider', subtitle: 'Last 30 days', items: [['Email', 24800], ['SMS', 11400], ['WhatsApp', 9000]] },
    actions: [
      a('MSG-029', 'Errors', 'SMS provider timeouts', '312 retries since morning', 'Urgent', '1 hour ago'),
      a('MSG-026', 'Template', 'WhatsApp template approval', 'Waiting for provider approval', 'Pending', '6 hours ago'),
      a('MSG-023', 'Domain', 'Email sender domain check', 'Review sending domain settings', 'Review', 'Yesterday')
    ],
    activity: [
      l('10:32 AM', 'Batch sent: fee reminders', 'System', 'MSG-032'),
      l('09:12 AM', 'Provider failover to backup SMS', 'System', 'MSG-031', 'Warning'),
      l('Yesterday', 'WhatsApp template approved', 'Provider', 'MSG-028')
    ]
  },
  'video-conferencing': {
    action: 'Test Connection',
    kpis: [
      k('Meetings (30 days)', '1,860', 'Online classes and meetings', '+15%'),
      k('Hours hosted', '3,420', 'Total meeting time', '+12%'),
      k('Recordings', '1,140', 'Saved to documents', '+9%'),
      k('Join failures', '46', 'Last 30 days', 'review', 'alert')
    ],
    chart: { title: 'Meetings Hosted', subtitle: 'Monthly, classes vs meetings', series: ['Classes', 'Meetings'], base: 1700, split: 0.3 },
    breakdown: { title: 'Meetings by Platform', subtitle: 'Last 30 days', items: [['Zoom', 820], ['Microsoft Teams', 640], ['Webex', 400]] },
    actions: [
      a('VC-038', 'Licences', 'Licence limit near', '92% of hosts in use', 'Urgent', '2 hours ago'),
      a('VC-035', 'Recording', 'Recordings not synced', '14 recordings pending upload', 'Pending', '5 hours ago'),
      a('VC-031', 'Settings', 'Waiting room policy', 'Review for exams', 'Review', 'Yesterday')
    ],
    activity: [
      l('10:00 AM', 'Class meeting created from timetable', 'System', 'VC-041'),
      l('09:30 AM', 'Recording saved', 'System', 'VC-040'),
      l('Yesterday', 'Join failed: expired link', 'Zoom', 'VC-037', 'Failed')
    ]
  },
  wearables: {
    action: 'Test Connection',
    kpis: [
      k('Connected devices', '412', 'Athlete wearables', '+38'),
      k('Readings (7 days)', '1.8 L', 'Heart rate, load, sleep', '+11%'),
      k('Athletes covered', '96%', 'Of active athletes', '+4 pts'),
      k('High-load alerts', '23', 'Last 7 days', 'review', 'alert')
    ],
    chart: { title: 'Readings Received', subtitle: 'Monthly, training vs recovery', series: ['Training', 'Recovery'], base: 700000, split: 0.4 },
    breakdown: { title: 'Devices by Sport', subtitle: 'Connected devices', items: [['Athletics', 128], ['Football', 96], ['Hockey', 74], ['Wrestling', 62], ['Swimming', 52]] },
    actions: [
      a('WRB-027', 'Alert', '23 high-load alerts', 'Coaches to review training load', 'Urgent', '40 mins ago'),
      a('WRB-024', 'Sync', '18 devices not synced', 'No data for 3 days', 'Pending', '4 hours ago'),
      a('WRB-021', 'Consent', 'Data consent renewals', 'Athletes to re-confirm', 'Review', 'Yesterday')
    ],
    activity: [
      l('10:20 AM', 'Overnight recovery data synced', 'System', 'WRB-030'),
      l('08:45 AM', 'High-load alert raised', 'System', 'WRB-029', 'Warning'),
      l('Yesterday', 'New devices paired', 'Coach', 'WRB-026')
    ]
  },
  'external-university-portals': {
    action: 'Test Connection',
    kpis: [
      k('Partner institutions', '14', 'Connected portals', '+2'),
      k('Exchanges (30 days)', '1,260', 'Credits, transcripts, enrolments', '+16%'),
      k('Credit transfers', '184', 'Processed this term', '+28'),
      k('Failed exchanges', '9', 'Last 30 days', 'review', 'alert')
    ],
    chart: { title: 'Data Exchanges', subtitle: 'Monthly, sent vs received', series: ['Sent', 'Received'], base: 1100, split: 0.45 },
    breakdown: { title: 'Exchanges by Type', subtitle: 'Last 30 days', items: [['Transcripts', 520], ['Credit transfers', 340], ['Enrolment checks', 260], ['Exchange students', 140]] },
    actions: [
      a('EXT-015', 'Credit', '12 credit transfers to approve', 'From partner university', 'Pending', '3 hours ago'),
      a('EXT-012', 'Failure', 'Transcript exchange failed', 'Partner portal unavailable', 'Urgent', '5 hours ago'),
      a('EXT-009', 'Partner', 'New partner onboarding', 'Agree data format', 'Review', 'Yesterday')
    ],
    activity: [
      l('10:05 AM', 'Transcripts sent to partner', 'System', 'EXT-018'),
      l('Yesterday', 'Credit transfer received', 'Partner portal', 'EXT-017'),
      l('Yesterday', 'Exchange failed: timeout', 'Partner portal', 'EXT-014', 'Failed')
    ]
  }

};

/** Generic dashboard for platform services and integrations, which have no hand-written content. */
export function fallbackDashboard(m: ModuleInfo): ModuleDashboard {
  const isIntegration = m.kind === 'integration';
  return {
    action: isIntegration ? 'Test Connection' : 'Open Settings',
    kpis: isIntegration
      ? [
          k('Requests (30 days)', '18,420', 'Calls through the adapter', '+7%'),
          k('Success rate', '99.2%', 'Responses without error', 'healthy'),
          k('Failed calls', '146', 'Retried by integration hub', 'review', 'alert'),
          k('Avg. latency', '420 ms', 'Round trip', '-30 ms')
        ]
      : [
          k('Requests (30 days)', '2.4 L', 'From all modules', '+11%'),
          k('Availability', '99.97%', 'Last 30 days', 'SLA met'),
          k('Errors', '38', 'Logged this month', 'review', 'alert'),
          k('Modules using it', '36', 'Through packages/sdk', 'all')
        ],
    chart: { title: 'Requests', subtitle: 'Monthly, successful vs retried', series: ['Successful', 'Retried'], base: isIntegration ? 3000 : 40000, split: 0.04 },
    breakdown: {
      title: 'Top Callers',
      subtitle: 'Requests this month',
      items: [['Admissions', 4200], ['Fees & Accounts', 3600], ['Examinations', 2900], ['Student Information', 2100], ['Helpdesk', 1300]]
    },
    actions: [
      a(`${m.id.toUpperCase().slice(0, 6)}-01`, 'Configuration', `Review ${m.name} configuration`, 'Keys listed in config/env.example', 'Review', '2 hours ago'),
      a(`${m.id.toUpperCase().slice(0, 6)}-02`, 'Errors', 'Recurring errors this week', 'Inspect logs in monitoring', 'Pending', 'Yesterday')
    ],
    activity: [
      l('10:00 AM', 'Health check passed', 'Monitoring', `${m.id}-HC`),
      l('Yesterday', 'Configuration reloaded', 'System', `${m.id}-CFG`)
    ]
  };
}

const MONTHS = ['Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep'];

/** Deterministic monthly rows for a module's histogram (same numbers on every render). */
export function monthlySeries(seedText: string, base: number, split = 0): { month: string; a: number; b: number }[] {
  let seed = [...seedText].reduce((h, c) => (h * 31 + c.charCodeAt(0)) >>> 0, 7);
  const rand = () => {
    seed = (seed * 1664525 + 1013904223) >>> 0;
    return seed / 2 ** 32;
  };
  return MONTHS.map((month, i) => {
    const trend = 0.82 + i * 0.05;
    const total = Math.max(1, Math.round(base * trend * (0.85 + rand() * 0.3)));
    const b = Math.round(total * split);
    return { month, a: total - b, b };
  });
}
