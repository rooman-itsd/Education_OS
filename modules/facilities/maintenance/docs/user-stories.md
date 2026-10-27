# maintenance: user stories

Roles are the module roles from `contracts/permissions.yaml`. Each academy maps its own roles to them (the
Facility / Inventory Staff, equipment manager and lab in-charge hold `maintenance-manager`). Each story lists the
API that serves it and the test that proves it (`backend/tests/`).

## Reporter (`maintenance-reporter`): anyone in the organisation

| # | Story | API | Test |
|---|---|---|---|
| R1 | As a reporter I report a fault on an asset, a bookable resource, an inventory unit or a described place, and the category's priority and assignee apply. | `POST /tickets` | `test_raise_applies_category_defaults_sla_and_number` |
| R2 | As a reporter I am told when the same fault on the same target is already open, so I can follow it instead. | `POST /tickets` → `possible_duplicates` | `test_raise_applies_category_defaults_sla_and_number` |
| R3 | As a reporter I see only my own tickets, never other people's. | `GET /tickets?scope=mine` | `test_scopes_and_visibility` |
| R4 | As a reporter I add notes to my ticket, but not time or cost. | `POST /tickets/{id}/work-entries` | `test_work_log_permissions_and_totals` |
| R5 | As a reporter I confirm a resolved ticket with a rating, or reopen it within the window when the fault comes back. | `POST /tickets/{id}/close`, `/reopen` | `test_full_lifecycle_with_hold_pausing_the_sla`, `test_reopen_within_the_window_goes_back_to_the_assignee` |
| R6 | As a reporter I cancel my ticket before work starts, for example as a duplicate. | `POST /tickets/{id}/cancel` | `test_cancel_rules` |

## Technician (`maintenance-technician`)

| # | Story | API | Test |
|---|---|---|---|
| T1 | As a technician I see the tickets assigned to me. | `GET /tickets?scope=assigned` | `test_scopes_and_visibility` |
| T2 | As a technician I start work, put it on hold with a reason (the SLA pauses), resume and resolve it with a note. | `POST /tickets/{id}/start`, `/hold`, `/resolve` | `test_full_lifecycle_with_hold_pausing_the_sla` |
| T3 | As a technician I log time, parts and cost, and the ticket shows the totals. | `POST /tickets/{id}/work-entries` | `test_work_log_permissions_and_totals` |
| T4 | As a technician I cannot work on a ticket that is not mine. | `POST /tickets/{id}/start` → 403 / 404 | `test_only_the_assignee_or_a_manager_works_on_a_ticket` |
| T5 | As a technician I tick off the checklist when I resolve a preventive ticket. | `POST /tickets/{id}/resolve` | `test_schedule_raises_preventive_tickets_without_drift` |

## Manager (`maintenance-manager`): Facility / Inventory Staff, equipment manager, lab in-charge

| # | Story | API | Test |
|---|---|---|---|
| M1 | As a manager I set up categories with a default priority, default assignees and SLA hours. | `POST /categories`, `PATCH /categories/{id}` | `test_categories_are_managed_by_managers_and_read_by_reporters` |
| M2 | As a manager I assign a ticket to a technician or an outside vendor, and reassign it. | `POST /tickets/{id}/assign` | `test_only_the_assignee_or_a_manager_works_on_a_ticket` |
| M3 | As a manager I triage: change priority (the SLA is recomputed), mark the target out of use. | `PATCH /tickets/{id}` | `test_priority_change_recomputes_the_sla` |
| M4 | As a manager I see every open ticket on my dashboard, past-SLA and urgent first, with counts. | `GET /tickets?scope=managed&open=true`, `GET /summary` (widget `tickets`) | `test_sweep_flags_breaches_once_and_widget_counts`, `TicketsWidget.test.tsx` |
| M5 | As a manager I plan preventive work on a fixed interval; tickets are raised ahead of the due date and the plan does not drift. | `POST /schedules`, `POST /schedules/{id}/raise-now` | `test_schedule_raises_preventive_tickets_without_drift` |
| M6 | As a manager I pause or delete a schedule; tickets it raised stay. | `PATCH /schedules/{id}`, `DELETE /schedules/{id}` | `test_schedule_pause_and_delete` |
| M7 | As a manager I cancel any ticket not yet resolved. | `POST /tickets/{id}/cancel` | `test_cancel_rules` |

## System

| # | Story | API | Test |
|---|---|---|---|
| S1 | A response or resolution target that passes is flagged and published once. | `application/jobs.py` `run_sweeps` | `test_sweep_flags_breaches_once_and_widget_counts` |
| S2 | A resolved ticket nobody confirms closes after `MAINTENANCE_AUTO_CLOSE_DAYS`. | `run_sweeps` | `test_sweep_auto_closes_resolved_tickets` |
| S3 | Preventive schedules raise their ticket `lead_days` before the due date, never two at once. | `run_sweeps` | `test_schedule_raises_preventive_tickets_without_drift` |
| S4 | One organisation never sees or changes another organisation's categories, tickets or schedules. | every query (`scoped`), RLS on Postgres | `test_no_cross_tenant_leak` |
| S5 | Every state change is recorded as an event (outbox) for audit, notification and the modules that own the targets. | `application/service.py` `_publish` | events asserted across `test_api.py` |
| S6 | The schema is created by the module's own Alembic chain with `organisation_id` and RLS on every table. | `db/migrations` | `test_upgrade_matches_models_and_downgrade_removes_tables` |
