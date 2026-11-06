# grievance: data model

Tables are prefixed `grievance_`, created by `db/migrations/versions/20261105_0001_initial.py` (revision `grievance_0001`,
version table `grievance_alembic_version`). Every table has `organisation_id` and the forced `tenant_isolation`
row-level-security policy on Postgres. Foreign keys stay inside the module; person ids come from identity, by id only.

| Table | Rows | Key columns |
|---|---|---|
| `grievance_committee` | A committee of one kind. Deactivated, never deleted. | `name` (unique per organisation), `kind` (`sgrc`, `anti_ragging`, `icc`, `ombudsperson`), `active` |
| `grievance_committee_member` | A person on a committee; the list is replaced as a whole. | `committee_id`, `person_id`, `role` (`chair`, `member`, `external_member`); unique per committee and person |
| `grievance_case` | A case. | `sequence` (per organisation, unique) and `number` (`GRV-000123`), `track`, `committee_id` (the committee it was filed with or transferred to), `complainant_id`, `respondent_person_id`, `respondent_description`, `category`, `description`, `incident_date`, `status`, `closure`, `not_admitted_reason`, `filed_at`, `acknowledged_at`, `decided_at`, `closed_at` |
| `grievance_proceeding` | A hearing, statement or note; committee only. | `grievance_id`, `kind`, `held_on`, `summary`, `recorded_by` |
| `grievance_update` | A message between committee and complainant. | `grievance_id`, `author_id`, `from_committee`, `body` |
| `grievance_decision` | The decision; one per case (unique `grievance_id`). | `outcome`, `findings`, `actions_recommended`, `decided_by`, `decided_at` |
| `grievance_appeal` | The appeal of an SGRC decision; one per case (unique `grievance_id`). | `committee_id` (ombudsperson), `reason`, `filed_at`, `outcome`, `outcome_note`, `decided_by`, `decided_at` |
| `grievance_audit_entry` | One row per change, and per read of case content by a committee member. | `actor`, `action`, `entity` (`case`, `committee`), `entity_id`, `reason`, `occurred_at` |

Worked out when read, never stored: `due_at`, `overdue` and `can_appeal` (from the `GRIEVANCE_*` settings and the clock).

Case numbers: `GRIEVANCE_CASE_NUMBER_PREFIX` plus a six-digit per-organisation sequence. On Postgres filing takes a
transaction-scoped advisory lock per organisation so two filings do not take the same number; the unique constraint on
`(organisation_id, sequence)` is the last guard (a lost race is a 409 `number_taken`, never a 500).

Nothing is deleted: cases end as `closed`, `not_admitted` or `withdrawn`; committees are deactivated.

Case text (`description`, respondent, proceedings, updates, decision, appeal) lives only in `grievance_case`,
`grievance_proceeding`, `grievance_update`, `grievance_decision` and `grievance_appeal`; events, notices and audit
entries never carry it.

Audit actions: `committee.created`, `committee.renamed`, `committee.members_changed`, `committee.activated`,
`committee.deactivated`, `case.filed`, `case.<from>_to_<to>` (status moves), `case.withdrawn`, `case.appealed`,
`case.decided`, `case.transferred`, `appeal.decided`, `update.added`, `proceeding.recorded`, `case.read`, `case.listed`.
