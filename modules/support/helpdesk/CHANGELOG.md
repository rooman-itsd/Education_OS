# Changelog — helpdesk

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Contract 0.2.0: the profile roles `support-staff`, `org-admin` and `management` get the grants of
  `helpdesk-agent`, `helpdesk-admin` and `helpdesk-viewer`, the defaults the catalogue already named for them.
  Tokens carry profile roles, so before this a support-staff user was refused every helpdesk operation.
- Contract 0.1.1: `POST /tickets` answers 409 when `assign_to_me` is sent by a caller who is not a member of the
  category's default queue (the same `assignee_not_in_queue` as `/assign`), so a ticket is never assigned to an agent
  who cannot open it. A public reply by the ticket's own requester through `POST /tickets/{id}/comments` is no longer
  counted as the first agent response (`helpdesk.ticket.responded`, `first_responded_at`).
- Module scaffolded.
- Contracts proposed: support queues and categories, tickets raised by requesters or by agents on their
  behalf, assignment, public replies and internal notes, hold, resolve, cancel and links; self-service
  endpoints to raise, reply, confirm, reopen and withdraw; `GET /stats/open-by-priority` behind the Support
  Staff widget `helpdesk.open-by-priority`; ticket events for sla-management; permissions and roles.
- PRD (`docs/prd.md`).
- Domain rules, with unit tests: ticket statuses and the moves between them (start, hold with a reason, resolve,
  close, reopen, withdraw, cancel; replies and reclassifying by status), and the open-by-priority counts behind
  `helpdesk.open-by-priority`: every priority has a row, urgent first; `total_open` is the sum of the rows;
  `oldest_created_at` is the earliest open ticket of the row, or null; resolved, closed and cancelled tickets are
  not counted. The reopen window (`can_reopen`, 409 once it has passed) and the auto-close rule.
- Application layer: permission keys and checks, use-case errors with their HTTP status (409 for a refused move,
  422 for an invalid value, 403), and `GET /stats/open-by-priority` (permission, scope, 403 for `scope=all`
  without `helpdesk:ticket:read-all`, `queue_id` narrowing). `HELPDESK_*` settings with the `env.example`
  defaults. Contract-drift tests read `contracts/*.yaml`. `pyproject.toml`: test extras and package discovery.
- Models and the first Alembic revision (`helpdesk_0001`): queues, categories, tickets, comments, ticket links and
  the per-organisation ticket number sequence, prefixed `helpdesk_`, each with `organisation_id` and, on Postgres,
  row-level security; own version table `helpdesk_alembic_version`. A test upgrades a throwaway SQLite file,
  compares it with the models and downgrades.
- Audit entries (`helpdesk_audit_entry`, in the same first revision) for every state change, with the reason where
  the contract asks for one to be kept. Temporary until the audit SDK ships; the shared schema with `helpdesk_`
  prefixes and this table follow the architecture lead's decision for #113.
- Repository, use cases and HTTP routes for all 25 contract operations; every ticket event of `events.yaml`
  published to the `eos_core` outbox with exactly its listed fields; the daily auto-close job
  (`application/jobs.py`). A ticket raised with `assign_to_me` also publishes `helpdesk.ticket.assigned`.
- API, lifecycle, permission and job tests, the cross-tenant leak test (`eos_testing`), and a test that the routes
  match the contract's operations. `pyproject.toml` test extras: httpx and eos-testing.
