# inventory-equipment: user stories

Roles are the module roles from `contracts/permissions.yaml`. Each academy maps its own roles to them and names
the item in its vocabulary (`inventory-equipment.item`: "Instrument", "Costume / prop", "Lab equipment", ...).
Each story lists the API that serves it and the test that proves it (`backend/tests/`).

## Borrower (`inventory-equipment-borrower`): learners and instructors

| # | Story | API | Test |
|---|---|---|---|
| B1 | As a borrower I search the catalogue and see what is available to borrow now. | `GET /items?q=&available=true` | `test_catalogue_search` |
| B2 | As a borrower I request a loan with a due date and get it ready for pickup straight away when no approval is needed. | `POST /loans` | `test_full_loan_cycle_of_a_unit` |
| B3 | As a borrower I am told clearly why I cannot borrow (too long, too many, consumable, too many open loans). | `POST /loans` → 422 with `code` | `test_loan_rule_violations` |
| B4 | As a borrower I see my open loans and due dates on my dashboard, overdue first. | `GET /loans?scope=mine&open=true` (widget `my-loans`) | `test_full_loan_cycle_of_a_unit` |
| B5 | As a borrower I cancel a loan before pickup, and a reserved piece goes back on the shelf. | `POST /loans/{id}/cancel` | `test_approval_flow_and_reservation` |
| B6 | As a borrower I extend my loan once, if nobody is waiting for the item. | `POST /loans/{id}/extend` | `test_extension_rules` |

## Approver (`inventory-equipment-approver`)

| # | Story | API | Test |
|---|---|---|---|
| A1 | As an approver I see requests for the categories I look after, and nobody else's. | `GET /loans?scope=managed&status=requested` | `test_approval_flow_and_reservation` |
| A2 | As an approver I approve (the requested piece is reserved) or reject with a reason. | `POST /loans/{id}/approve`, `/reject` | `test_approval_flow_and_reservation`, `test_reject_needs_reason` |

## Store staff (`inventory-equipment-manager`): Facility / Inventory Staff, equipment manager, lab in-charge

| # | Story | API | Test |
|---|---|---|---|
| M1 | As staff I set up categories, stores and items in our own words, tracked per piece or by quantity. | `POST /categories`, `/locations`, `/items` | `test_stock_ledger_and_low_stock_events` |
| M2 | As staff I register tagged pieces, and cannot reuse a tag. | `POST /items/{id}/units` | `test_unit_status_changes_and_tracking_lock` |
| M3 | As staff I receive, issue, transfer, adjust and write off stock; every change is in the ledger and stock never goes negative. | `POST /movements`, `GET /movements`, `GET /stock` | `test_stock_ledger_and_low_stock_events` |
| M4 | As staff I see what is low against its reorder level, and procurement is told once per crossing. | `GET /low-stock` (widget `low-stock`), event `stock.ran-low` | `test_stock_ledger_and_low_stock_events` |
| M5 | As staff I hand out the exact pieces or quantities, take them back (partly, too) and record damage. | `POST /loans/{id}/hand-out`, `/return` | `test_full_loan_cycle_of_a_unit`, `test_quantity_loan_hand_out_partial_return_and_lost` |
| M6 | As staff I record lost items, and the loan closes with a loss. | `POST /loans/{id}/mark-lost` | `test_quantity_loan_hand_out_partial_return_and_lost` |
| M7 | As staff I see overdue loans with days late, and counts on my dashboard. | `GET /loans?scope=managed&status=overdue` (widget `overdue-loans`), `GET /summary` | `test_sweeps_mark_overdue_and_expire_pickups` |
| M8 | As staff I mark a piece in repair, missing or retired, and cannot change tracking once stock exists. | `PUT /units/{id}/status`, `PATCH /items/{id}` | `test_unit_status_changes_and_tracking_lock` |

## System

| # | Story | Where | Test |
|---|---|---|---|
| S1 | Loans past their due date become overdue; approved loans not picked up in time are cancelled. | `application/jobs.py` `run_sweeps` | `test_sweeps_mark_overdue_and_expire_pickups` |
| S2 | One organisation never sees or changes another organisation's catalogue, stock or loans. | every query (`scoped`), RLS on Postgres | `test_no_cross_tenant_leak` |
| S3 | Every state change is recorded as an event (outbox) for audit, notification, maintenance and procurement. | `application/service.py` `_publish` | events asserted across `test_api.py` |
| S4 | The schema is created by the module's own Alembic chain with `organisation_id` and RLS on every table. | `db/migrations` | `test_upgrade_matches_models_and_downgrade_removes_tables` |
