# Changelog — hr-payroll

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Widgets (#336): `leave-requests`, `payroll-run-status` and `joinings-and-exits` (HR Staff), with loading, empty and
  error-with-retry states; 36 tests. No payroll run yet (404 `not_found`) is the empty state, kept apart from an
  unmounted module. Frontend test dependencies added to the package. Enabling the module in `apps/frontend` is a
  separate PR.
- Module scaffolded.
- Contracts: employees with exits and service records, salaries, leave types, leave requests with approval,
  monthly payroll runs with separate preparer and approver, payslips, appraisals, self-service and the
  joinings-and-exits report behind the HR Staff widgets; events; permissions and roles.
- PRD (`docs/prd.md`).
