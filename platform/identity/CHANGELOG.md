# Changelog — identity

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Every dashboard layout lists the module roles its profile role holds in `module_roles` (`projects-member`,
  `portfolio-learner`, `lms-instructor`, `field-training-coordinator`, ...), and the base `student` and `faculty`
  layouts list the roles of lms, library, transport, timetable-attendance and examinations. 221 of 278
  role/widget pairs are now backed (was 85); the 57 left are modules whose catalogue grants no role or no fitting
  role, listed in `apps/backend/tests/test_role_inheritance.py`. The dashboards README documents `module_roles`.
- An academy role now holds the permissions of the role its dashboard layout `extends` (`student` or `faculty`),
  through `eos_core.config.permissions_for`, so `current_principal`, every `require(...)` guard and `/auth/me`
  report them: a research scholar holds `fees-accounts:self:read`, a research supervisor
  `academic-management:roster:read`. Previously every academy role was refused by every module whose catalogue named
  only the common roles. The dashboards README says so, and a layout may not extend a privileged role.
- No person may hold the `service` role. `create_user` refuses it before writing anything, so every way a
  role is assigned (`POST /users`, tenancy's registration, the super-admin seed) is covered, and `POST /users`
  answers 403. `current_principal` also drops it from any token, so a row or token that already carries it
  grants nothing. `service` is the catalogue holder of keys meant for no person, such as
  `notification:message:send`.
- Module scaffolded.
