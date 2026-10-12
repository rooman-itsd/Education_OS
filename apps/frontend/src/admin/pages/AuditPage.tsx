import React, { useState } from 'react';
import {
  History,
  ShieldAlert,
  Search,
  Download,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  KeyRound,
  FileCheck2,
  ShieldCheck
} from '../lib/icons';
import { MOCK_AUDIT_LOGS } from '../data/mockData';
import { roleTitle } from '../data/roles';
import { AuditLog } from '../types';
import { PageHeader, StatGrid, BTN_PRIMARY, BTN_SECONDARY } from '../components/ui/dashboard';

export const AuditPage: React.FC = () => {
  const [logs] = useState<AuditLog[]>(MOCK_AUDIT_LOGS);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedRole, setSelectedRole] = useState('All');
  const [selectedStatus, setSelectedStatus] = useState('All');
  const [toastMsg, setToastMsg] = useState<string | null>(null);

  const showNotification = (msg: string) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 3000);
  };

  const filteredLogs = logs.filter((log) => {
    const matchesSearch =
      log.user.toLowerCase().includes(searchQuery.toLowerCase()) ||
      log.action.toLowerCase().includes(searchQuery.toLowerCase()) ||
      log.resource.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesRole = selectedRole === 'All' || log.role === selectedRole;
    const matchesStatus = selectedStatus === 'All' || log.status === selectedStatus;
    return matchesSearch && matchesRole && matchesStatus;
  });

  const roles = ['All', ...Array.from(new Set(logs.map((l) => l.role)))];

  return (
    <div className="space-y-6">
      {/* Toast Alert */}
      {toastMsg && (
        <div className="fixed bottom-6 right-6 z-50 flex items-center gap-2 bg-[#12233F] text-white px-4 py-3 rounded-lg shadow-xl border border-[#12233F] text-xs">
          <CheckCircle2 className="w-4 h-4 text-[#126B3D]" />
          <span>{toastMsg}</span>
        </div>
      )}

      <PageHeader
        title="Audit Activity"
        subtitle={
          <span className="inline-flex flex-wrap items-center gap-2">
            Every state change writes to platform/audit, and audit records are immutable (ARCHITECTURE.md). Its API is not
            built yet, so these are sample events using the event names in the repo's contracts.
            <span className="inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded-full bg-[#F1F5F9] text-[#475569]">
              <ShieldCheck className="w-3 h-3" />
              Sample data
            </span>
          </span>
        }
        actions={
          <>
            <button onClick={() => showNotification('Export needs the platform/audit API, which is not built yet')} className={BTN_PRIMARY}>
              <Download className="w-3.5 h-3.5" />
              Export Audit Log
            </button>
          </>
        }
      />

      <StatGrid
        stats={[
          { label: 'Events today', icon: History, value: String(logs.filter((l) => !l.timestamp.startsWith('Yesterday')).length), note: 'Sample events' },
          { label: 'Successful', icon: CheckCircle2, value: String(logs.filter((l) => l.status === 'Success').length), note: 'State changes recorded' },
          {
            label: 'Blocked or failed',
            icon: ShieldAlert,
            value: String(logs.filter((l) => l.status !== 'Success').length),
            delta: 'review',
            deltaTone: 'alert',
            note: 'Failed or needs review'
          },
          { label: 'Active actors', icon: FileCheck2, value: String(new Set(logs.map((l) => l.user)).size), note: 'Distinct users and services' }
        ]}
      />

      {/* FILTERS BAR */}
      <div className="bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] p-4 shadow-2xs">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {/* Search */}
          <div className="relative">
            <Search className="w-4 h-4 text-[#475569] absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder="Search by action, user, or resource ID..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 text-xs rounded-lg border border-[#E2E8F0] focus:outline-none focus:ring-2 focus:ring-[#9333EA] bg-[#F6F8FB]"
            />
          </div>

          {/* Role Filter */}
          <div>
            <select
              value={selectedRole}
              onChange={(e) => setSelectedRole(e.target.value)}
              className="w-full px-3 py-1.5 text-xs rounded-lg border border-[#E2E8F0] focus:outline-none focus:ring-2 focus:ring-[#9333EA] bg-[#F6F8FB] text-[#12233F]"
            >
              <option value="All">All Roles</option>
              {roles.filter((r) => r !== 'All').map((r) => (
                <option key={r} value={r}>{roleTitle(r)}</option>
              ))}
            </select>
          </div>

          {/* Status Filter */}
          <div>
            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              className="w-full px-3 py-1.5 text-xs rounded-lg border border-[#E2E8F0] focus:outline-none focus:ring-2 focus:ring-[#9333EA] bg-[#F6F8FB] text-[#12233F]"
            >
              <option value="All">All Event Outcomes</option>
              <option value="Success">Success</option>
              <option value="Failed">Failed</option>
              <option value="Warning">Warning</option>
            </select>
          </div>
        </div>
      </div>

      {/* AUDIT LOGS TABLE */}
      <div className="bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] shadow-2xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="bg-[#F6F8FB] border-b border-[#E2E8F0] text-[#475569] font-semibold">
                <th className="py-3 px-4 w-32">Timestamp</th>
                <th className="py-3 px-4">User</th>
                <th className="py-3 px-4">Role</th>
                <th className="py-3 px-4">Action</th>
                <th className="py-3 px-4">Resource Target</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4 text-right">Origin IP</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#F1F5F9] text-[#12233F]">
              {filteredLogs.length === 0 ? (
                <tr>
                  <td colSpan={7} className="py-8 text-center text-[#475569]">
                    No audit records matching search parameters.
                  </td>
                </tr>
              ) : (
                filteredLogs.map((log) => (
                  <tr key={log.id} className="hover:bg-[#F6F8FB] transition-colors">
                    <td className="py-3 px-4 font-mono text-[#475569] whitespace-nowrap">
                      {log.timestamp}
                    </td>
                    <td className="py-3 px-4 font-semibold text-[#12233F]">
                      {log.user}
                    </td>
                    <td className="py-3 px-4">
                      <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-[#F1F5F9] text-[#7E22CE]">
                        {roleTitle(log.role)}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-[#12233F]">
                      {log.action}
                    </td>
                    <td className="py-3 px-4 font-mono text-[#7E22CE] font-semibold">
                      {log.resource}
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-semibold ${
                          log.status === 'Success'
                            ? 'bg-[#16834B26] text-[#126B3D]'
                            : log.status === 'Warning'
                            ? 'bg-[#F39A1926] text-[#8A4F00]'
                            : 'bg-[#DC262626] text-[#B91C1C]'
                        }`}
                      >
                        {log.status === 'Success' ? (
                          <CheckCircle2 className="w-3 h-3" />
                        ) : log.status === 'Warning' ? (
                          <AlertTriangle className="w-3 h-3" />
                        ) : (
                          <XCircle className="w-3 h-3" />
                        )}
                        <span>{log.status}</span>
                      </span>
                    </td>
                    <td className="py-3 px-4 text-right font-mono text-[11px] text-[#64748B]">
                      {log.ipAddress}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <div className="py-3 px-4 border-t border-[#E2E8F0] bg-[#F6F8FB] flex items-center justify-between text-xs text-[#475569]">
          <span>
            Displaying <strong className="text-[#12233F]">{filteredLogs.length}</strong> sequential ledger entries
          </span>
          <span className="text-[11px]">platform/audit: append-only by design; API not built yet</span>
        </div>
      </div>
    </div>
  );
};
