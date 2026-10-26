# web-portal-cms

**Domain:** student-lifecycle  
**Kind:** feature  
**Status:** implemented (M1 Foundation)  
**Owner:** Praveen (@praveen-rooman)

Public website, CMS marketing pages, announcements, and the organisation sign-up & approval experience.

---

## Scope

`web-portal-cms` owns the public-facing presence and the entry experience for prospective institutions:
- The public website shell, brand styling (`public.css`), responsive layouts, and hash-based navigation:
  - `#/` (`HomePage`): Hero section, value proposition, product pillars, student lifecycle journey, platform differentiators, and FAQ.
  - `#/features` (`FeaturesPage`): Comprehensive catalogue across Student Lifecycle, Academics & LMS, Practice & Experiential Learning, Facilities, Governance, Support, and Specialized Sports suites.
  - `#/signup` (`SignUpPage`): Live billing plans from `GET /api/v1/billing/plans`, trial journey breakdown, FAQ, and registration entry.
- Direct composition of platform services without duplicating logic:
  - Composes `platform/billing` for transparent plan tiers and trial duration.
  - Composes `platform/tenancy` for academy profile selection, organization registration, token verification, and Super Admin approval/rejection.
  - Composes `platform/identity` for login gating based on organisation activation status.

**Explicitly not this module's responsibility:**  
Organisation tenancy records and entitlements (`platform/tenancy`), plan definitions and subscription billing (`platform/billing`), creating Person/Student records (`student-information`), or the anonymous applicant admissions funnel (`admissions`). See [docs/prd.md](docs/prd.md) and [docs/features.md](docs/features.md) for architectural boundaries.

---

## Public Surface

- **API Contract:** [contracts/openapi.yaml](contracts/openapi.yaml)
- **Domain Events:** [contracts/events.yaml](contracts/events.yaml)
- **Permissions:** [contracts/permissions.yaml](contracts/permissions.yaml)

---

## Onboarding & Registration Lifecycle (M1 Foundation)

The end-to-end onboarding experience follows ADR-0004 (Institution Profiles) and ADR-0005 (Multi-Tenant SaaS):

```
Prospect signs up on Public Site
   ↓
Selects Academy Type (GET /api/v1/tenancy/academy-types)
   ↓
Submits Org & Admin Account (POST /api/v1/tenancy/register)
   • Org created in 'pending_verification' status on Trial Plan
   • Verification token generated & email notification sent
   ↓
Admin verifies email (POST /api/v1/tenancy/register/verify)
   • Org status transitions to 'pending_approval'
   • Sign-in refused with 401 until platform approval
   ↓
Super Admin Review Queue (GET /api/v1/tenancy/admin/organisations?status=pending_approval)
   ├── APPROVE (POST /api/v1/tenancy/admin/organisations/{id}/approve)
   │     • Org status becomes 'active'
   │     • Events published: tenancy.organisation.approved, tenancy.organisation.activated
   │     • Automated approval email sent to admin with sign-in link
   │     • Admin can now sign in and lands on Organisation Admin dashboard
   │
   └── REJECT (POST /api/v1/tenancy/admin/organisations/{id}/reject)
         • Org status updated to 'suspended' with reason
         • Rejection email sent to admin explaining the decision
```

---

## Email Notifications

All email triggers during the sign-up and approval flow pass through the platform notification service (`eos_core.notify.send_email`):
- **Verification Email:** Sent immediately upon registration with the 48-hour activation token.
- **Approval Email:** Sent to the administrator when the Super Admin approves the organization, confirming the academic package and linking to sign-in.
- **Rejection Email:** Sent to the applicant if the registration is rejected by the Super Admin, including the specific reason provided.

---

## Data Model & Isolation

- **No dedicated database tables:** As a client-facing feature module that composes core services, `web-portal-cms` maintains no database tables of its own (`module.yaml` has no `db/` schema).
- **Tenant Isolation:** All underlying tenancy records (`tenancy_organisation`, `tenancy_registration_token`, `tenancy_organisation_module`) are platform-scoped in the `tenancy` schema and protected by platform role-based access control.

---

## Testing & Verification

1. **Frontend Typechecks & Unit Tests:**
   - Typechecks pass cleanly across the package:
     ```powershell
     pnpm --filter @eos/web-portal-cms typecheck
     ```
2. **Backend Integration & Email Notification Tests:**
   - Verified in `apps/backend/tests/test_approval.py`:
     ```powershell
     .\.venv\Scripts\pytest.exe apps/backend/tests/test_approval.py -v
     ```
   - Covers token registration, verification, 401 protection while pending, Super Admin approval, approval email verification, rejection handling, and rejection email verification.
3. **End-to-End Onboarding Specification:**
   - Verified via Playwright in `tests/e2e/onboarding/register-approve-signin.spec.ts`.

---

## Directory Layout

| Path | Purpose |
|---|---|
| `docs/` | PRD, features reference, user stories, screens |
| `contracts/` | OpenAPI specs, events, permissions |
| `frontend/src/public/` | Public site shell (`PublicSite.tsx`), pages (`HomePage`, `FeaturesPage`, `SignUpPage`), components, and styles (`public.css`) |
| `frontend/src/api/` | Public API client fetching billing plans and institution types |
| `backend/` | Backend scaffold (business logic delegated to core platform services) |

---

## Porting this module to another repo

Follow [docs/architecture/module-standard.md](../../../docs/architecture/module-standard.md#portability-checklist).
