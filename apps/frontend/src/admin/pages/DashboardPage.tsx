import React, { useEffect, useRef, useState } from 'react';
import { useNavigate } from '../lib/router';
import {
  Users,
  Trophy,
  FileClock,
  IndianRupee,
  Presentation,
  LifeBuoy,
  TrendingUp,
  CheckCircle2,
  UserPlus,
  GraduationCap,
  ChevronDown,
  UserCog,
  Megaphone,
  DownloadCloud,
  RefreshCw,
  FileCheck2,
  Scale
} from '../lib/icons';
import { roleTitle } from '../data/roles';
import { useOrganisation } from '../lib/organisation';
import { useAuth } from '../lib/auth';
import { CountUp } from '../components/ui/CountUp';
import { CampusPhoto } from '../components/ui/CampusArt';
import { MiniHistogram, MiniPie, MiniStackedBars, MiniDonut, MiniHBars, MiniGauge } from '../components/ui/kpiViz';
import { StatGrid, PageHeader, BTN_PRIMARY, BTN_SECONDARY } from '../components/ui/dashboard';
import { HistogramPanel, BreakdownPanel, ActionSummaryPanel, UpcomingPanel, ActivityPanel, PanelLink, activityToneForRole } from '../components/ui/panels';
import { ENROLLMENT_TREND, ADMISSIONS_FUNNEL, FUNNEL_COLORS, MOCK_AUDIT_LOGS } from '../data/mockData';

const ENROLLMENT_SERIES = [
  { key: 'academics', name: 'Academic' },
  { key: 'sportsQuota', name: 'Sports quota' }
];

/** Colour pairs from the design palette, one per area. */
const TONES = {
  admissions: { fg: '#7E22CE', bg: '#F3E8FF' },
  exams: { fg: '#4338CA', bg: '#EEEEFD' },
  workflow: { fg: '#6256C9', bg: '#EFEDFB' },
  finance: { fg: '#15803D', bg: '#EAF6EC' },
  governance: { fg: '#DC2626', bg: '#FEF2F2' },
  sports: { fg: '#C2410C', bg: '#FFF1E6' }
};

/** Sample schedule, as days from today so "next two weeks" always holds. */
const UPCOMING = [
  { inDays: 1, title: 'Admission review', meta: 'Admissions committee · Batch 2026', category: 'Admissions', tone: TONES.admissions, to: '/admissions' },
  { inDays: 5, title: 'Examination schedule', meta: 'End-semester timetable release', category: 'Exam', tone: TONES.exams, to: '/modules/examinations' },
  { inDays: 8, title: 'Finance reconciliation', meta: 'Autumn fee ledger close', category: 'Finance', tone: TONES.finance, to: '/modules/fees-accounts' },
  { inDays: 12, title: 'Inter-university athletics', meta: 'Tournament & events · Main campus', category: 'Sports', tone: TONES.sports, to: '/modules/tournament-events' }
];

const isoInDays = (days: number) => {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
};

/** Upward trend figure. */
const Up: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <span className="inline-flex items-center">
    <TrendingUp className="w-3 h-3 mr-0.5" />
    {children}
  </span>
);

