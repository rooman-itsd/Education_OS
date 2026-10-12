# Changelog — hostel

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Module scaffolded.
- Contracts proposed: hostels and rooms, room requests and allocation with check-in and check-out, mess menu,
  leave requests, visitor log, discipline incidents, notices, and the self-service endpoints behind the
  Student widget `hostel.notices`; events; permissions and roles.
- PRD (`docs/prd.md`).
- Contract 0.2.0: gate pass. Security records a resident leaving and returning on an approved leave request
  (`POST /leave-requests/{id}/gate-out` and `/gate-in`, leave status `out`, event `hostel.leave.departed`,
  permission `hostel:gate:record` for `hostel-security` and `hostel-warden`; security may list leave requests).
- Permissions: the profile role `student` gets `hostel:self:read` and `hostel:self:request`, so students need no
  hostel-specific role. `hostel-resident` stays for residents who are not students.
