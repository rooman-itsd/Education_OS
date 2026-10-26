# asset-management: user stories

Roles are the module roles from `contracts/permissions.yaml`. Each academy maps its own roles to them (Facility /
Inventory Staff hold `asset-management-manager`, Finance Staff hold `asset-management-finance`). Each story lists the
API that serves it and the test that proves it (`backend/tests/`).

## Manager (`asset-management-manager`): Facility / Inventory Staff

| # | Story | API | Test |
|---|---|---|---|
| M1 | As a manager I set up categories with depreciation defaults and a verification interval. | `POST /categories`, `PATCH /categories/{id}` | `test_categories_validate_depreciation_and_refuse_nulls` |
| M2 | As a manager I register an asset with its cost; a tag is generated when I give none, and I see its book value. | `POST /assets` | `test_register_generates_tags_and_values_the_asset` |
| M3 | As a manager I edit an asset's details, but location, department and custodian change only by transfer. | `PATCH /assets/{id}` | `test_edit_status_and_transfers` |
| M4 | As a manager I mark an asset in repair, idle or missing with a reason. | `PUT /assets/{id}/status` | `test_edit_status_and_transfers` |
| M5 | As a manager I move an asset to another place, department or custodian, and keep its history. | `POST /assets/{id}/transfers`, `GET /assets/{id}/transfers` | `test_edit_status_and_transfers` |
| M6 | As a manager I see on my dashboard which assets are overdue or due for verification, and how open audits are going. | `GET /verifications/due` (widget `audit-due`) | `test_verification_due_cycle_and_overdue_sweep`, `AuditDueWidget.test.tsx` |
| M7 | As a manager I plan a verification cycle, start it, and close it so its results update the assets. | `POST /verification-cycles`, `/start`, `/close` | `test_verification_due_cycle_and_overdue_sweep` |
| M8 | As a manager I carry out an approved disposal and the system works out book value and gain or loss. | `POST /disposals/{id}/complete` | `test_disposal_request_decide_and_complete` |

## Verifier (`asset-management-verifier`)

| # | Story | API | Test |
|---|---|---|---|
| V1 | As a verifier I record found, missing, damaged or relocated for assets by scanning their tag. | `POST /verification-cycles/{id}/lines` | `test_verification_due_cycle_and_overdue_sweep` |
| V2 | As a verifier I see which lines are still pending. | `GET /verification-cycles/{id}/lines?result=pending` | `test_verification_due_cycle_and_overdue_sweep` |

## Custodian (`asset-management-custodian`)

| # | Story | API | Test |
|---|---|---|---|
| C1 | As a custodian I see only the assets in my care. | `GET /assets`, `GET /assets/{id}` | `test_custodians_see_only_their_assets` |
| C2 | As a custodian I request disposal of an asset in my care, and withdraw it while it is open. | `POST /disposals`, `POST /disposals/{id}/cancel` | `test_disposal_request_decide_and_complete` |

## Finance (`asset-management-finance`)

| # | Story | API | Test |
|---|---|---|---|
| F1 | As finance I calculate depreciation for a period as a draft, recalculate or delete it, and post it to lock it. | `POST /depreciation-runs`, `DELETE /depreciation-runs/{id}`, `POST /depreciation-runs/{id}/post` | `test_depreciation_runs_draft_post_and_lock` |
| F2 | As finance I cannot post a later period before an earlier one, or change a posted period. | `POST /depreciation-runs/{id}/post` → 409 | `test_depreciation_runs_draft_post_and_lock` |
| F3 | As finance I see an asset's posted depreciation and its projected schedule to the end of its life. | `GET /assets/{id}/depreciation` | `test_depreciation_runs_draft_post_and_lock` |
| F4 | As finance I approve or reject disposal requests, never my own. | `POST /disposals/{id}/approve`, `/reject` | `test_disposal_request_decide_and_complete`, `test_requester_cannot_decide_their_own_disposal` |
| F5 | As finance I see totals: assets by status, cost and book value, verification and disposal backlogs, expiring warranties. | `GET /summary` | `test_summary_counts` |

## System

| # | Story | API | Test |
|---|---|---|---|
| S1 | An asset past its verification date publishes `verification-overdue` once per due date. | `application/jobs.py` `run_sweeps` | `test_verification_due_cycle_and_overdue_sweep` |
| S2 | Two registrations at once never get the same generated tag. | `repo.next_tag_number` lock, retry on the unique constraint | `test_a_generated_tag_that_collides_is_retried_once` |
| S3 | One organisation never sees or changes another organisation's assets, cycles, runs or disposals. | every query (`scoped`), RLS on Postgres | `test_no_cross_tenant_leak` |
| S4 | Every state change is recorded as an event (outbox) for audit, notification, finance and maintenance. | `application/service.py` `_publish` | events asserted across `test_api.py` |
| S5 | The schema is created by the module's own Alembic chain with `organisation_id` and RLS on every table. | `db/migrations` | `test_upgrade_matches_models_and_downgrade_removes_tables` |
