# amc-vendor-support: product requirements

Owner: Madhumita (@madhumitha-rooman) · Status: draft for review · Week 1 task (issue linked in the PR)
Global support suite · tier `common` (every academy type enables it)

## Purpose

AMC contracts, vendor support engagements, renewals (`module.yaml`). An organisation keeps annual maintenance
contracts (AMCs) with outside vendors for lifts, generators, air conditioning, lab instruments, servers, software and
similar. This module records each contract (vendor, period, coverage, response terms, what it covers), the support
calls and service visits made to the vendor under it, and its renewal. Vendors themselves, purchase orders, invoices
and payments stay in procurement. The contract is `contracts/openapi.yaml`, `events.yaml` and `permissions.yaml`.

## Users and what they need

| Role (profile role → module role, proposed; open question 6) | Needs | Dashboard widget |
|---|---|---|
| Support Staff, Facility Staff (`support-staff`, `facility-staff` → `amc-vendor-support-coordinator`) | Find the contract that covers an item, raise a call or visit with the vendor, record the vendor's response and resolution, see contracts about to expire | `amc-vendor-support.contracts-expiring` (`GET /stats/contracts-expiring`) |
| Org admin (`org-admin` → `amc-vendor-support-contract-manager`) | Record and activate contracts, list what they cover, terminate and renew them; everything a coordinator does | `amc-vendor-support.contracts-expiring` |
| Management, Finance Staff (`management`, `finance-staff` → `amc-vendor-support-viewer`) | Read contracts, coverage and engagements | — |

## Main flows

1. **Record a contract.** A contract manager records an AMC as a draft: the vendor (`vendor_id` from procurement),
   title, coverage type (`comprehensive`: parts and labour; `non_comprehensive`: labour only), scope, start and end
   dates, value, an optional reference to the procurement purchase order, response and resolution hours, preventive
   visits per year, the vendor's support contacts, an owner and how many days before the end date renewal should
   start (`renewal_notice_days`). It gets a per-organisation number (`AMC-000012`).
2. **List what it covers.** Covered items are added and removed while the contract is a draft or active. Each item
   has a description, and optionally a reference to an asset in asset-management (`{module: asset-management,
   entity: asset, id}`).
3. **Activate.** The contract manager activates a draft (`draft → active`). Publishes
   `amc-vendor-support.contract.activated`.
4. **Find coverage.** Anyone with read access asks which active contracts cover a given record, for example an asset,
   with `GET /coverage`. Maintenance and asset screens can use it to choose the AMC to reference.
5. **Raise an engagement.** A coordinator raises a breakdown call or a preventive visit against an active contract
   that has not expired, optionally for one covered item and with references to the maintenance ticket, helpdesk
   ticket or incident behind it. It gets a number (`AVS-000034`) and status `open`, and records when the vendor was
   told and the vendor's own call reference.
6. **Track the engagement.** The coordinator records the vendor's response (`open → in_progress`), the resolution
   with a note (`in_progress → resolved`) and closes it (`resolved → closed`). An engagement raised in error is
   cancelled from `open` or `in_progress`. Whether the vendor responded and resolved within the contract's hours is
   worked out when read (`within_terms`).
7. **Expiry.** A contract is **expiring** when it is active and its end date is within `renewal_notice_days`, and
   **expired** when it is active and its end date has passed. Both are worked out when read; there is no timer and
   no expiry event in v1.
8. **Renew.** The contract manager starts a renewal, which creates a draft successor copied from the contract with the
   next period. Activating the successor marks the original `renewed`. Publishes
   `amc-vendor-support.contract.renewed` (in addition to `contract.activated` for the successor).
9. **Terminate.** The contract manager ends an active contract early with a reason and an effective date
   (`active → terminated`). Open engagements under it stay open until they are resolved or cancelled. Publishes
   `amc-vendor-support.contract.terminated`.

### Statuses

```
Contract (stored):   draft → active → terminated
                     active → renewed            (when its successor is activated)
Contract (on read):  expiring = active and end_date within renewal_notice_days
                     expired  = active and end_date passed

Engagement:          open → in_progress → resolved → closed
                     open or in_progress → cancelled
```

## Rules

- Every table carries `organisation_id` with row-level security; every event carries `organisation_id`.
- Every state change writes an audit record through `packages/sdk`: contracts, covered items, engagements.
- Vendors belong to procurement. A contract stores `vendor_id` only; vendor details are read from procurement's
  published API (`GET /vendors/{id}`). No vendor data is copied into this module.
- References to other modules use `{module, entity, id}` by id only, with no foreign keys and no check against the
  other module.
- A contract's end date is after its start date. Only a draft can be edited freely; an active contract can change its
  owner, contacts, renewal notice and covered items only. Terms (dates, value, coverage type, response hours) change
  through a renewal.
- An engagement can only be raised against an active contract that has not expired, and a covered item named on it
  must belong to that contract.
- A contract has at most one successor; a renewal starts from an active contract only.
- Nothing is deleted: contracts are terminated or renewed, engagements cancelled. A covered item added by mistake can
  be removed, and the removal is audited.
- Event payloads carry ids, numbers, dates and status only, never scope text, contacts or engagement notes.
- No dependency on another module being enabled. No real vendor or contract data in tests or seeds.

