# placement-career: product requirements

Owner: Gokula Lakshmi (@gokulalakshmirooman-source) · Status: draft for review · Issue #337 (was #132)
Campus life · tier `common`

## Purpose

Campus placement for **jobs**: the organisation's company records, placement drives, job openings, student
applications and offers. Students see openings with their eligibility criteria and CTC and apply; the placement
officer shortlists, records offers and sees who is already placed. Contract: `contracts/openapi.yaml`, `events.yaml`,
`permissions.yaml`. Stories: [user-stories.md](user-stories.md).

No written product statement for placement existed before this module; the rules below are the owner's decisions on
#337 (see [Decisions](#decisions)).

## Users

Role ids are those of the dashboard layouts (`platform/identity/config/dashboards/`).

| Actor | Roles | Holds | Needs | Dashboard widget |
|---|---|---|---|---|
| Placement officer | placement-officer; industry-coordinator (hospitality), practicum-coordinator (teacher education) | `placement-career-officer` through the layout's `module_roles` | Keep company records, announce drives, post openings, shortlist, record offers, see placed students | `placement-career.drives` (`GET /reports/drives-upcoming`, placement-officer), `placement-career.openings` (`GET /reports/openings-summary`) |
| Viewer | industry-liaison (design and fashion) | `placement-career-viewer` | See companies, drives, openings and the summary; no individual applications | `placement-career.openings` (`GET /reports/openings-summary`) |
| Student | `student` and every layout that extends it (management-student, engineering-student, hospitality-trainee, law-student, ...) | the `student` grants | See open openings with criteria and CTC, apply with a self-declaration, follow their applications and offers, withdraw | `placement-career.openings` (`GET /me/openings`) |

Companies are records, not users: nobody from a company signs in. org-admin and management hold no placement-career
role in v1.0.

## Main flows

1. **Companies.** The officer records a company: name, industry, website, recruiter contact (staff only) and notes.
   An inactive company gets no new drives or openings.
2. **Drive.** A dated campus event of one company: date (and an end date for a drive over several days), venue,
   registration closing date, selection rounds (shown, not tracked) and eligibility criteria. Draft → scheduled
   (students see it) → completed, or cancelled while no opening of it has applications.
3. **Opening.** A job with title, description, location, CTC per annum, positions, eligibility criteria and the last
   day to apply. It belongs to a drive of the same company, or stands alone (off-campus or referral). Draft → open →
   closed, or cancelled while it has no applications. An opening in a drive opens once the drive is scheduled and stops
   taking applications on or before the drive date.
4. **Apply.** A student applies to an open opening up to and including its last day (IST), declaring that they meet
   the criteria, optionally with their programme, graduating year, CGPA and active backlogs. One application per
   student per opening; a withdrawn one cannot be resubmitted.
5. **Shortlist to offer.** The officer verifies the declaration and moves the application one step at a time:
   applied → shortlisted → in_process → offered (with the offer: CTC, joining date, notes) → accepted or declined
   (the officer records the student's answer). The officer can reject with a reason from applied, shortlisted or
   in_process; the student can withdraw from the same states.
6. **Placed.** A student with an accepted offer is flagged `student_placed` on every application the officer sees.
   Nothing is blocked.

## Rules

- Openings are jobs only. Internships, including those a management institute calls "Internship", are
  field-training openings and placements.
- Eligibility criteria are shown, never enforced. The student's declaration is not checked by the system.
- The application sequence is fixed: no skipping, no moving back. Every move is audited.
- No one-offer rule in v1.0: a placed student can still apply and receive offers.
- Students see the CTC of openings and of their own offers. They never see company contacts, other students'
  applications or the placed flag.
- Draft and cancelled drives and openings are visible only with the matching manage permission.
- Nothing is deleted: drives and openings are cancelled or closed, applications rejected or withdrawn.
- Business dates are Indian (Asia/Kolkata); timestamps are UTC. Money is exact decimal rupees.
- Every table carries `organisation_id` with row-level security; every event carries `organisation_id`.
- Event payloads carry ids and dates only: no names, declarations, offered CTC or company contacts.

## Integration points

| Direction | With | How |
|---|---|---|
| Publishes | notification (may consume) | drive, opening and application events; no module consumes them in v1.0 |
| Platform | identity, audit | through `packages/sdk` |
| Layouts | platform/identity | `module_roles` of placement-officer, industry-coordinator, practicum-coordinator (`placement-career-officer`) and industry-liaison (`placement-career-viewer`) |

placement-career reads nothing from other modules: no academic records, no field-training data.

## Out of scope (v1.0)

- Internships (field-training).
- Recruiter logins and a company portal.
- Automatic eligibility checks from academic records (planned once examinations publishes results).
- A one-offer or "dream offer" policy, per organisation as a setting later.
- Offer letters and résumés as documents, offer revocation, career counselling services.

## Decisions

Decided by the owner; see #337.

| # | Decision |
|---|---|
| P1 | An opening is a job only. Internships stay in field-training. |
| P2 | The placement officer posts openings and drives through a module role (`placement-career-officer`); industry-coordinator and practicum-coordinator get the same role. industry-liaison is view only (`placement-career-viewer`). Companies are records, not logins. |
| P3 | A drive is a dated campus event holding several openings. An opening can also exist without a drive. |
| P4 | Eligibility criteria are shown on the drive or opening. Students self-declare and the officer shortlists. There is no automatic eligibility check in v1.0. |
| P5 | Applications follow a fixed status sequence. There is no one-offer rule in v1.0, but students already placed are flagged to the officer. |
| P6 | Students can see the CTC. |
| P7 | Read access to openings is granted to the common `student` role, the way fees-accounts does it. |

## Open questions (for review)

These were not covered by the decisions above; the contract takes the most conservative option until the owner says
otherwise.

1. A drive belongs to one company, and its openings to that company (`company_mismatch`). Pool drives with several
   companies would need a change.
2. The officer records the student's answer to an offer (accepted or declined); students do not accept in the app.
3. The `student` role also gets `self:read` and `self:apply`, so students can apply (P4, P5). No separate learner
   module role is added.
4. A drive or opening with applications cannot be cancelled, only closed; nothing changes applications automatically.
5. industry-liaison (viewer) sees summary counts but not individual applications, which are students' personal data.
6. org-admin and management hold no placement-career role.
