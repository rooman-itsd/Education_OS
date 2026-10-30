# Changelog — identity

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Plan user limit. `create_user` refuses the person who would take the organisation past its plan's `users`
  limit with `PlanLimitReachedError`, before anything is written; `POST /users` answers `409` with
  `{"code": "plan_limit_reached", "limit": "users", "allowed", "used"}`. The limit comes through the new
  `hooks.user_limit(db, organisation_id)` (None, the default, is no limit), which apps/backend wires to
  billing's `user_limit`, so identity imports nothing. New `count_active_users(db, organisation_id)`, the
  figure the limit and billing's usage count.
- No person may hold the `service` role. `create_user` refuses it before writing anything, so every way a
  role is assigned (`POST /users`, tenancy's registration, the super-admin seed) is covered, and `POST /users`
  answers 403. `current_principal` also drops it from any token, so a row or token that already carries it
  grants nothing. `service` is the catalogue holder of keys meant for no person, such as
  `notification:message:send`.
- Module scaffolded.
