# web-portal-cms — PRD

**Domain:** student-lifecycle · **Tier:** common · **Owner:** Praveen (@praveen-rooman)

## 1. Purpose

web-portal-cms is the organisation's public website: CMS-authored pages, announcements and
notices, and the public entry point for a **new organisation** to sign up to Education OS. It is
the front door, not the engine: the sign-up page it hosts composes two platform services that
already own the underlying business logic — `platform/billing` (plans) and `platform/tenancy`
(organisation registration) — rather than re-implementing registration here.

## 2. Users / actors

| Actor | Relationship |
|---|---|
| Public visitor | Browses CMS pages, announcements, and the pricing/sign-up page, with no account. |
| Prospective organisation (academy) | Chooses a plan and an academy type, fills in organisation and admin details, and submits a sign-up. Becomes the Organisation Admin once created. |
| CMS editor (organisation staff, once onboarded) | Authors and publishes pages and announcements for their own organisation's public site. |
| Super admin | Approves the new organisation's academic package after sign-up (`platform/tenancy`'s existing flow). Not a web-portal-cms actor; mentioned here only because the sign-up flow ends with them. |

## 3. Scope

**In scope**
- Public CMS: pages, announcements/notices, published vs. draft content, per organisation.
- The sign-up page: a public page that lets a prospective organisation pick a plan (data from
  `platform/billing`), pick an academy type (data from `platform/tenancy`), and submit the
  organisation + admin details **directly to `platform/tenancy`'s existing `/register` endpoint**.
- A confirmation/next-steps page shown after submission (email verification pending, then
  super-admin approval pending — both already owned by `platform/tenancy`).

**Explicitly out of scope**
- **Organisation registration itself.** `platform/tenancy` owns `POST /register`,
  `POST /register/verify`, `GET /academy-types`, and the `pending_verification → pending_approval
  → active` lifecycle (ADR-0005). web-portal-cms does not duplicate this logic, does not store an
  `Organisation` entity, and does not implement its own `/register`-equivalent endpoint. Its
  contract is not modified or extended by this module.
- **Plans and pricing data.** `platform/billing` owns `GET /plans` (already public) and all plan
  fields (price, limits, modules). web-portal-cms does not store or duplicate plan records.
- **Organisation Admin account creation.** Created by `platform/tenancy`'s `/register` as part of
  registering the organisation; web-portal-cms never creates a user account of any kind.
- **Student/applicant sign-up of any kind.** This page is for an organisation (an academy)
  signing up as a customer, never for a student or applicant. A student/Person record is created
  only by an authorised staff member in `student-information`, and an applicant's admission
  application is anonymous and unrelated to this flow (`admissions`). Nothing here creates,
  references, or depends on a Person or Application record.
- Super admin approval of the academic package — `platform/tenancy` + the admin screens in
  `apps/frontend/src/admin`, not this module.

## 4. Capabilities

1. Serve published CMS pages and announcements, publicly and per organisation.
2. Staff: create, edit, publish/unpublish and delete pages and announcements for their own
   organisation.
3. Serve the sign-up page's own content (marketing copy, terms-of-service page) as ordinary CMS
   pages, so the page is editable without a deploy.
4. Compose, client-side, the data needed to render the sign-up form: plans from
   `platform/billing`'s existing public `GET /plans`, academy types from `platform/tenancy`'s
   existing public `GET /academy-types`.
