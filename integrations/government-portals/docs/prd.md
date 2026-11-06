# government-portals: product requirements

Owner: Himanshu (@himanshu-rooman) · Backups: Faizan, Akshata · Kind: integration · Tier: common · Status: draft for review
Issue #143 · Depends on the integration-hub contracts (the regulatory-submission port).

## Purpose

Help an institution file its statutory returns and accreditation submissions to the government portals, in each
portal's own format, from the data Education OS already holds:

- **AISHE** (All India Survey on Higher Education): the annual Data Capture Format, DCF-I for universities, DCF-II for
  colleges (with teacher information), DCF-III for standalone institutions.
- **NIRF** (National Institutional Ranking Framework): the annual Data Capturing System submission per ranking
  category, and the copy of the submitted data the institution must publish on its own website.
- **NAAC**: IIQA (Institutional Information for Quality Assessment), SSR (Self Study Report), AQAR (Annual Quality
  Assurance Report), and responses to DVV (Data Validation and Verification) with metric-wise evidence.

It implements the **regulatory-submission** port ([contracts/ports/regulatory-submission.yaml](../contracts/ports/regulatory-submission.yaml))
and the Adapter contract ([contracts/ports/adapter.yaml](../contracts/ports/adapter.yaml)), both defined by
`platform/integration-hub`. Its callers are `modules/governance/regulatory-reports` (returns and their deadlines) and
`modules/governance/iqac-accreditation` (accreditation cycles), which today record filings but explicitly do not
generate the forms or talk to the portals (their PRDs' out-of-scope lists). This adapter is that missing piece.

## The honest constraint: no API

**None of these portals offers an API to institutions or their software vendors.** Each is a web application behind
the institution's own login (the AISHE nodal officer, the NIRF registered institution, the NAAC HEI account), with
forms to key in and files to upload. So the port is built around a **package** and a **recorded manual filing**:

1. The calling module gathers the data and evidence and calls `prepare_package`.
2. The adapter validates the data against the form's rules, writes the portal's own files, arranges the evidence, and
   returns a checklist of the portal steps.
3. A person signs in to the portal with the institution's login, keys in or uploads the package, and submits.
4. The person calls `record_manual_submission` (through the calling module's screen) with the portal's reference and
   the acknowledgement. The hub publishes `integration-hub.regulatory-package.submitted`.

`submit` exists in the port so that the day a portal opens an API (the One Nation One Data platform is meant to become
the single entry point) the adapter adds an API channel and no module changes. Until then `submit` answers
`manual_action_required`.

## What the portals are (sources)

| Portal | What an institution does | Source |
|---|---|---|
| AISHE | Registers, is approved by its approving authority (university or state nodal officer), gets an **AISHE code** and a nodal officer login. Fills the annual DCF; the older offline DCF upload has been replaced by **Web DCF** entry. College DCF-II includes teacher information. No API, no vendor registration. Helpdesk aishe-helpdesk@nic.in | https://aishe.gov.in (home page, Web DCF instruction manual link, reference dates); state and university circulars on DCF-I/II/III (secondary) |
| NIRF | Registers per discipline category and fills the online **Data Capturing System (DCS)** in the annual window (2026 cycle: deadline extended to 9 March 2026 on the official home page). Must publish the submitted data as a PDF under a "NIRF" tab on its own website. No API. Support techsupport@nirfindia.org | https://www.nirfindia.org/ (home page notices); framework https://www.nirfindia.org/nirfpdfcdn/2025/framework/Overall.pdf (not readable to our fetch; cited from its notice) |
| NAAC | IIQA in the last six months of accreditation validity, then SSR across seven criteria, then DVV in which the HEI answers metric-level queries with supporting documents; AQAR every year. Online entry with Excel data templates and evidence uploads. Accreditation is moving to a binary (accredited / not) model and data collection to the One Nation One Data platform | https://www.naac.gov.in, https://assessmentonline.naac.gov.in (not reachable to our fetch); NAAC press release on major reforms, 27 Jan 2024, https://www.ugc.gov.in/pdfnews/0821441_NAAC-Major-Reforms-in-Accreditation-Press-Release-27January-2024.pdf; Radhakrishnan Committee report, https://www.ugc.gov.in/pdfnews/1238790_Dr_Radhakrishnan-Committee-Final-Report.pdf |

**Not verified**: the current cycle's exact field lists and templates (most are visible only after an institution
signs in), the AQAR 2025-26 deadline, NAAC's per-file size limits, and whether the One Nation One Data platform is live
with any interface. The forms catalogue is therefore versioned per cycle and filled from the first institution's
portal access (open question 1).

## Design

### Forms catalogue (v1.0)

| form_code | Authority | Channel | Package contents |
|---|---|---|---|
| `aishe.dcf-i` | AISHE | manual_entry | Keying sheet in Web DCF section order (basic details, departments, programmes, enrolment by category, examination results, staff, infrastructure, finance), with totals cross-checked |
| `aishe.dcf-ii` | AISHE | manual_entry | As above for colleges, with the teacher information list |
| `aishe.dcf-iii` | AISHE | manual_entry | As above for standalone institutions |
| `nirf.dcs.<category>` (`overall`, `university`, `college`, `engineering`, `management`, `pharmacy`, `medical`, `law`, `architecture`, `dental`, `research`, `agriculture`, `innovation`, `open-university`, `skill-university`, `state-public-university`, `sdg`) | NIRF | manual_entry | Keying sheet by parameter (teaching, learning and resources; research and professional practice; graduation outcomes; outreach and inclusivity; perception), and the **website copy PDF** the institution must publish |
| `naac.iiqa` | NAAC | manual_entry | Keying sheet |
| `naac.ssr` | NAAC | manual_entry and file_upload | Per criterion and metric: the values, the filled data templates, the evidence files named by metric number, and a bundle |
| `naac.aqar` | NAAC | manual_entry and file_upload | As SSR, for the year |
| `naac.dvv-response` | NAAC | file_upload | Per DVV query: the clarification and the supporting documents, named by metric |

Each form has a `data_schema` (JSON Schema) and rules (required fields, cross-totals such as enrolment by gender equals
enrolment by category, year ranges). The categories and parameters follow the published frameworks of the cycle in
`GOVERNMENT_PORTALS_*_FORMAT`; a new cycle is a new adapter release with golden files, never a silent reuse.

### Rules

- **Never store a portal password**, and never automate a portal's web pages (no scraping, no robotic form filling).
  Filing is done by the institution's own nodal officer, who is accountable for the data (AISHE's nodal officer
  guidelines say so).
