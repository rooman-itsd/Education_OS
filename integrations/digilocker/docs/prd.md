# digilocker: product requirements

Owner: Himanshu (@himanshu-rooman) · Backups: Faizan, Akshata · Kind: integration · Tier: common · Status: draft for review
Issue #141 · Depends on the integration-hub contracts (the certificate-issuance port).

## Purpose

Put the academic documents an institution issues (degrees, marksheets, grade cards, migration certificates) into
each student's DigiLocker, where employers, universities and government services accept them as originals; and, with a
person's consent, fetch a document someone else issued to them (an applicant's Class XII marksheet) so admissions does
not have to trust a scan.

It implements the **certificate-issuance** port ([contracts/ports/certificate-issuance.yaml](../contracts/ports/certificate-issuance.yaml))
and the Adapter contract ([contracts/ports/adapter.yaml](../contracts/ports/adapter.yaml)), both defined by
`platform/integration-hub`. No module calls DigiLocker: examinations calls the port and never knows which wallet
answers.

## What it is not

| Not this | That belongs to |
|---|---|
| Deciding a document is final, rendering and signing the PDF | the issuing module (examinations; who owns transcripts and certificates is examinations Q7) |
| Lodging award *data* with the National Academic Depository | `integrations/nad` (the academic-records port). NAD now runs on DigiLocker, but it is a separate registration and a separate upload |
| Connection settings, credentials, OAuth state, callbacks, retries | `platform/integration-hub` |
| Aadhaar-based issuance or eKYC | Out of scope (open question 2) |

## How DigiLocker works for an issuer (sources)

| Fact | Source |
|---|---|
| An institution registers as an **Issuer** on the DigiLocker partner portal; login works only after DigiLocker (NeGD, MeitY) approves and the activation link is used. The portal shows the **Issuer ID**, used as the organisation id in every URI | Partner's configuration manual, Issuer: https://cdn.apisetu.gov.in/portal/assets/workflow_issuer.pdf |
| A **demo environment** exists for building: demo citizen portal https://developers.digitallocker.gov.in/ and demo partner portal https://devpartners.digitallocker.gov.in | same manual |
| Two models. **Pull**: the issuer hosts two APIs (Pull URI Request: search by the student's details; Pull Doc Request: fetch by URI) that DigiLocker calls, XML over HTTPS POST, with an optional API key checked through a `keyhash`. **Push**: the issuer pushes URIs to residents' accounts (portal CSV, single API call, or CSV by API) | same manual; Pull API Specification v1.3, https://img1.digitallocker.gov.in//assets/img/digital_locker_pull_API_specification_v1_3.pdf; Dedicated Repository (Push) API Specification v1.7.2, https://img1.digitallocker.gov.in/assets/img/digital_locker_dedicated_repository_(push)_API_specification_v1_7_2.pdf |
| **Doc types** are codes; common ones exist, and DigiLocker may create a new one on request "but not always" | issuer manual |
| URI format `<IssuerId>-<DocType>-<DocId>` | Issuer specification (search excerpt) and the Requester spec's examples |
| **Push URI to Account**: `POST /public/account/1/pushuri` with `clientid`, `digilockerid`, `uri`, `doctype`, `description`, `docid`, `issuedate` (DDMMYYYY), `validfrom`, `validto`, `action` (A add, U update, D delete), `ts` (no older than 30 min) and `hmac` = SHA-256 over the client secret and those fields in order; 200 with no body. Only for a registered issuer that implemented the issuer APIs. `POST /public/account/2/verify` tells whether an account exists for a mobile number | Requester API Specification v1.12 (Sept 2023), https://cf-media.api-setu.in/resources/Requester-APISpecification-V1_12.pdf |
| **Requester (Authorised Partner)**: OAuth 2.0 authorization code with **PKCE S256 only**; `GET /public/oauth2/1/authorize` (`req_doctype`, `purpose` such as `educational` or `verification`, `consent_valid_till`), `POST /public/oauth2/1/token` (access and refresh tokens), `POST /public/oauth2/1/revoke`; `GET /oauth2/2/files/issued`; `GET /oauth2/1/file/uri` returns the file with an HMAC (SHA-256 of the content keyed by the client secret); `POST /oauth2/1/pull/pulldocument` pulls from an issuer with a fixed consent text shown to the user | Requester API Specification v1.12 |
| A registered Indian mobile number and a **server located in India** are required for API access | DigiLocker onboarding FAQ (search excerpt only), https://www.digilocker.gov.in/assets/FAQ%20DL%20EL_onboarding.pdf |
| Onboarding for issuers and requesters runs through API Setu | https://apisetu.gov.in, https://partners.digilocker.gov.in |

**Not verified** (the PDFs above were not all readable, and DigiLocker publishes no rate limits): the exact XML of the
Pull spec v1.3, the current sandbox base URL and how sandbox access is granted in 2026, whether `digilocker.meripehchaan.gov.in`
replaces `api.digitallocker.gov.in`, and rate limits. Each is confirmed against the specs DigiLocker sends at
onboarding; none changes the port.

## Design

### Issuing (port `issue`, `replace`, `withdraw`)

The adapter supports both models and uses **Pull as the default**, because Pull works for every student without
DigiLocker needing to know them in advance and without Aadhaar:

1. examinations (or whoever issues) calls `issue` with the signed PDF's document id and hash, the doc kind, the holder
   and the **search keys** the student will type in DigiLocker (roll number and year by default; configured per doc
   type on the connection).
2. The adapter records the document in its own schema: URI `<issuer_id>-<doc_type>-<document_number>`, the document id
   and hash, a hash of the normalised search keys, and the holder's name and date of birth for matching. Status
   `available_for_pull`.
3. **Push when possible.** If the connection has push enabled and the holder's DigiLocker id is known (from an earlier
   account link) or found with `account/2/verify` from a mobile number the caller passed, the adapter signs and sends
   Push URI (`action=A`) and the status becomes `pushed`. The mobile number is used once and not stored. If no account
   is found the status stays `available_for_pull`; the student can still pull it.