## Data model (summary)

| Entity | Key fields |
|---|---|
| AmcContract | id, number, vendor_id, title, coverage_type, scope, start_date, end_date, value (amount, currency), purchase_order_reference, response_hours, resolution_hours, preventive_visits_per_year, vendor_contacts [name, phone, email], owner_id, renewal_notice_days, status, renewed_from_id, renewed_to_id, activated_at, terminated_at, termination_reason |
| CoveredItem | id, contract_id, description, reference (optional, e.g. an asset) |
| Engagement | id, number, contract_id, kind (breakdown_call, preventive_visit), description, covered_item_id, references, vendor_call_reference, status, reported_at, vendor_responded_at, resolved_at, resolution_note, closed_at, raised_by |

## Dashboard widget

| Widget id | Dashboard | Endpoint | Permission | Shows |
|---|---|---|---|---|
| `amc-vendor-support.contracts-expiring` | Support Staff | `GET /stats/contracts-expiring?within_days=` | `amc-vendor-support:contract:read` | Active contracts ending within the window (default `AMC_VENDOR_SUPPORT_EXPIRY_WINDOW_DAYS`) and active contracts already past their end date, soonest first, with number, vendor id, title, end date and whether a renewal draft exists |

The widget implementation is out of scope for this PR; this PR defines only the endpoint contract.

## Events

| Event | What it is for | Current consumers |
|---|---|---|
| `amc-vendor-support.contract.activated` | Coverage started. Lets modules that hold an AMC reference (asset-management, maintenance) know the contract is in force. | None yet (open question 5) |
| `amc-vendor-support.contract.renewed` | The original contract was succeeded by the activated renewal, so holders of the old reference can move to the new one. | None yet (open question 5) |
| `amc-vendor-support.contract.terminated` | Coverage ended early. | None yet (open question 5) |

Engagements publish no public event in v1; no module needs one.

## Integration points

| Direction | With | How |
|---|---|---|
| Publishes | anyone | the three events above (`events.yaml`) |
| Consumes | none in v1 | |
| Platform | identity, audit | through `packages/sdk`: permission checks; audit |
| References | procurement | `vendor_id` (a procurement vendor); `purchase_order_reference` `{module: procurement, entity: purchase-order, id}` |
| References | asset-management | covered items `{module: asset-management, entity: asset, id}`. Assets hold their own `amc_reference` to a contract here |
| References | maintenance, helpdesk, incident-management | engagement references to a maintenance ticket, helpdesk ticket or incident. Maintenance vendor assignments hold their own `amc_reference` to a contract here |
| Serves | maintenance, asset-management screens | `GET /coverage` to find the active contracts covering a record |

## Configuration

`config/env.example`: `AMC_VENDOR_SUPPORT_CONTRACT_NUMBER_PREFIX`, `AMC_VENDOR_SUPPORT_ENGAGEMENT_NUMBER_PREFIX`,
`AMC_VENDOR_SUPPORT_EXPIRY_WINDOW_DAYS`, `AMC_VENDOR_SUPPORT_DEFAULT_CURRENCY`.

## Out of scope (v1)

- Vendor registration, approval, suspension and blacklisting (procurement).
- Purchase orders, tenders for renewals, vendor invoices and payments (procurement, fees-accounts).
- Carrying out repairs (maintenance); the asset register and warranties (asset-management).
- SLA clocks and breach tracking (sla-management covers helpdesk tickets only in v1).
- Contract documents and vendor service reports as attachments (open question 4).
- Renewal reminders and expiry events (open question 3); automatic renewal.
- A vendor portal or vendor log-ins.

## Open questions (for review)

1. **Vendor master (Gokula Lakshmi, procurement).** AMC contracts reference procurement's `vendor_id` and copy no vendor
   data. Must a vendor be `approved` in procurement before a contract can be activated, and is reading
   `GET /vendors/{id}` the agreed way to show vendor details?
2. **Vendor blacklisting.** procurement publishes `procurement.vendor.blacklisted`. v1 does not consume it. Should a
   later version flag or block contracts with a blacklisted vendor?
3. **Renewal reminders (Himanshu).** Expiring and expired are worked out when read and shown in the widget. Reminders or
   an expiry event would need the scheduler, whose contract is proposed in PR #189 and not merged. Wanted later?
4. **Contract documents.** `platform/documents` has no contract, so signed contracts and vendor reports cannot be
   attached in v1. Add them when that contract exists?
5. **Asset and maintenance sync (Ashritha).** Should asset-management set an asset's `amc_reference` from
   `contract.activated` and move it on `contract.renewed`, and should maintenance raise an engagement here when it
   assigns a ticket to an AMC vendor? Each needs a change in that module's own PR.
6. **Roles (Faizan).** Who manages AMCs (org admin, admin office, facility staff), and should roles be module roles
   mapped to profile roles as proposed here, or named after profile roles? The repository does not fix the convention yet.
7. **Vendor response tracking.** `within_terms` is worked out when read. Should vendor response times ever be tracked by
   sla-management? Not in its v1.
8. **Event format (Himanshu, Faizan).** This contract follows the convention on `main`: `organisation_id` in each payload
   and a file-level `version`. The event-bus contract proposed in PR #189 puts `organisation_id` in the envelope only and
   declares `version` on every event.