- Preparing again for the same `package_key` supersedes the previous package; a filed package is read-only.
- Evidence is referenced by document id; the adapter copies nothing out of `platform/documents` except into the
  package's bundle.

### Connection (per organisation, in integration-hub)

| Kind | Name | Notes |
|---|---|---|
| setting | `institution_type` | university, college or standalone; selects the DCF |
| setting | `aishe_code` | e.g. C-12345 |
| setting | `nirf_institute_id`, `nirf_categories` | The categories the institution applies in |
| setting | `naac_hei_id` | From the NAAC account |
| secret | none | The adapter holds no credentials |

Provider id `aishe`, `nirf` and `naac`, one connection each. There is no sandbox and nothing is sent, so the three
modes behave the same (the package is built locally) and the healthcheck is always healthy: a connection is created in
`sandbox` like any other and switched to `live` with no credentials to enter, which keeps the hub's rules uniform.

### Error mapping

| Situation | Port error |
|---|---|
| Data fails the form's schema or rules | `invalid_request`, with issues; status `invalid` |
| Form or cycle not in the catalogue | `unsupported` |
| `submit` on a manual form | `manual_action_required` |
| Recording a filing twice, or on a superseded package | `conflict` |
| Evidence document missing in platform/documents | `invalid_request` (issue on that metric) |

### Rate limits

None apply: nothing is sent to a portal.

## Sandbox and mock

There is nothing to mock on the provider side. Tests are **golden files**: for each form and cycle, a fixture data set
produces exactly the expected keying sheet, templates and website copy, and every rule has a failing fixture. The
first institution's filing in each cycle is the acceptance test: the person keys the package into the portal and
reports anything the portal refused (open question 1).

## Data model (summary)

Own schema `government_portals`; every table has `organisation_id` with row-level security.

| Entity | Key fields |
|---|---|
| package | id, organisation_id, package_key, form_code, format_version, period, status, issues, checklist, caller_module, caller_reference, submitted_on, submitted_by, portal_reference, acknowledgement_document_id, superseded_by |
| package_file | organisation_id, package_id, document_id, filename, role, metric |

The data used to prepare a package is not kept: it belongs to the calling module, which can prepare again.

## Personal data (DPDP Act 2023)

- AISHE and NIRF data is mostly aggregate (counts by category); the teacher information list in DCF-II names staff, and
  some NAAC evidence names students. Filing it is the institution's statutory duty.
- Package files live in `platform/documents` with access for the filing staff; nothing leaves Education OS except what a
  person uploads.
- The NIRF website copy is public by design: the adapter puts only the aggregate data NIRF requires in it.

## Permissions and events

- `government-portals:package:read` (org-admin): `GET /forms`, `GET /packages`, `GET /packages/{id}`.
- No events of its own: the hub publishes `integration-hub.regulatory-package.prepared` and `.submitted`.

## External dependencies

**Nothing for Rooman to apply for.** Each institution files with its own registration:

| What | With whom | Link |
|---|---|---|
| AISHE registration and nodal officer login (per institution) | AISHE, Ministry of Education; approved by the university or state nodal officer | https://aishe.gov.in |
| NIRF registration per category (per institution) | NIRF, Ministry of Education | https://www.nirfindia.org |
| NAAC HEI account (per institution) | NAAC | https://www.naac.gov.in |
| Read access for Rooman to one institution's portal screens, to copy the current cycle's field lists | The first institution's nodal officer | (open question 1) |

## Out of scope (v1.0)

- UGC portals other than AISHE (UAMP, UGC's own returns), AICTE, NBA, state portals: each is a new form in the
  catalogue once someone needs it.
- One Nation One Data, until it publishes an interface.
- Computing the numbers (enrolment counts, research output): the calling module or `platform/reporting` supplies them.

## Open questions (for review)

1. **Field lists per cycle (Himanshu, the governance office).** The current DCF, DCS and NAAC templates are visible
   only after an institution signs in. Which institution's nodal officer walks Rooman through them for the 2025-26
   AISHE, 2026 NIRF and current NAAC formats?
2. **Where the data comes from (Madhumita).** regulatory-reports records filings but does not compute numbers. Does it
   gather data from `platform/reporting` and call `prepare_package`, or does reporting call the port itself?
3. **NAAC binary accreditation.** Build SSR and AQAR to the current manual, and add the new framework when NAAC
   publishes its formats?
4. **NIRF website copy.** Generate the PDF only (proposed), or also publish it to the institution's website through
   web-portal-cms?
5. **Modes that mean nothing here.** These connections have no sandbox and send nothing, yet go through the hub's
   sandbox-then-live step like the rest (proposed), rather than a special case in the hub. Agreed?
6. **Operator view.** Should the `governance` role also hold `government-portals:package:read`?