4. **Pull URI Request** arrives at the hub's provider-request route (`/inbound/digilocker/{key}/pull-uri`). The adapter
   checks `orgId`, the `keyhash` and the timestamp, then matches the doc type, the hashed search keys **and** the
   DigiLocker-verified name and date of birth. One match: answer the URI (and the PDF if the doc type is set to send it).
   None or several: Status 0. It never matches on Aadhaar, even if DigiLocker sends it.
5. **Pull Doc Request** returns the PDF (base64) and, where the doc type has one, the XML data copy. A withdrawn
   document answers Status 0. The hub publishes `integration-hub.certificate.pulled`.
6. `replace` swaps the document behind the same URI (and pushes `action=U` where pushed); `withdraw` marks it withdrawn
   (and pushes `action=D`).

### Fetching a person's documents (port `fetch_holder_document`, `list_holder_documents`)

For admissions and student-information to verify a document instead of trusting an upload. The person links their
DigiLocker through the hub (`POST /me/account-links`, port certificate-issuance, provider `digilocker`): PKCE, `purpose`
`educational`, `req_doctype` limited to what the module asked for, `consent_valid_till` from `DIGILOCKER_CONSENT_DAYS`.
The adapter then lists issued documents or fetches one by URI, **verifies the HMAC** over the file before keeping it,
and stores it in `platform/documents`. The link is revoked (`/oauth2/1/revoke`) when the person disconnects or the
consent expires.

### Connection (per organisation, in integration-hub)

| Kind | Name | Notes |
|---|---|---|
| setting | `issuer_id` | From the partner portal dashboard |
| setting | `doc_types` | `[{doc_kind, doc_type, search_fields, send_pdf_on_uri_request, has_xml}]` |
| setting | `push_enabled` | Push needs the issuer's app credentials and DigiLocker's permission |
| secret | `issuer_api_key` | The key DigiLocker uses in `keyhash` on Pull requests |
| secret | `push_client_id`, `push_client_secret` | The issuer's app, for Push URI HMAC |
| platform secret | `DIGILOCKER_REQUESTER_CLIENT_ID/SECRET` | Rooman's requester app, in `config/env.example` |

The hub shows the two callback URLs to register on the partner portal (`.../pull-uri`, `.../pull-doc`).

### Error mapping

| DigiLocker answer | Port error | Retryable |
|---|---|---|
| Network error, timeout, TLS failure | `transport_unavailable` | yes |
| HTTP 5xx | `provider_error` | yes |
| HTTP 429 (if ever sent) | `throttled` | yes |
| HTTP 401 or 403, `invalid_client`, HMAC refused | `auth_failed` | no |
| `ts` refused as stale | `provider_error` (we sign again on retry) | yes |
| HTTP 400, invalid doc type, malformed field | `invalid_request` | no |
| Requester token expired and refresh refused, consent expired | `consent_required` | no |
| No such URI | `not_found` | no |
| Hash of the stored file differs from `document_sha256` | `invalid_request` (never sent) | no |

Provider text never leaves the adapter; only the code, and DigiLocker's own error code as `provider_code`.

### Rate limits

DigiLocker publishes none. The adapter sends at most `1` push per document and spreads a batch of `issue` calls through
the hub's queue; on any 429 the hub holds the connection's queue. Pull requests are answered from the local index, so
their volume costs nothing upstream.

