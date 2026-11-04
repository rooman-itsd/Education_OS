# Changelog — transport

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Module scaffolded.
- Contracts proposed: stops and routes, vehicles and drivers with compliance dates, route assignment, pass
  requests and passes, trips with live position and delay, notices, and the self-service endpoints behind
  the Student widget `transport.notices`; events; permissions and roles.
- PRD (`docs/prd.md`).
- Contract 0.2.0: `POST /passes` takes an optional `rider_type` (`student` or `staff`, default `student`), carried
  on `transport.pass.issued`. Students get the self-service keys through `transport-rider`, which the student layout
  lists in `module_roles`.
- User stories (`docs/user-stories.md`).
- Backend (`eos_transport`): every operation of contract 0.2.0 in domain, application, infrastructure and api layers;
  events to the outbox; an audit entry for every state change; the daily jobs that expire passes, flag expiring
  vehicle and driver documents once per expiry date, and purge positions after the retention period
  (`config/env.example`). Ids in request bodies must be uuids (422 otherwise).
- Migration `transport_0001`: eleven tables, each with `organisation_id` and the row-level-security policy.
- Tests: domain rules, every user-story area, real `student` tokens, the cross-tenant leak test, and the migration
  against the models.
- Widget `transport.notices` for the Student dashboard, built on `@eos/ui-kit`, with tests.
- Review fixes (#473): a role whose layout extends `student` requests passes as a student; duplicates that pass the
  check at the same moment answer 409 (route code, vehicle registration); a trip start locks the route, and pass
  requests of one person run one at a time on Postgres; capacity, stop sequence, delay, speed, reasons, notice body,
  `expiring_within_days` and instants are bounded (422, never a 500); a cursor we never handed out starts from the top;
  stop search takes `%` and `_` literally; the notices widget says "not available yet", "sign in again" or "no
  access" as the other widgets do.
