import React, { useCallback, useEffect, useState } from 'react';
import {
  Users,
  UserCheck,
  Clock,
  UserX,
  Search,
  Plus,
  X,
  Shield,
  CheckCircle2,
} from '../lib/icons';
import { MOCK_USERS } from '../data/mockData';
import { PageHeader, StatGrid, BTN_PRIMARY } from '../components/ui/dashboard';
import { findRole, roleTitle, useRoles } from '../data/roles';
import { User, UserStatus } from '../types';
import { useSearchParams } from '../lib/router';
import { useAuth } from '../lib/auth';
import { api, ApiError } from '../../api/client';

/** A user as GET /api/v1/identity/users returns it. */
interface ApiUser {
  id: string;
  email: string;
  name: string;
  roles: string[];
}

const fromApi = (u: ApiUser): User => ({
  id: u.id,
  name: u.name,
  email: u.email,
  role: u.roles[0] ?? 'student',
  department: '–',
  status: 'Active',
  lastLogin: '–',
  dataScope: findRole(u.roles[0] ?? '')?.dataScope ?? 'Self'
});

export const UsersPage: React.FC = () => {
  const { session } = useAuth();
  const { ROLES } = useRoles();
  // Live: an org admin's own organisation, through the identity API. Otherwise the sample list.
  const live = Boolean(session?.organisation);
  const canCreate = !session?.me.is_super_admin;
  const [params] = useSearchParams();
  const [usersList, setUsersList] = useState<User[]>(live ? [] : MOCK_USERS);
  const [newUserPassword, setNewUserPassword] = useState('');
  const [saving, setSaving] = useState(false);
  const loadUsers = useCallback(async () => {
    if (!live) return;
    try {
      setUsersList((await api<ApiUser[]>('/identity/users')).map(fromApi));
    } catch (err) {
      setToastMsg(err instanceof ApiError ? `Could not load users: ${err.message}` : 'Could not load users');
    }
  }, [live]);
  useEffect(() => {
    void loadUsers();
  }, [loadUsers]);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedRole, setSelectedRole] = useState('All');
  const [selectedDept, setSelectedDept] = useState('All');
  const [selectedStatus, setSelectedStatus] = useState('All');
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);
  useEffect(() => {
    if (params.get('new') === '1' && canCreate) setShowAddModal(true);
  }, [params, canCreate]);
  const [toastMsg, setToastMsg] = useState<string | null>(null);

  // New user state for modal
  const [newUserName, setNewUserName] = useState('');
  const [newUserEmail, setNewUserEmail] = useState('');
  const [newUserRole, setNewUserRole] = useState('faculty');
  const [newUserDept, setNewUserDept] = useState('Physical Education');

  const showNotification = (msg: string) => {
    setToastMsg(msg);
    setTimeout(() => setToastMsg(null), 3000);
  };

  const handleOpenUserDrawer = (user: User) => {
    setSelectedUser(user);
    setIsDrawerOpen(true);
  };

  const handleCloseDrawer = () => {
    setIsDrawerOpen(false);
    setSelectedUser(null);
  };

  const handleToggleStatus = (targetId: string) => {
    setUsersList((prev) =>
      prev.map((u) => {
        if (u.id === targetId) {
          const nextStatus: UserStatus = u.status === 'Active' ? 'Suspended' : 'Active';
          const updated = { ...u, status: nextStatus };
          if (selectedUser?.id === targetId) setSelectedUser(updated);
          showNotification(`Preview only: ${u.name} shown as ${nextStatus}; suspending users is not in the identity API yet`);
          return updated;
        }
        return u;
      })
    );
  };

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newUserName || !newUserEmail) return;

    if (live) {
      // POST /api/v1/identity/users: org admin only; password of at least 8 characters.
      setSaving(true);
      try {
        await api('/identity/users', { method: 'POST', json: { email: newUserEmail, name: newUserName, password: newUserPassword, roles: [newUserRole] } });
        await loadUsers();
        setShowAddModal(false);
        setNewUserName('');
        setNewUserEmail('');
        setNewUserPassword('');
        showNotification(`${newUserName} can now sign in with ${newUserEmail}`);
      } catch (err) {
        showNotification(err instanceof ApiError ? `Not created: ${err.message}` : 'Not created');
      } finally {
        setSaving(false);
      }
      return;
    }

    const created: User = {
      id: `USR-${1000 + usersList.length + 1}`,
      name: newUserName,
      email: newUserEmail,
      role: newUserRole,
      department: newUserDept,
      status: 'Active',
      lastLogin: 'Never (New)',
      dataScope: findRole(newUserRole)?.dataScope ?? 'Department'
    };

    setUsersList([created, ...usersList]);
    setShowAddModal(false);
    setNewUserName('');
    setNewUserEmail('');
    setNewUserPassword('');
    showNotification(`Preview only: ${created.name} added to this page, not saved`);
  };

  // Filtering
  const filteredUsers = usersList.filter((u) => {
    const matchesSearch =
      u.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      u.email.toLowerCase().includes(searchQuery.toLowerCase()) ||
      u.id.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesRole = selectedRole === 'All' || u.role === selectedRole;
    const matchesDept = selectedDept === 'All' || u.department === selectedDept;
    const matchesStatus = selectedStatus === 'All' || u.status === selectedStatus;
    return matchesSearch && matchesRole && matchesDept && matchesStatus;
  });

  const roles = ['All', ...Array.from(new Set(usersList.map((u) => u.role)))];
  const departments = ['All', ...Array.from(new Set(usersList.map((u) => u.department)))];

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
        title="Users & Access"
        subtitle={live ? 'Users of your organisation, from platform/identity.' : session?.me.is_super_admin ? 'Sample directory. Users belong to organisations; a super admin works through organisation screens (not built yet).' : 'Sample directory (preview). Sign in as an organisation admin to see and add real users.'}
        actions={
          canCreate ? (
            <button onClick={() => setShowAddModal(true)} className={BTN_PRIMARY}>
              <Plus className="w-3.5 h-3.5" />
              Add User
            </button>
          ) : undefined
        }
      />

      <StatGrid
        stats={[
          { label: 'Users', icon: Users, value: usersList.length.toLocaleString('en-IN'), note: live ? 'In your organisation' : 'Sample list' },
          { label: 'Active', icon: UserCheck, value: String(usersList.filter((u) => u.status === 'Active').length), note: live ? 'Can sign in' : 'Sample list' },
          { label: 'Pending', icon: Clock, value: String(usersList.filter((u) => u.status === 'Pending').length), note: 'Not signed in yet' },
          { label: 'Suspended', icon: UserX, value: String(usersList.filter((u) => u.status === 'Suspended').length), deltaTone: 'alert', note: 'Sample only: no suspend API yet' }
        ]}
      />

      {/* FILTER & SEARCH BAR */}
      <div className="bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] p-4 shadow-2xs space-y-3">
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {/* Search */}
          <div className="relative">
            <Search className="w-4 h-4 text-[#475569] absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder="Search by name, ID or email..."
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

          {/* Department Filter */}
          <div>
            <select
              value={selectedDept}
              onChange={(e) => setSelectedDept(e.target.value)}
              className="w-full px-3 py-1.5 text-xs rounded-lg border border-[#E2E8F0] focus:outline-none focus:ring-2 focus:ring-[#9333EA] bg-[#F6F8FB] text-[#12233F]"
            >
              <option value="All">All Departments</option>
              {departments.filter((d) => d !== 'All').map((d) => (
                <option key={d} value={d}>{d}</option>
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
              <option value="All">All Statuses</option>
              <option value="Active">Active</option>
              <option value="Pending">Pending</option>
              <option value="Suspended">Suspended</option>
            </select>
          </div>
        </div>
      </div>

      {/* USERS TABLE */}
      <div className="bg-[#FFFFFF] rounded-xl border border-[#E2E8F0] shadow-2xs overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="bg-[#F6F8FB] border-b border-[#E2E8F0] text-[#475569] font-semibold">
                <th className="py-3 px-4">User ID</th>
                <th className="py-3 px-4">Name</th>
                <th className="py-3 px-4">Role</th>
                <th className="py-3 px-4">Department</th>
                <th className="py-3 px-4">Email</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Last Login</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#F1F5F9] text-[#12233F]">
              {filteredUsers.length === 0 ? (
                <tr>
                  <td colSpan={8} className="py-8 text-center text-[#475569]">
                    No university users match the applied filters.
                  </td>
                </tr>
              ) : (
                filteredUsers.map((user) => (
                  <tr
                    key={user.id}
                    className="hover:bg-[#F6F8FB] transition-colors cursor-pointer group"
                    onClick={() => handleOpenUserDrawer(user)}
                  >
                    <td className="py-3 px-4 font-mono font-medium text-[#7E22CE]">
                      {user.id}
                    </td>
                    <td className="py-3 px-4">
                      <div className="font-semibold text-[#12233F]">{user.name}</div>
                      <div className="text-[11px] text-[#64748B] font-mono">{user.employeeId}</div>
                    </td>
                    <td className="py-3 px-4">
                      <span className="inline-flex items-center gap-1 font-medium px-2 py-0.5 rounded bg-[#F1F5F9] text-[#7E22CE]">
                        {roleTitle(user.role)}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-[#475569]">
                      {user.department}
                    </td>
                    <td className="py-3 px-4 text-[#475569] font-mono text-[11px]">
                      {user.email}
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold ${
                          user.status === 'Active'
                            ? 'bg-[#16834B26] text-[#126B3D]'
                            : user.status === 'Pending'
                            ? 'bg-[#F39A1926] text-[#8A4F00]'
                            : 'bg-[#DC262626] text-[#B91C1C]'
                        }`}
                      >
                        <span className="w-1.5 h-1.5 rounded-full bg-current" />
                        {user.status}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-[#475569] whitespace-nowrap">
                      {user.lastLogin}
                    </td>
                    <td className="py-3 px-4 text-right" onClick={(e) => e.stopPropagation()}>
                      <button
                        onClick={() => handleOpenUserDrawer(user)}
                        className="px-2.5 py-1 rounded border border-[#E2E8F0] hover:border-[#9333EA] text-[#7E22CE] font-medium hover:bg-[#FFFFFF] text-[11px] transition-colors"
                      >
                        Details →
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Table footer count */}
        <div className="py-3 px-4 border-t border-[#E2E8F0] bg-[#F6F8FB] flex items-center justify-between text-xs text-[#475569]">
          <span>
            Showing <strong className="text-[#12233F]">{filteredUsers.length}</strong> of{' '}
            <strong className="text-[#12233F]">{usersList.length}</strong> loaded staff records
          </span>
          <span className="text-[11px]">Sample data · identity lists and creates users today</span>
        </div>
      </div>

      {/* RIGHT-SIDE USER DETAILS DRAWER */}
      {isDrawerOpen && selectedUser && (
        <div className="fixed inset-0 z-50 overflow-hidden">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-[#12233F]/50 backdrop-blur-xs transition-opacity"
            onClick={handleCloseDrawer}
          />

          <div className="fixed inset-y-0 right-0 max-w-full flex pl-10">
            <div className="w-screen max-w-md bg-[#FFFFFF] shadow-2xl border-l border-[#E2E8F0] flex flex-col">
              {/* Drawer Header */}
              <div className="p-5 border-b border-[#E2E8F0] flex items-center justify-between bg-[#F6F8FB]">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-xs px-2 py-0.5 rounded bg-[#7E22CE26] text-[#7E22CE] font-semibold">
                    {selectedUser.id}
                  </span>
                  <span className="text-sm font-bold text-[#12233F]">User Profile & Scope</span>
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
                {/* Profile Snapshot */}
                <div className="flex items-center gap-4 pb-4 border-b border-[#F1F5F9]">
                  <div className="w-14 h-14 rounded-xl bg-[#7E22CE] text-white flex items-center justify-center font-bold text-lg shadow-sm">
                    {selectedUser.name
                      .split(' ')
                      .map((n) => n[0])
                      .slice(0, 2)
                      .join('')}
                  </div>
                  <div>
                    <h3 className="text-base font-bold text-[#12233F]">{selectedUser.name}</h3>
                    <p className="text-xs text-[#7E22CE] font-medium">{roleTitle(selectedUser.role)}</p>
                    <p className="text-[10px] text-[#64748B] font-mono">
                      role: {selectedUser.role} · {findRole(selectedUser.role)?.permissions.length ?? 0} permission keys
                    </p>
                    <p className="text-[11px] text-[#475569]">{selectedUser.department}</p>
                  </div>
                </div>

                {/* Key Attributes */}
                <div className="space-y-3">
                  <h4 className="text-xs font-bold text-[#12233F] uppercase tracking-wider text-[#475569]">
                    Institutional Details
                  </h4>

                  <div className="p-3.5 rounded-lg bg-[#F6F8FB] border border-[#E2E8F0] space-y-2.5 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="text-[#475569]">Employee Code:</span>
                      <span className="font-mono font-medium text-[#12233F]">{selectedUser.employeeId}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-[#475569]">Institutional Email:</span>
                      <span className="font-mono text-[#7E22CE]">{selectedUser.email}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-[#475569]">Official Phone:</span>
                      <span className="text-[#12233F]">{selectedUser.phone}</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-[#475569]">Last Authenticated:</span>
                      <span className="text-[#12233F]">{selectedUser.lastLogin}</span>
                    </div>
                  </div>
                </div>

                {/* RBAC Data Scope */}
                <div className="space-y-2">
                  <h4 className="text-xs font-bold text-[#12233F] uppercase tracking-wider text-[#475569]">
                    Data Scope (sample, not enforced)
                  </h4>
                  <div className="p-3.5 rounded-lg bg-[#7E22CE26]/50 border border-[#9333EA]/20 flex items-start gap-3">
                    <Shield className="w-4 h-4 text-[#7E22CE] mt-0.5" />
                    <div>
                      <div className="font-semibold text-xs text-[#7E22CE]">{selectedUser.dataScope} Scope</div>
                      <p className="text-[11px] text-[#475569] mt-0.5">
                        {selectedUser.dataScope === 'Institution'
                          ? 'Whole organisation. Row-level security today is per organisation only.'
                          : selectedUser.dataScope === 'Department'
                          ? `Own department (${selectedUser.department}). Not enforced by the API yet.`
                          : 'Assigned records only. Not enforced by the API yet.'}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Security Status */}
                <div className="space-y-2">
                  <h4 className="text-xs font-bold text-[#12233F] uppercase tracking-wider text-[#475569]">
                    Security Status
                  </h4>
                  <div className="p-3.5 rounded-lg bg-[#F6F8FB] border border-[#E2E8F0] space-y-2 text-xs">
                    <div className="flex items-center justify-between">
                      <span className="text-[#475569]">Two-Factor Authentication:</span>
                      <span className="font-semibold px-2 py-0.5 rounded text-[10px] bg-[#F1F5F9] text-[#475569]">Not available yet</span>
                    </div>
                    <div className="flex items-center justify-between">
                      <span className="text-[#475569]">Account Status:</span>
                      <span
                        className={`font-semibold px-2 py-0.5 rounded text-[10px] ${
                          selectedUser.status === 'Active'
                            ? 'bg-[#16834B26] text-[#126B3D]'
                            : selectedUser.status === 'Pending'
                            ? 'bg-[#F39A1926] text-[#8A4F00]'
                            : 'bg-[#DC262626] text-[#B91C1C]'
                        }`}
                      >
                        {selectedUser.status}
                      </span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Drawer Footer Actions */}
              <div className="p-4 border-t border-[#E2E8F0] bg-[#F6F8FB] space-y-2">
                <div className="grid grid-cols-2 gap-2">
                  <button
                    onClick={() => {
                      showNotification('Password reset is not in the identity API yet');
                    }}
                    className="py-2 px-3 rounded-lg border border-[#E2E8F0] hover:bg-[#FFFFFF] text-xs font-medium text-[#12233F] transition-colors"
                  >
                    Reset Password
                  </button>
                  <button
                    onClick={() => handleToggleStatus(selectedUser.id)}
                    className={`py-2 px-3 rounded-lg text-xs font-medium transition-colors ${
                      selectedUser.status === 'Active'
                        ? 'border border-[#DC262626] text-[#B91C1C] hover:bg-[#DC262626]/30'
                        : 'border border-[#16834B26] text-[#126B3D] hover:bg-[#16834B26]/50'
                    }`}
                  >
                    {selectedUser.status === 'Active' ? 'Suspend User' : 'Activate User'}
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* CREATE USER MODAL */}
      {showAddModal && (
        <div className="fixed inset-0 z-50 bg-[#12233F]/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="w-full max-w-md bg-[#FFFFFF] rounded-xl shadow-2xl border border-[#E2E8F0] overflow-hidden">
            <div className="p-4 border-b border-[#E2E8F0] flex items-center justify-between bg-[#F6F8FB]">
              <h3 className="text-sm font-bold text-[#12233F]">Create Institutional User</h3>
              <button
                onClick={() => setShowAddModal(false)}
                className="text-[#475569] hover:text-[#12233F]"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <form onSubmit={handleCreateUser} className="p-5 space-y-4 text-xs">
              <div>
                <label className="block font-semibold text-[#12233F] mb-1">Full Name</label>
                <input
                  type="text"
                  required
                  value={newUserName}
                  onChange={(e) => setNewUserName(e.target.value)}
                  placeholder="e.g. Gurpreet Singh"
                  className="w-full p-2 bg-[#FFFFFF] text-[#12233F] border border-[#E2E8F0] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#9333EA]"
                />
              </div>

              <div>
                <label className="block font-semibold text-[#12233F] mb-1">Institutional Email</label>
                <input
                  type="email"
                  required
                  value={newUserEmail}
                  onChange={(e) => setNewUserEmail(e.target.value)}
                  placeholder="e.g. name@your-institution.edu"
                  className="w-full p-2 bg-[#FFFFFF] text-[#12233F] border border-[#E2E8F0] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#9333EA]"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block font-semibold text-[#12233F] mb-1">Assigned Role</label>
                  <select
                    value={newUserRole}
                    onChange={(e) => setNewUserRole(e.target.value)}
                    className="w-full p-2 bg-[#FFFFFF] text-[#12233F] border border-[#E2E8F0] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#9333EA]"
                  >
                    {ROLES.filter((r) => r.id !== 'super-admin').map((r) => (
                      <option key={r.id} value={r.id}>{r.title}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block font-semibold text-[#12233F] mb-1">Department</label>
                  <select
                    value={newUserDept}
                    onChange={(e) => setNewUserDept(e.target.value)}
                    className="w-full p-2 bg-[#FFFFFF] text-[#12233F] border border-[#E2E8F0] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#9333EA]"
                  >
                    <option value="Sports Science & Biomechanics">Sports Science</option>
                    <option value="Athletics & Track">Athletics</option>
                    <option value="Physical Education">Physical Education</option>
                    <option value="Finance & Accounts">Finance</option>
                    <option value="Computer Science & AI">Computer Science</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block font-semibold text-[#12233F] mb-1">Initial Password</label>
                <input
                  type="password"
                  required
                  minLength={8}
                  value={newUserPassword}
                  onChange={(e) => setNewUserPassword(e.target.value)}
                  placeholder="At least 8 characters"
                  className="w-full p-2 bg-[#FFFFFF] text-[#12233F] border border-[#E2E8F0] rounded-lg focus:outline-none focus:ring-2 focus:ring-[#9333EA]"
                />
              </div>

              <div className="p-3 bg-[#F1F5F9] border border-[#E2E8F0] rounded-lg text-[11px] text-[#475569]">
                {live
                  ? 'Created in your organisation through platform/identity. Share the password with the user; email invitations and 2FA are not available yet.'
                  : 'Preview: the user is added to this page only and not saved.'}
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-3 py-1.5 rounded-lg border border-[#E2E8F0] hover:bg-[#F1F5F9] text-[#475569]"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="px-4 py-1.5 rounded-lg bg-[#F65B66] text-white font-semibold hover:bg-[#E9505C]"
                >
                  {saving ? 'Creating…' : 'Create User'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