const getGreeting = (hour: number) => (hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening');

export const DashboardPage: React.FC = () => {
  const org = useOrganisation();
  const { session } = useAuth();
  const viewerName = session?.me.name || session?.me.email || 'Administrator';
  const navigate = useNavigate();
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const [showMore, setShowMore] = useState(false);
  const moreRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const close = (e: MouseEvent) => {
      if (moreRef.current && !moreRef.current.contains(e.target as Node)) setShowMore(false);
    };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, []);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3000);
  };

  const moreActions = [
    { label: 'Generate report', icon: DownloadCloud, run: () => showToast('Reports need platform/reporting, which is not built yet') },
    { label: 'Create user', icon: UserCog, run: () => navigate('/users?new=1') },
    { label: 'New announcement', icon: Megaphone, run: () => showToast('Announcements need platform/notification, which is not built yet') },
    {
      label: 'Refresh metrics',
      icon: RefreshCw,
      run: () => {
        setRefreshKey((k) => k + 1);
        showToast('Sample figures reloaded');
      }
    }
  ];

  const kpis = [
    { label: 'Total Students', icon: Users, value: <CountUp key={refreshKey} end={3842} />, delta: <Up>+4.8%</Up>, note: 'vs last session', to: '/modules/student-information',
      viz: (
        <MiniHistogram
          values={[3420, 3510, 3560, 3640, 3700, 3790, 3842]}
          colors={['#6256C9', '#315EA8', '#159A72', '#22A06B', '#E89A35', '#E45B67', '#315EA8']}
        />
      ) },
    { label: 'Active Athletes', icon: Trophy, value: <CountUp key={refreshKey} end={428} />, delta: <Up>+8.2%</Up>, note: '16 disciplines', to: '/modules/athlete-performance',
      viz: (
        // athletes by discipline group: athletics, wrestling, hockey, boxing, other sports
        <MiniPie
          delay={600}
          slices={[
            { value: 30, color: '#315EA8' },
            { value: 20, color: '#159A72' },
            { value: 18, color: '#E89A35' },
            { value: 14, color: '#E45B67' },
            { value: 18, color: '#6256C9' }
          ]}
        />
      ) },
    { label: 'Pending Approvals', icon: FileClock, value: <CountUp key={refreshKey} end={38} />, delta: '12 urgent', deltaTone: 'alert' as const, to: '/admissions',
      viz: (
        // 38 pending by queue: admissions, other, examination, finance, grievance
        <MiniHBars
          delay={300}
          bars={[
            { value: 12, color: '#E45B67' },
            { value: 10, color: '#6256C9' },
            { value: 8, color: '#E89A35' },
            { value: 5, color: '#315EA8' },
            { value: 3, color: '#159A72' }
          ]}
        />
      ) },
    {
      label: 'Fee Collection',
      icon: IndianRupee,
      value: <CountUp key={refreshKey} end={8.42} decimals={2} prefix="₹" suffix=" Cr" />,
      delta: <Up>+12.4%</Up>,
      note: 'Autumn 2026',
      to: '/modules/fees-accounts',
      viz: (
        // ₹ Cr per month, split by fee head: tuition, hostel, exam & other
        <MiniStackedBars
          delay={900}
          colors={['#22A06B', '#315EA8', '#E89A35']}
          stacks={[
            [3.1, 1.3, 0.7],
            [3.4, 1.4, 0.8],
            [3.7, 1.6, 0.9],
            [4.0, 1.7, 0.9],
            [4.4, 1.8, 1.1],
            [4.7, 2.0, 1.2],
            [5.0, 2.1, 1.32]
          ]}
        />
      )
    },
    { label: 'Active Faculty', icon: Presentation, value: <CountUp key={refreshKey} end={312} />, delta: '96% rostered', deltaTone: 'muted' as const, accent: 'navy' as const, to: '/modules/hr-payroll',
      viz: (
        // 96% rostered, split by school (Sports Sciences, Physical Education, Coaching, Allied); 4% unrostered stays grey
        <MiniDonut
          of={100}
          delay={450}
          slices={[
            { value: 34, color: '#6256C9' },
            { value: 26, color: '#315EA8' },
            { value: 21, color: '#159A72' },
            { value: 15, color: '#E89A35' }
          ]}
        />
      ) },
    { label: 'Support Tickets', icon: LifeBuoy, value: <CountUp key={refreshKey} end={24} />, delta: 'Avg response 4.2h', deltaTone: 'muted' as const, accent: 'orange' as const, to: '/modules/helpdesk',
      viz: (
        // average response 4.2h on a 0–6h scale: green < 3h, amber 3–5h, coral 5–6h
        <MiniGauge
          delay={1200}
          value={4.2 / 6}
          zones={[
            { to: 0.5, color: '#22A06B' },
            { to: 0.8333, color: '#E89A35' },
            { to: 1, color: '#E45B67' }
          ]}
        />
      ) }
  ];

  const queues = [
    { label: 'Admission approvals', count: 12, level: 'urgent' as const, icon: GraduationCap, tone: TONES.admissions, onOpen: () => navigate('/admissions') },
    { label: 'Other approvals', count: 10, level: 'pending' as const, icon: FileClock, tone: TONES.workflow, onOpen: () => navigate('/modules/workflow') },
    { label: 'Examination approvals', count: 8, level: 'pending' as const, icon: FileCheck2, tone: TONES.exams, onOpen: () => navigate('/modules/examinations') },
    { label: 'Finance approvals', count: 5, level: 'pending' as const, icon: IndianRupee, tone: TONES.finance, onOpen: () => navigate('/modules/fees-accounts') },
    { label: 'Grievance cases', count: 3, level: 'normal' as const, icon: Scale, tone: TONES.governance, onOpen: () => navigate('/modules/grievance') }
  ];

  const upcoming = UPCOMING.map(({ inDays, to, ...it }) => ({ ...it, date: isoInDays(inDays), onOpen: () => navigate(to) }));

  return (
    <div className="space-y-6">
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-50 flex items-center gap-2 bg-[#12233F] text-white px-4 py-3 rounded-lg shadow-lg text-xs">
          <CheckCircle2 className="w-4 h-4 text-[#6FCF97]" />
          <span>{toastMessage}</span>
        </div>
      )}

      <PageHeader
        title="Dashboard"
        art={<CampusPhoto />}
        subtitle={
          <>
            <span className="block text-[15px] text-[#12233F]">
              {getGreeting(new Date().getHours())}, <span className="font-semibold">{viewerName}</span>
            </span>
            <span className="block mt-0.5 text-[13px] text-[#64748B]">{org.name} · Academic Year 2026–27</span>
          </>
        }
        actions={
          <>
            <button onClick={() => showToast('Student records need the student-information module, which is not built yet')} className={BTN_SECONDARY}>
              <UserPlus className="w-3.5 h-3.5 text-[#7E22CE]" />
              Add Student
            </button>
            <button onClick={() => navigate('/admissions')} className={BTN_PRIMARY}>
              <GraduationCap className="w-3.5 h-3.5" />
              Review Admissions
            </button>
            <div className="relative" ref={moreRef}>
              <button onClick={() => setShowMore((v) => !v)} aria-haspopup="menu" aria-expanded={showMore} className={BTN_SECONDARY}>
                More
                <ChevronDown className="w-3.5 h-3.5 text-[#64748B]" />
              </button>
              {showMore && (
                <div role="menu" className="absolute right-0 mt-1.5 w-48 rounded-lg bg-white border border-[#E2E8F0] shadow-lg py-1 z-20">
                  {moreActions.map(({ label, icon: Icon, run }) => (
                    <button
                      key={label}
                      role="menuitem"
                      onClick={() => {
                        setShowMore(false);
                        run();
                      }}
                      className="w-full flex items-center gap-2.5 px-3 py-2 text-xs text-[#12233F] hover:bg-[#F6F8FB]"
                    >
                      <Icon className="w-3.5 h-3.5 text-[#64748B]" />
                      {label}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </>
        }
      />

      <StatGrid stats={kpis} colorful />

      {/* Enrollment + admissions overview */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <HistogramPanel
          className="lg:col-span-2 eos-lift"
          title="Student Enrollment"
          subtitle="Enrollment by academic year"
          data={ENROLLMENT_TREND}
          xKey="year"
          series={ENROLLMENT_SERIES}
          height={260}
          tooltipLabel={(year) => `Academic year ${year}`}
        />
        <BreakdownPanel
          className="eos-lift"
          title="Admissions Overview"
          subtitle="Batch 2026"
          relativeToFirst
          items={ADMISSIONS_FUNNEL.map((f, i) => ({ label: f.stage, count: f.count, color: FUNNEL_COLORS[i] }))}
          action={<PanelLink onClick={() => navigate('/admissions')}>View Admissions</PanelLink>}
          footer={{ label: 'Overall acceptance', value: '37.8%' }}
        />
      </div>

      {/* Actions + upcoming */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ActionSummaryPanel rows={queues} className="eos-lift" />
        <UpcomingPanel items={upcoming} className="eos-lift" />
      </div>

      <ActivityPanel
        items={MOCK_AUDIT_LOGS.slice(0, 5).map((l) => ({
          id: l.id,
          time: l.timestamp,
          title: l.action,
          meta: `${l.user} · ${roleTitle(l.role)}`,
          status: l.status,
          tone: activityToneForRole(l.role)
        }))}
        action={<PanelLink onClick={() => navigate('/audit-logs')}>View all</PanelLink>}
      />
    </div>
  );
};
