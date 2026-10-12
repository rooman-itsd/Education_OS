import { asset } from '../lib/assets';
import React, { useEffect, useState } from 'react';
import {
  GraduationCap,
  Clock,
  CheckCircle2,
  FileCheck2,
  Search,
  X,
  Award,
  Check,
  AlertTriangle,
  Download
} from '../lib/icons';
import { ThemeScope } from '../components/ui/theme';
import { themeForSuite } from '../data/suiteThemes';
import { MOCK_APPLICATIONS, ADMISSIONS_FUNNEL, FUNNEL_COLORS } from '../data/mockData';
import { PageHeader, StatGrid, BTN_SECONDARY } from '../components/ui/dashboard';
import { CampusPhoto } from '../components/ui/CampusArt';
import { HistogramPanel, BreakdownPanel } from '../components/ui/panels';
import { MODULE_DASHBOARDS, monthlySeries } from '../data/moduleDashboards';

const ADM_DASH = MODULE_DASHBOARDS.admissions!;
import { AdmissionApplication } from '../types';

export const AdmissionsPage: React.FC = () => {
  const [applications, setApplications] = useState<AdmissionApplication[]>(MOCK_APPLICATIONS);
  // Photo header once public/admissions.jpg exists; otherwise the plain violet header.
  const [hasPhoto, setHasPhoto] = useState(false);
  useEffect(() => {
    const img = new Image();
    img.onload = () => setHasPhoto(true);
    img.src = asset('/admissions.jpg');
  }, []);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedStatus, setSelectedStatus] = useState<string>('All');
  const [selectedProgramme, setSelectedProgramme] = useState<string>('All');
  const [selectedCategory, setSelectedCategory] = useState<string>('All');

  const [selectedApp, setSelectedApp] = useState<AdmissionApplication | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [toastMsg, setToastMsg] = useState<string | null>(null);

  const showNotification = (msg: string) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 3500);
  };

  const handleOpenDrawer = (app: AdmissionApplication) => {
    setSelectedApp(app);
    setIsDrawerOpen(true);
  };

  const handleCloseDrawer = () => {
    setIsDrawerOpen(false);
    setSelectedApp(null);
  };

  const handleApproveApplication = (appId: string) => {
    setApplications((prev) =>
      prev.map((a) => {
        if (a.id === appId) {
          const updated: AdmissionApplication = {
            ...a,
            status: 'Confirmed',
            timeline: a.timeline.map((step) =>
              step.step === 'Document Verification'
                ? { ...step, status: 'completed', note: 'Statutory verification signed off by Admissions Committee' }
                : step.step === 'Confirmation & Registration'
                ? { ...step, status: 'completed', timestamp: 'Just now', note: 'Marked confirmed (sample)' }
                : step
            )
          };
          if (selectedApp?.id === appId) setSelectedApp(updated);
          return updated;
        }
        return a;
      })
    );
    showNotification(`Sample only: ${appId} marked Confirmed on this page. No letter is sent; the admissions module is not built yet.`);
  };

  const handleRequestChanges = (appId: string) => {
    setApplications((prev) =>
      prev.map((a) => {
        if (a.id === appId) {
          const updated: AdmissionApplication = {
            ...a,
            status: 'Under Review',
            timeline: a.timeline.map((step) =>
              step.step === 'Document Verification'
                ? { ...step, status: 'in-progress', note: 'Changes requested (sample)' }
                : step
            )
          };
          if (selectedApp?.id === appId) setSelectedApp(updated);
          return updated;
        }
        return a;
      })
    );
    showNotification(`Sample only: ${appId} sent back to review on this page. No message is sent to the candidate.`);
  };

  const handleToggleDocVerification = (docId: string) => {
    if (!selectedApp) return;
    const updatedDocs = selectedApp.documents.map((d) =>
      d.id === docId ? { ...d, verified: !d.verified } : d
    );
    const updatedApp = { ...selectedApp, documents: updatedDocs };
    setSelectedApp(updatedApp);
    setApplications((prev) => prev.map((a) => (a.id === updatedApp.id ? updatedApp : a)));
  };

  // Filter logic
  const filteredApps = applications.filter((app) => {
    const matchesSearch =
      app.applicant.toLowerCase().includes(searchQuery.toLowerCase()) ||
      app.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      app.email.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = selectedStatus === 'All' || app.status === selectedStatus;
    const matchesProgramme = selectedProgramme === 'All' || app.programme.includes(selectedProgramme);
    const matchesCategory = selectedCategory === 'All' || app.category === selectedCategory;

    return matchesSearch && matchesStatus && matchesProgramme && matchesCategory;
  });

  return (
    <ThemeScope theme={themeForSuite('student-lifecycle')} className="space-y-6">
      {/* Toast Alert */}
      {toastMsg && (
        <div className="fixed bottom-6 right-6 z-50 flex items-center gap-2 bg-[#12233F] text-white px-4 py-3 rounded-lg shadow-xl border border-[#12233F] text-xs">
          <CheckCircle2 className="w-4 h-4 text-[#126B3D]" />
          <span>{toastMsg}</span>
        </div>
      )}

      <PageHeader
        title="Admissions"
        art={hasPhoto ? <CampusPhoto src={asset('/admissions.jpg')} position="70% 45%" tone="violet" /> : undefined}
        subtitle="Application and verification workflow · Academic Year 2026–27"
        actions={
          <button
            onClick={() => showNotification('Export needs the admissions module, which is not built yet')}
            className={BTN_SECONDARY}
          >
            <Download className="w-3.5 h-3.5 text-[#475569]" />
            Export Roster
          </button>
        }
      />

      <StatGrid
        stats={[
          { label: 'Total applications', icon: GraduationCap, value: '1,284', note: 'Undergraduate & Masters' },
          { label: 'Confirmed', icon: CheckCircle2, value: '486', delta: '37.8%', note: 'Sample figure' },
          { label: 'Under review', icon: Clock, value: '86', delta: 'Dean review', deltaTone: 'alert', note: 'Requires Dean review' },
          { label: 'Shortlisted', icon: FileCheck2, value: '824', delta: '64.2%', deltaTone: 'muted', note: 'Counselling invitations issued' }
        ]}
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <HistogramPanel
          className="lg:col-span-2"
          title={ADM_DASH.chart.title}
          subtitle={ADM_DASH.chart.subtitle}
          data={monthlySeries('admissions', ADM_DASH.chart.base, ADM_DASH.chart.split)}
          xKey="month"
          series={[{ key: 'a', name: ADM_DASH.chart.series[0]! }, { key: 'b', name: ADM_DASH.chart.series[1]! }]}
          tooltipLabel={(m) => `${m} 2026`}
        />
        <BreakdownPanel
          title="Admissions Funnel"
          subtitle="Batch 2026 conversion"
          relativeToFirst
          items={ADMISSIONS_FUNNEL.map((f, i) => ({ label: f.stage, count: f.count, color: FUNNEL_COLORS[i] }))}
          footer={{ label: 'Overall acceptance', value: '37.8%' }}
        />
      </div>

      {/* FILTERS BAR */}
      <div className="bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] p-4 shadow-2xs">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {/* Search */}
          <div className="relative">
            <Search className="w-4 h-4 text-[#475569] absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder="Search by candidate name or ID..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 text-xs rounded-lg border border-[#E2E8F0] focus:outline-none focus:ring-2 focus:ring-[#9333EA] bg-[#F6F8FB]"
            />
          </div>

          {/* Status Filter */}
          <div>
            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              className="w-full px-3 py-1.5 text-xs rounded-lg border border-[#E2E8F0] focus:outline-none focus:ring-2 focus:ring-[#9333EA] bg-[#F6F8FB] text-[#12233F]"
            >
              <option value="All">All Statuses</option>
              <option value="Under Review">Under Review</option>
              <option value="Shortlisted">Shortlisted</option>
              <option value="Confirmed">Confirmed</option>
            </select>
          </div>

          {/* Programme Filter */}
          <div>
            <select
              value={selectedProgramme}
              onChange={(e) => setSelectedProgramme(e.target.value)}
              className="w-full px-3 py-1.5 text-xs rounded-lg border border-[#E2E8F0] focus:outline-none focus:ring-2 focus:ring-[#9333EA] bg-[#F6F8FB] text-[#12233F]"
            >
              <option value="All">All Programmes</option>
              <option value="B.Tech">B.Tech CSE (Sports Analytics)</option>
              <option value="B.Sc">B.Sc Sports Science & Biomechanics</option>
              <option value="BBA">BBA Sports Management</option>
              <option value="M.P.Ed">M.P.Ed Physical Education</option>
            </select>
          </div>

          {/* Category Filter */}
          <div>
            <select
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className="w-full px-3 py-1.5 text-xs rounded-lg border border-[#E2E8F0] focus:outline-none focus:ring-2 focus:ring-[#9333EA] bg-[#F6F8FB] text-[#12233F]"
            >
              <option value="All">All Categories</option>
              <option value="General">General</option>
              <option value="OBC">OBC</option>
              <option value="SC/ST">SC/ST</option>
              <option value="Sports Quota">Sports Quota</option>
              <option value="Defence">Defence</option>
            </select>
          </div>
        </div>
      </div>

      {/* ADMISSIONS TABLE */}
      <div className="bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] shadow-2xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="bg-[#F6F8FB] border-b border-[#E2E8F0] text-[#475569] font-semibold">
                <th className="py-3 px-4">Application ID</th>
                <th className="py-3 px-4">Applicant</th>
                <th className="py-3 px-4">Programme</th>
                <th className="py-3 px-4">Category</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Submitted</th>
                <th className="py-3 px-4 text-right">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#F1F5F9] text-[#12233F]">
              {filteredApps.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-[#475569]">
                    No applicant records match the selected filters.
                  </td>
                </tr>
              ) : (
                filteredApps.map((app) => (
                  <tr
                    key={app.id}
                    className="hover:bg-[#F6F8FB] transition-colors cursor-pointer group"
                    onClick={() => handleOpenDrawer(app)}
                  >
                    <td className="py-3 px-4 font-mono font-medium text-[var(--accent)]">
                      {app.id}
                    </td>
                    <td className="py-3 px-4">
                      <div className="font-semibold text-[#12233F]">{app.applicant}</div>
                      <div className="text-[11px] text-[#64748B] flex items-center gap-1">
                        <span>Rank #{app.meritRank}</span>
                        {app.sportsDiscipline && <span>• {app.sportsDiscipline}</span>}
                      </div>
                    </td>
                    <td className="py-3 px-4 text-[#12233F] font-medium">
                      {app.programme}
                    </td>
                    <td className="py-3 px-4">
                      <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-[#F1F5F9] text-[var(--accent)]">
                        {app.category}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-semibold ${
                          app.status === 'Confirmed'
                            ? 'bg-[#16834B26] text-[#126B3D]'
                            : app.status === 'Shortlisted'
                            ? 'bg-[#F39A1926] text-[#8A4F00]'
                            : 'bg-[#DC262626] text-[#B91C1C]'
                        }`}
                      >
                        <span className="w-1.5 h-1.5 rounded-full bg-current" />
                        {app.status}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-[#475569]">
                      {app.submitted}
                    </td>
                    <td className="py-3 px-4 text-right" onClick={(e) => e.stopPropagation()}>
                      <button
                        onClick={() => handleOpenDrawer(app)}
                        className="px-3 py-1 rounded-md border border-[#E2E8F0] hover:border-[#9333EA] text-[var(--accent)] font-semibold hover:bg-[#FFFFFF] text-[11px] transition-colors"
                      >
                        View →
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <div className="py-3 px-4 border-t border-[#E2E8F0] bg-[#F6F8FB] flex items-center justify-between text-xs text-[#475569]">
          <span>
            Displaying <strong className="text-[#12233F]">{filteredApps.length}</strong> candidate applications
          </span>
          <span className="text-[11px]">Sample data · admissions module not built yet</span>
        </div>
      </div>

      {/* RIGHT-SIDE APPLICATION DOSSIER DRAWER */}
      {isDrawerOpen && selectedApp && (
        <div className="fixed inset-0 z-50 overflow-hidden">
          <div
            className="absolute inset-0 bg-[#12233F]/50 backdrop-blur-xs transition-opacity"
            onClick={handleCloseDrawer}
          />

          <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
            <div className="w-screen max-w-lg bg-[#FFFFFF] shadow-2xl border-l border-[#E2E8F0] flex flex-col">
              {/* Drawer Header */}
              <div className="p-5 border-b border-[#E2E8F0] flex items-center justify-between bg-[#F6F8FB]">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs px-2 py-0.5 rounded bg-[#7E22CE26] text-[var(--accent)] font-bold">
                    {selectedApp.id}
                  </span>
                  <span className="text-sm font-bold text-[#12233F]">APPLICATION DETAILS</span>
                </div>
                <button
                  onClick={handleCloseDrawer}
                  className="p-1 rounded-md text-[#475569] hover:text-[#12233F] hover:bg-[#FFFFFF]"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Drawer Body */}
              <div className="flex-1 overflow-y-auto p-6 space-y-6">
                {/* Candidate Overview Card */}
                <div className="p-4 rounded-xl bg-[#F6F8FB] border border-[#E2E8F0] space-y-3">
                  <div className="flex items-start justify-between">
                    <div>
                      <h3 className="text-base font-bold text-[#12233F]">{selectedApp.applicant}</h3>
                      <p className="text-xs text-[var(--accent)] font-medium">{selectedApp.programme}</p>
                    </div>
                    <span
                      className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold ${
                        selectedApp.status === 'Confirmed'
                          ? 'bg-[#16834B26] text-[#126B3D]'
                          : selectedApp.status === 'Shortlisted'
                          ? 'bg-[#F39A1926] text-[#8A4F00]'
                          : 'bg-[#DC262626] text-[#B91C1C]'
                      }`}
                    >
                      {selectedApp.status}
                    </span>
                  </div>

                  <div className="grid grid-cols-2 gap-2 text-xs pt-2 border-t border-[#E2E8F0]">
                    <div>
                      <span className="text-[#475569] text-[11px]">Quota / Category:</span>
                      <p className="font-semibold text-[#12233F]">{selectedApp.category}</p>
                    </div>
                    <div>
                      <span className="text-[#475569] text-[11px]">Merit Rank:</span>
                      <p className="font-semibold text-[#12233F]">Merit Rank #{selectedApp.meritRank}</p>
                    </div>
                    <div>
                      <span className="text-[#475569] text-[11px]">Candidate Contact:</span>
                      <p className="font-mono text-[#12233F]">{selectedApp.phone}</p>
                    </div>
                    <div>
                      <span className="text-[#475569] text-[11px]">Email Address:</span>
                      <p className="font-mono text-[var(--accent)] truncate">{selectedApp.email}</p>
                    </div>
                  </div>

                  {selectedApp.sportsDiscipline && (
                    <div className="pt-2 border-t border-[#E2E8F0] flex items-center gap-1.5 text-xs text-[var(--accent)]">
                      <Award className="w-3.5 h-3.5 text-[#8A4F00]" />
                      <span className="font-medium">Athletic Discipline:</span>
                      <span className="font-semibold">{selectedApp.sportsDiscipline}</span>
                    </div>
                  )}
                </div>

                {/* Statutory Documents Section */}
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <h4 className="text-xs font-bold text-[#12233F] uppercase tracking-wider">
                      Uploaded Statutory Documents ({selectedApp.documents.length})
                    </h4>
                    <span className="text-[11px] text-[#475569]">Click checkbox to toggle verification</span>
                  </div>

                  <div className="space-y-2">
                    {selectedApp.documents.map((doc) => (
                      <div
                        key={doc.id}
                        onClick={() => handleToggleDocVerification(doc.id)}
                        className={`p-3 rounded-lg border flex items-center justify-between transition-colors cursor-pointer ${
                          doc.verified
                            ? 'bg-[#16834B26]/30 border-[#16834B]/30 hover:bg-[#16834B26]/50'
                            : 'bg-[#DC262614] border-[#DC262640] hover:bg-[#DC262626]'
                        }`}
                      >
                        <div className="flex items-center gap-2.5">
                          <button
                            type="button"
                            className={`w-5 h-5 rounded flex items-center justify-center transition-colors ${
                              doc.verified ? 'bg-[#16834B] text-white' : 'border border-[#CBD5E1] bg-[#FFFFFF]'
                            }`}
                          >
                            {doc.verified && <Check className="w-3.5 h-3.5 stroke-[3]" />}
                          </button>
                          <div>
                            <p className="text-xs font-semibold text-[#12233F]">{doc.name}</p>
                            <p className="text-[10px] text-[#475569]">
                              Format: {doc.type} • {doc.fileSize || 'size unknown'}
                            </p>
                          </div>
                        </div>

                        <span
                          className={`text-[10px] font-semibold px-2 py-0.5 rounded ${
                            doc.verified ? 'bg-[#16834B26] text-[#126B3D]' : 'bg-[#DC262626] text-[#B91C1C]'
                          }`}
                        >
                          {doc.verified ? 'Verified ✓' : 'Pending Verification'}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Admission Timeline Progression */}
                <div className="space-y-3">
                  <h4 className="text-xs font-bold text-[#12233F] uppercase tracking-wider">
                    Application Lifecycle Timeline
                  </h4>

                  <div className="relative pl-6 space-y-4 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-0.5 before:bg-[#E2E8F0]">
                    {selectedApp.timeline.map((step, idx) => {
                      const isComplete = step.status === 'completed';
                      const isInProgress = step.status === 'in-progress';

                      return (
                        <div key={idx} className="relative">
                          {/* Dot */}
                          <div
                            className={`absolute -left-6 top-0.5 w-4 h-4 rounded-full border-2 flex items-center justify-center ${
                              isComplete
                                ? 'bg-[#16834B] border-white text-white'
                                : isInProgress
                                ? 'bg-[#9333EA] border-white text-white animate-pulse'
                                : 'bg-[#F1F5F9] border-[#CBD5E1]'
                            }`}
                          >
                            {isComplete && <Check className="w-2.5 h-2.5 stroke-[3]" />}
                          </div>

                          <div className="space-y-0.5">
                            <p className="text-xs font-bold text-[#12233F]">{step.step}</p>
                            <p className="text-[11px] text-[#475569]">{step.timestamp}</p>
                            {step.note && (
                              <p className="text-[11px] text-[var(--accent)] bg-[#7E22CE26]/40 p-1.5 rounded mt-1">
                                {step.note}
                              </p>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>

              {/* Drawer Footer Actions */}
              <div className="p-4 border-t border-[#E2E8F0] bg-[#F6F8FB] space-y-2">
                <div className="grid grid-cols-2 gap-2">
                  <button
                    onClick={() => handleRequestChanges(selectedApp.id)}
                    className="py-2.5 px-3 rounded-lg border border-[#F39A19] text-[#8A4F00] hover:bg-[#F39A1926]/40 text-xs font-semibold transition-colors flex items-center justify-center gap-1.5"
                  >
                    <AlertTriangle className="w-3.5 h-3.5" />
                    <span>Request Changes</span>
                  </button>

                  <button
                    onClick={() => handleApproveApplication(selectedApp.id)}
                    disabled={selectedApp.status === 'Confirmed'}
                    className="py-2.5 px-3 rounded-lg bg-[#16834B] hover:bg-[#126B3D] text-white text-xs font-semibold transition-colors flex items-center justify-center gap-1.5 shadow-sm disabled:opacity-70"
                  >
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    <span>Approve & Admit</span>
                  </button>
                </div>
                <p className="text-[10px] text-center text-[#475569]">
                  Sample workflow: changes stay on this page. The admissions module is not built yet.
                </p>
              </div>
            </div>
          </div>
        </div>
      )}
    </ThemeScope>
  );
};
