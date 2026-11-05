# transport: user stories

Owner: Tejaswini (@tejaswini-rooman) · Status: draft for review · Issue #111

Stories by role for the transport module. Each story follows `prd.md` and is bounded by the contract in
`contracts/openapi.yaml` (0.2.0), `events.yaml` and `permissions.yaml`; where a need is not in the contract it is
listed under [Gaps](#gaps-not-in-the-contract) instead of being written as a story. Paths are relative to
`/api/v1/transport`.

## Roles

| Role (`permissions.yaml`) | Who | Grants |
|---|---|---|
| `transport-rider` | Every student (the student layout lists it in `module_roles`), and staff riders | `self:read`, `self:request` |
| `transport-admin` | Transport office | `route:read`, `route:manage`, `vehicle:read`, `vehicle:manage`, `pass:read`, `pass:manage`, `tracking:read`, `notice:publish` |
| `transport-driver` | Driver of a route | `route:read`, `tracking:record` |
| `transport-viewer` | Management and org admin, read only | `route:read`, `vehicle:read`, `pass:read`, `tracking:read` |

All keys above are short for `transport:<resource>:<action>`. A call without the permission named for its endpoint
is refused with 403 and changes nothing. Wherever a story says "rider", the caller holds
`transport-rider`, directly or through the student layout; every endpoint behind its two self-service keys is limited
to the caller's own records.

## Rules every story inherits

- **R1 Tenant isolation.** Every record carries `organisation_id` and is protected by row-level security. Another
  organisation's record is never listed, and a request for it by id answers 404. The cross-tenant leak test passes.
- **R2 Events carry the tenant.** Every published event carries `organisation_id`.
- **R3 Audit.** Every state change writes an audit record with the actor.
- **R4 Nothing is deleted.** Passes are cancelled, rejected or expire; routes, vehicles and drivers are
  deactivated; notices expire or are withdrawn. Only positions are purged, after the retention period.
- **R5 Own data only.** `/me/*` returns only the caller's own passes and notices.
- **R6 No hard dependency.** Transport works when fees-accounts is not enabled; pass events simply raise no invoice.
- **R7 Test data.** No real rider or driver data in tests or seeds.

## 1. Stops and routes

**ST-1 Create and edit stops.** As the transport office, I record stops with a name and optional coordinates.
- `POST /stops` and `PATCH /stops/{id}` need `route:manage`. Latitude is -90..90, longitude -180..180.
- `GET /stops?q=` lists stops whose name contains `q`; staff and riders may read it.

**RO-1 Create a route.** As the transport office, I create a route with a code, name, direction label and its stops in
order with scheduled times (HH:MM).
- At least two stops, each once, each sequence once; unknown stops answer 404. The code is unique (409).

**RO-2 Change or deactivate a route.** `PATCH /routes/{id}` replaces the name, code and stops; optional fields left out
keep their value. A stop that is the boarding stop of a current pass or request cannot be removed (409
`stop_in_use`). `active: false` deactivates the route; it then takes no new passes.

**RO-3 Find a route.** As a rider, I list routes and their stops (`GET /routes`, `?active=`, `?stop_id=`) to choose one.
Staff also see one route's capacity and issued passes (`GET /routes/{id}`, `route:read`).

## 2. Fleet and compliance

**FL-1 Vehicles.** As the transport office, I add vehicles (registration number, unique; capacity; type; insurance,
fitness and permit expiry) and update or deactivate them (`vehicle:manage`). Capacity cannot drop below the
passes issued today on a route the vehicle serves (409 `capacity_below_passes`).

**FL-2 Drivers.** As the transport office, I add drivers with licence number and expiry, and a `person_id` when the
driver signs in to record trips.

**FL-3 Expiring documents.** `GET /vehicles?expiring_within_days=N` and `GET /drivers?expiring_within_days=N` list
those with a document already expired or expiring within N days.

**AS-1 Assign a vehicle and driver.** `PUT /routes/{id}/assignment` (`route:manage`) sets the route's vehicle and
driver. Refused (409) when either is inactive, or the vehicle's insurance or fitness, or the driver's licence, has
expired. A change publishes `transport.route.reassigned`; repeating the same assignment publishes nothing.

## 3. Passes

**PA-1 Request a pass.** As a rider, I request a pass for a route, boarding stop and period (`POST /me/passes`).
- The route is active, the stop is on it, the end is not before the start nor in the past.
- One open request or issued pass per person for overlapping dates (409 `overlapping_pass`).
- Publishes `transport.pass.requested`. `rider_type` is `student` for the student role, else `staff`.

**PA-2 Decide a request.** As the transport office, I issue or reject a requested pass (`POST /passes/{id}/decision`).
- Rejecting needs a reason and publishes `transport.pass.rejected`.
- Issuing publishes `transport.pass.issued` with what fees-accounts needs (person, rider type, route, stop, period).
- Issued passes overlapping the period never exceed the vehicle's capacity; a route without a vehicle has no
  seats. Going over needs `override_capacity` and a reason (409 `route_full` otherwise).

**PA-3 Issue directly.** `POST /passes` issues a pass to a person with the same checks; `rider_type` defaults to
`student`.

**PA-4 Cancel.** The office cancels any pass; a rider cancels their own (another's answers 404). A reason of at
least 3 characters is required. Cancelling an issued pass publishes `transport.pass.cancelled` with the date; a
cancelled request publishes nothing. Cancelling twice, or an expired pass, answers 409.

**PA-5 See passes.** A rider sees their passes, current first (`GET /me/passes`). Staff list passes by status, route
and person, paged (`GET /passes`, `pass:read`).

## 4. Trips and live position

**TR-1 Run a trip.** As the route's driver, I start a trip (`POST /trips`), send positions (1 to 100 per call), report
the delay, and end it (`tracking:record`).
- Only the route's current driver may start, record on and end its trips (409 `not_route_driver`).
- One running trip per route (409 `trip_running`). The route needs a vehicle, and the vehicle and driver must
  still pass the assignment checks on the day.
- Publishes `transport.trip.started`, `transport.trip.delayed` when the delay increases, and
  `transport.trip.completed`. Positions are never published.

**LV-1 Where is my bus.** As a rider with an issued pass valid today on the route, or as transport staff with
`tracking:read`, I see the running trip, its latest position, its delay and the stop it is at or nearing
(`GET /routes/{id}/live`); without a running trip the answer is null. A rider without such a pass gets 403.

## 5. Notices

**NO-1 Publish.** The office publishes a notice (delay, cancellation, route change, general) to one route or all
routes (`notice:publish`). A driver may publish only to the route they drive. Publishes
`transport.notice.published`. An expiry in the past answers 422.

**NO-2 Withdraw.** The office withdraws a current notice; withdrawing again answers 409. `GET /notices` shows every
notice with its status.

**WI-1 Student widget `transport.notices`.** As a rider, I see on my dashboard the current notices for the routes of my
issued passes plus notices to all routes, newest first (`GET /me/notices`, `self:read`). A pass request alone
does not bring a route's notices.

## 6. Daily jobs

**JB-1 Expire passes.** Issued passes past their end date become `expired`; `transport.pass.expired` goes out once each.

**JB-2 Flag documents.** Once per document and expiry date, 30 days before (`TRANSPORT_DOCUMENT_EXPIRY_NOTICE_DAYS`),
`transport.document.expiry-flagged` goes out for a vehicle's insurance, fitness or permit, or a driver's licence.

**JB-3 Purge positions.** Positions older than `TRANSPORT_POSITION_RETENTION_DAYS` (30) are deleted.

## Gaps (not in the contract)

- Names (`person_name`) are not cached yet: transport consumes no student-information or hr-payroll events.
- No screens for the office or drivers yet (later wave); only the Student widget is built.
- Notification of riders on reassignment, delay or notices is left to the notification service reading the events.
