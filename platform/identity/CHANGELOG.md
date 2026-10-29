# Changelog — identity

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- No person may hold the `service` role. `create_user` refuses it before writing anything, so every way a
  role is assigned (`POST /users`, tenancy's registration, the super-admin seed) is covered, and `POST /users`
  answers 403. `current_principal` also drops it from any token, so a row or token that already carries it
  grants nothing. `service` is the catalogue holder of keys meant for no person, such as
  `notification:message:send`.
- Module scaffolded.