5. Submit the sign-up form directly to `platform/tenancy`'s existing public `POST /register`.
6. Show a confirmation page after submission, and handle the verification link
   (`platform/tenancy`'s existing `POST /register/verify`).

## 5. Important workflows

**Browsing the public site.**
A visitor reads published pages and announcements. No account is required. Draft content is
never served publicly.

**Organisation sign-up (the flow named in Issue #62).**

```
Visitor opens the sign-up page (web-portal-cms)
  → page loads plans from platform/billing GET /plans (public)
  → page loads academy types from platform/tenancy GET /academy-types (public)
  → visitor picks a plan and an academy type, fills organisation + admin details
  → page submits directly to platform/tenancy POST /register (public)
  → platform/tenancy creates the organisation (pending_verification) and its Organisation Admin,
    platform/billing starts the trial
  → web-portal-cms shows a confirmation page: "check your email to verify"
  → visitor clicks the verification link → platform/tenancy POST /register/verify
  → organisation becomes pending_approval
  → web-portal-cms shows a "waiting for approval" page
  → (outside this module) super admin approves the academic package
  → organisation becomes active; the new Organisation Admin can sign in
```

web-portal-cms's own backend does not sit between the sign-up page and `platform/tenancy`/
`platform/billing` for this flow — the frontend calls both directly, exactly as
`docs/architecture/ARCHITECTURE.md`'s existing registration-flow description shows
("sign-up page → tenancy.register"). This module's contract therefore adds no new endpoint for
registration itself; see §7 for exactly what is and isn't called.

**Editing the public site.**
A CMS editor (once their organisation is active) creates and publishes pages/announcements
scoped to their own organisation.

## 6. Business rules

- **This is organisation sign-up, not student or applicant sign-up.** Nothing in this module's
  scope, data model or contract creates a Person (`student-information`) or an Application
  (`admissions`) record. This was an explicit decision for Issue #62 and is treated as a hard
  boundary, not a style choice.
- **web-portal-cms does not become a second source of truth for organisations or plans.** It
  reads `platform/billing`'s plans and submits to `platform/tenancy`'s registration endpoint; it
  never stores a competing copy of either.
- CMS content (pages, announcements) belongs to exactly one organisation (`organisation_id`) once
  that organisation exists; the **sign-up page, its supporting marketing pages, and the plan
  list are the one part of this module's content that is pre-organisation** (there is no
  `organisation_id` yet for a visitor who hasn't signed up) and are served from a
  platform-level/public content set, not scoped to any one organisation.
- Draft content is never served from public read endpoints.

## 7. Integrations

- **platform/billing** (existing contract, not modified) — `GET /plans` is called directly by
  the sign-up page to render plan choices. No new endpoint is added to billing's contract.
- **platform/tenancy** (existing contract, not modified) — `GET /academy-types` is called to
  render academy-type choices; `POST /register` is called to submit the sign-up;
  `POST /register/verify` is called from the emailed verification link. No new endpoint is added
  to tenancy's contract, and this module never reads or writes tenancy's `organisation` table.
- **platform/notification** (not yet contracted) — expected to send the verification email once
  that module's contract exists; web-portal-cms does not send email itself.
- **platform/audit** — page/announcement publish and unpublish actions are audited.
- **student-information, admissions** — no integration. Explicitly not touched by this flow (see
  §6).

## 8. Permissions

See `contracts/permissions.yaml`. Summary: `web-portal-cms:page:manage`,
`web-portal-cms:announcement:manage`. Public read (pages, announcements, and the sign-up page's
own content) needs no permission key. The sign-up submission itself needs no web-portal-cms
permission because it is not a web-portal-cms endpoint — `platform/tenancy`'s `/register` is
already public (`security: []`) by its own contract.

## 9. Audit / state changes

Page/announcement create, update, publish, unpublish and delete are audited. The organisation
sign-up's own state changes (registered, verified, approved) are audited by `platform/tenancy`,
not duplicated here.

## 10. Tenant considerations

- Pages and announcements carry `organisation_id` with row-level security once an organisation
  exists; a public visitor browsing one organisation's site never sees another's content.
- The sign-up page and plan list are, by nature, pre-tenant content: they are not scoped to an
  `organisation_id` because no organisation exists yet for that visitor. This is a deliberate,
  narrow exception to "every table has `organisation_id`" (module-standard rule 11), limited to
  content that exists before any tenant does — the same reasoning `platform/tenancy`'s own
  `organisation` table already relies on ("the one schema whose tables are not themselves
  tenant-scoped, because they define the tenants").

## 11. Acceptance criteria for Issue #62 (Week 1)

- [ ] `docs/prd.md` describes the organisation onboarding/sign-up flow end to end, including which
      calls go to `platform/billing` and `platform/tenancy` directly, with no backend/frontend
      implementation code.
- [ ] `contracts/openapi.yaml` covers this module's own CMS surface (pages, announcements) and
      clearly documents, in its description, that registration and plan data are served by
      `platform/tenancy` and `platform/billing` respectively, without adding a duplicate endpoint.
- [ ] No endpoint, schema or event in this module's contracts creates or references a
      Person/Student record or an admissions Application.
- [ ] `platform/tenancy`'s and `platform/billing`'s contracts are not modified.
- [ ] `contracts/permissions.yaml` has no permission key required for public sign-up, since
      sign-up is not this module's own endpoint.