## Sandbox and mock

- **Sandbox**: the DigiLocker demo partner portal (devpartners.digitallocker.gov.in) and demo citizen accounts, once
  Rooman (or the first institution) is given access. The Pull channels are tested by registering the sandbox URLs there.
- **Mock (until then, and in CI)**: recorded request and response pairs built from the Requester v1.12 spec and the Pull
  v1.3 spec, replayed with no network: push (accepted, HMAC refused, stale ts), account verify, OAuth token exchange
  and refresh, issued-files list, file by URI with a correct and a wrong HMAC, and Pull URI and Pull Doc requests signed
  with a known key. The contract tests run against the mock and, when `DIGILOCKER_SANDBOX_*` is set, against sandbox.
- v1.0 ships with the mock and the sandbox path built; each institution goes live when DigiLocker approves it as an
  issuer (lead's decision, 5 Nov 2026).

## Data model (summary)

Own schema `digilocker`; every table has `organisation_id` with row-level security.

| Entity | Key fields |
|---|---|
| issued_document | id, organisation_id, issuance_key, doc_kind, doc_type, uri, document_id, sha256, document_number, person_id, holder_name_normalised, holder_dob, search_key_hash, status, issued_on, valid_from, valid_to, pushed_at, withdrawn_at, last_pulled_at |
| pull_request_log | organisation_id, txn, channel, doc_type, matched (boolean), issued_document_id, received_at (no search values, no Aadhaar) |

## Personal data (DPDP Act 2023)

- Issuing is done by the institution for the student's own benefit, under the institution's lawful basis for its
  academic records; the student chooses whether to pull. Fetching someone's document always needs their consent at
  DigiLocker, for a stated purpose, with an expiry.
- Stored: what is needed to answer a pull (hashed search keys, normalised name, date of birth) and the document
  reference. Never Aadhaar, never the mobile number, never the search values in clear.
- DigiLocker is a Government of India service hosted in India; the onboarding FAQ requires the issuer's server to be in
  India, which the Proxmox deployment satisfies.
- Withdrawing a document stops it being served; deleting a student's records (erasure) withdraws their documents first.

## Permissions and events

- `digilocker:issuance:read` (org-admin): the read-only `GET /issuances` view.
- No events of its own: the hub publishes `integration-hub.certificate.issued`, `.withdrawn`, `.pulled` and the delivery
  events.

## External dependencies (what Rooman must apply for)

| What | With whom | How | Needed for |
|---|---|---|---|
| Issuer registration, **per institution** (each gets its own Issuer ID) | DigiLocker, NeGD (MeitY) | Partner portal https://partners.digilocker.gov.in (API Setu https://apisetu.gov.in); approval by email | Live issuing |
| Doc type codes for degree, provisional, marksheet, grade card, migration certificate, with search parameters | DigiLocker issuer team | Requested during issuer onboarding | Live issuing |
| Permission to Push URI to accounts, and the issuer app credentials | DigiLocker | During issuer onboarding | Push (Pull works without it) |
| **Requester (Authorised Partner) app** for Rooman, purpose educational, with the redirect URI | DigiLocker, NeGD | Partner portal, requester registration | Fetching applicants' documents |
| Sandbox access (demo partner portal) and the current Pull and Push specs | DigiLocker | Partner portal or the onboarding contact | Sandbox testing |

## Out of scope (v1.0)

- Aadhaar-seeded issuance (Dedicated Repository Push by Aadhaar) and eKYC (open question 2).
- DigiLocker's e-sign or document signing: the PDF arrives signed from the issuing module.
- Bulk CSV push through the partner portal: the adapter pushes one URI per document through the API.

## Open questions (for review)

1. **Pull by default (Himanshu).** Pull works for every student without knowing their DigiLocker account; Push is
   added where the account is known. Agreed, or Push first?
2. **Aadhaar (Faizan).** Issuance against Aadhaar is the other Push path. Proposed: never, because storing or sending
   Aadhaar brings Aadhaar Act obligations Education OS has not taken on.
3. **Who is the issuer (Faizan, lead).** Each institution registers as its own issuer (proposed; DigiLocker issues the
   Issuer ID to the institution), or can Rooman act as a technology partner for many?
4. **Requester app.** One Rooman requester app for every institution (proposed), or each institution registers its own?
5. **Search keys.** Roll number plus year of passing, matched with name and date of birth, as the default for every
   doc type? Confirm with examinations (Akshata).
6. **Result fields.** The XML data copy needs fields from `examinations.result.published` (examinations Q12).
7. **Operator view.** Should `examination-staff` also hold `digilocker:issuance:read`?
