# facility-booking: user stories

Roles are the module roles from `contracts/permissions.yaml`. Each academy maps its own roles to them and
names the resource in its vocabulary (`facility-booking.resource`: "Practice room", "Lab / skills room", ...).
Each story lists the API that serves it and the test that proves it (`backend/tests/`).

## Booker (`facility-booking-user`): learners and instructors

| # | Story | API | Test |
|---|---|---|---|
| U1 | As a booker I find resources by type, capacity, features or free time, so I can pick one that suits me. | `GET /resources?q=&min_capacity=&free_from=&free_to=` | `test_resource_search_and_free_filter` |
| U2 | As a booker I see when a resource is free this week, without seeing who holds the busy slots. | `GET /resources/{id}/availability` | `test_availability_hides_holder_from_users` |
| U3 | As a booker I book a free slot and get it confirmed straight away when no approval is needed. | `POST /bookings` | `test_book_a_free_resource` |
| U4 | As a booker I am told clearly why a slot cannot be booked (taken, closed, too long, misaligned, in the past). | `POST /bookings` → 409 / 422 with `code` | `test_double_booking_is_refused_and_hides_who_holds_the_slot`, `test_rule_violations_return_422_with_codes` |
| U5 | As an instructor I book the same slot every week for a term, skipping weeks that are already taken. | `POST /bookings` with `recurrence`, `skip_conflicts` | `test_recurring_booking_and_series_cancel` |
| U6 | As a booker I see my upcoming bookings on my dashboard. | `GET /bookings?scope=mine&from=now` (widget `my-bookings`) | `test_widget_queries_and_summary` |
| U7 | As a booker I move or cancel my booking before it starts, and the slot is freed for others. | `PATCH /bookings/{id}`, `POST /bookings/{id}/cancel` | `test_reschedule_and_cancel` |
| U8 | As a booker I check in when I arrive, so my booking is not released as a no-show. | `POST /bookings/{id}/check-in` | `test_check_in_no_show_and_sweeps` |
| U9 | As an instructor I cancel all remaining weeks of a recurring booking at once. | `POST /series/{id}/cancel` | `test_recurring_booking_and_series_cancel` |

## Approver (`facility-booking-approver`): HoD, lab in-charge, studio instructor

| # | Story | API | Test |
|---|---|---|---|
| A1 | As an approver I see the pending requests for the resources I look after, and nobody else's. | `GET /bookings?scope=managed&status=pending` | `test_approval_flow`, `test_widget_queries_and_summary` |
| A2 | As an approver I approve a request, or reject it with a reason the booker can read. | `POST /bookings/{id}/approve`, `/reject` | `test_approval_flow`, `test_reject_needs_reason` |
| A3 | As an approver I cannot decide on resources I am not listed for. | `POST /bookings/{id}/approve` → 404 | `test_approval_flow` |

## Facility / Inventory Staff (`facility-booking-manager`)

| # | Story | API | Test |
|---|---|---|---|
| M1 | As staff I set up resource types and resources in our own words, with capacity, features and approvers. | `POST /resource-types`, `POST /resources` | `test_book_a_free_resource` |
| M2 | As staff I set opening hours and close a resource for an exam or a holiday. | `PUT /resources/{id}/opening-hours`, `POST /resources/{id}/blackouts` | `test_rule_violations_return_422_with_codes` |
| M3 | As staff I take a resource out of service and get the list of bookings to move; none are cancelled silently. | `PUT /resources/{id}/status` | `test_out_of_service_blocks_bookings_and_lists_affected` |
| M4 | As staff I book for someone else, and restrict a resource to certain roles and its capacity. | `POST /bookings` with `booked_for` | `test_booking_for_someone_else_needs_manage`, `test_role_restricted_resource_and_capacity` |
| M5 | As staff I see today's bookings and counts (pending, no-shows, out of service) on my dashboard. | `GET /bookings?scope=managed&date=today`, `GET /summary` (widget `bookings-today`) | `test_widget_queries_and_summary` |
| M6 | As staff I see who holds a busy slot and record a no-show. | `GET /resources/{id}/availability`, `POST /bookings/{id}/no-show` | `test_availability_hides_holder_from_users`, `test_check_in_no_show_and_sweeps` |
| M7 | As staff I cancel anyone's booking, always giving a reason. | `POST /bookings/{id}/cancel` | `test_reschedule_and_cancel` |

## System

| # | Story | Where | Test |
|---|---|---|---|
| S1 | Bookings not checked in within the grace period become no-shows; finished ones become completed. | `application/jobs.py` `run_sweeps` | `test_check_in_no_show_and_sweeps` |
| S2 | One organisation never sees or changes another organisation's resources or bookings. | every query (`scoped`), RLS on Postgres | `test_no_cross_tenant_leak` |
| S3 | Every state change is recorded as an event (outbox) for audit and notification. | `application/service.py` `_publish` | events asserted across `test_api.py` |
| S4 | The database schema is created by the module's own Alembic chain, with `organisation_id` and RLS on every table. | `db/migrations` | `test_upgrade_matches_models_and_downgrade_removes_tables` |
