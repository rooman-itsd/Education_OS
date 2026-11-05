# Changelog — library

All notable changes to this module. Follows Keep a Changelog, semver per module.

## [Unreleased]
- Module scaffolded.
- Contracts proposed: catalogue of titles and copies, members, loan policies, issue, return, renew and lost,
  reservations with holds, fines, digital resources, and the self-service endpoints behind the Student
  widget `library.loans`; events; permissions and roles.
- PRD (`docs/prd.md`).
- Contract 0.2.0: `module.yaml` consumes `fees-accounts.invoice.paid` (agreed on #175). Students get the
  self-service keys through `library-member`, which the student layout lists in `module_roles`.
- User stories (`docs/user-stories.md`).
- Backend (`eos_library`): every operation of contract 0.2.0 in domain, application, infrastructure and api layers;
  exact money (Decimal); events to the outbox; an audit entry for every state change; the daily jobs that flag
  overdue loans once and expire uncollected holds; the consumer that marks a fine paid from
  `fees-accounts.invoice.paid`, registered on the `eos.event_consumers` entry point. Ids in request bodies must be
  uuids (422 otherwise).
- Migration `library_0001`: nine tables, each with `organisation_id` and the row-level-security policy.
- Tests: domain rules, every user-story area, the consumer, real `student` tokens, the cross-tenant leak test, and the
  migration against the models.
- Widget `library.loans` for the Student dashboard, built on `@eos/ui-kit`, with tests.
- Review fixes (#476): a loan keeps the daily fine rate and renewal limit it was issued with (a renewal takes the
  current rate), so a later `PUT /loan-policies` or a lost category policy no longer changes its fines; policy
  numbers, title year and money (10 integer digits, as `Numeric(12, 2)` holds) are bounded, 422 never a 500;
  duplicates that pass the check at the same moment answer 409 (copy, member, policy category, active reservation,
  now also a partial unique index); an issue locks the member; a cursor we never handed out starts from the top;
  the consumer scopes by the event envelope's organisation and ignores a non-string reference; the loans widget
  says "not available yet", "sign in again" or "no access" as the other widgets do.
