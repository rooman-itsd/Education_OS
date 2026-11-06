# external-university-portals: product requirements

Owner: Himanshu (@himanshu-rooman) · Backups: Faizan, Akshata · Kind: integration · Tier: common · Status: draft for review
Issue #146 · Depends on the integration-hub contracts (the inter-institution-records port).

## Purpose

Students move between institutions: a semester abroad, a twinning programme, a transfer, a partner's summer school.
Each time, records cross: our transcript goes to the partner, the partner's results come back and have to be
recognised. Today that is a PDF by email and a person retyping grades. This adapter makes the exchange a recorded step
with known formats:

- **Out:** a learner's transcript of records written in the partner's format and delivered over the partner's channel.
- **In:** a partner's file read into one normalised shape, with every line it could not map, for a person in the
  consuming module to review and accept.

It implements the **inter-institution-records** port ([contracts/ports/inter-institution-records.yaml](../contracts/ports/inter-institution-records.yaml))
and the Adapter contract ([contracts/ports/adapter.yaml](../contracts/ports/adapter.yaml)), both defined by
`platform/integration-hub`. Expected callers: examinations (outgoing transcripts), enrolment-registration and
academic-management (recognising incoming credits), admissions (transfer applicants), student-information (exchange
students).

## What it is not

| Not this | That belongs to |
|---|---|
| Deciding equivalence and accepting credits | the consuming module and the institution's equivalence committee; the adapter only maps and suggests |
| Indian credit transfer between HEIs | the Academic Bank of Credits, through `integrations/nad` (academic-records port). Under the UGC ABC Regulations 2021 credits move through ABC, credited by the HEI |
| Putting documents in a student's DigiLocker | `integrations/digilocker` |
| Rendering and signing the transcript PDF | the issuing module (examinations Q7) |
| Mobility agreements, nominations, learning agreements | not in v1.0 (Erasmus Without Paper, open question 3) |

## The landscape (sources)

| Route | What it is | Machine interface | Fit for v1.0 | Source |
|---|---|---|---|---|
| **File exchange** (PDF transcript, partner's CSV template) | What almost every partner does today, by email or the partner's portal | none | **Default** | — |
| **EMREX** | European network for students to move their results: a national client (EMC) asks a data provider (EMP); results travel as **ELMO XML** (based on CEN EN 15981, EuroLMAI); a central registry (EMREG) lists providers. Members: Chile, Croatia, Finland, Germany, Netherlands, Norway, Poland, Sweden; no India node | Open specs and code (`elmo-schemas`, `emrex-client`, `EMP-mockup`) | **ELMO XML as a file format** in v1.0; joining the network later | https://emrex.eu/technical/, https://emrex.eu/about/, https://github.com/emrex-eu |
| **Europass Digital Credentials (EDC)** | Credentials in JSON-LD, an application profile of the **European Learning Model**, aligned with **W3C Verifiable Credentials 1.1**, electronically sealed; open-source issuer, viewer and wallet | Open specs; no issuer registration documented | **Export** in v1.0 (open question 2 on sealing) | https://europass.europa.eu/en/information-developers, https://www.w3.org/TR/vc-data-model-1.1/ |
| **Erasmus Without Paper (EWP)** | Network APIs between European HEIs (inter-institutional agreements, learning agreements, mobilities); each HEI's host publishes a discovery manifest, a central registry reads it, requests are signed with HTTP Signatures; a development registry exists | Open specs on GitHub | Later, only if Erasmus partners ask | https://github.com/erasmus-without-paper/ewp-specs-architecture |
| Groningen Declaration | Principles for student data portability; no technical interface | none | Nothing to build | https://www.feani.org/gdn-groningen-declaration-network |
| Parchment / Digitary, My eQuals, PESC transcripts | Commercial transcript networks (Digitary and Parchment have combined; Parchment powers My eQuals in Australia and New Zealand) | by contract only | Out of scope | https://www.int.parchment.com/en-au/myequals-solutions |

**Not verified**: EMREX's joining steps, whether EWP admits non-European HEIs, the current ELMO and ELM version numbers
(pinned at build from the repositories above), and any public API for the commercial networks.

## Design

### Partners are connections

Each partner institution is one integration-hub connection (port inter-institution-records), so partners are added by
configuration, not code:

| Kind | Name | Notes |
|---|---|---|
| setting | `partner_id`, `name`, `country`, `institution_code` (Erasmus code, AISHE code, PIC) | |
| setting | `formats_out`, `formats_in` | Subset of pdf, csv, elmo_xml, edc_jsonld |
| setting | `channel` | download, email or partner_portal (api later) |
| setting | `email`, `portal_url` | Where to deliver |
| setting | `csv_mapping` | Column mapping for the partner's own spreadsheet |
| setting | `grade_conversion`, `credit_conversion` | Suggestions shown to the reviewer, never applied silently |
| secret | `signing_key`, `signing_certificate` | The institution's key for signed ELMO and EDC exports (open question 2) |

Provider ids: `file` (PDF and CSV), `elmo` (ELMO XML), `edc` (Europass). Modes: `mock` and `sandbox` validate files
against the published schemas without delivering; `live` delivers.

### Out: export and send

1. The calling module calls `export_records` with the normalised transcript (close to ELM and ELMO: learner, issuer,
   programme, entries with credits, credit system, grade, grade scheme, term) and, for PDF, the signed PDF it rendered.
2. The adapter writes the format, validates it against the schema (ELMO XSD, ELM SHACL or JSON Schema), signs it where
   configured (XML Signature for ELMO; a Verifiable Credential proof for EDC), stores it in `platform/documents`, and
   records the exchange.
3. `send_records` delivers by the partner's channel:
   - **download** and **partner_portal**: `manual_action_required` with the file and steps; a person sends or uploads it
     and calls `record_manual_delivery` with the partner's reference;
   - **email**: through `platform/notification` to the partner's registered address, with a **time-limited download
     link** (`EXTERNAL_UNIVERSITY_PORTALS_LINK_TTL_HOURS`) rather than an attachment, because messaging-providers does not
     send attachments and a transcript should not sit in mailboxes indefinitely.
4. The hub publishes `integration-hub.inter-institution-record.exchanged`.

### In: import for review

1. The calling module stores the partner's file in `platform/documents` and calls `import_records` with the partner and
   format.
2. The adapter parses it: ELMO XML (verifying its signature when present), EDC JSON-LD (verifying the credential proof),
   or CSV with the partner's mapping. A PDF transcript is not parsed (`unsupported`): it is kept and keyed in by a person.
3. It returns the normalised transcript, `integrity` (verified, unsigned or failed) and every unmapped line. **Nothing is
   accepted here**: credits and grades become the student's record only when the consuming module's reviewer accepts
   them.

### Error mapping

| Situation | Port error |
|---|---|
| Transcript fails the target format's schema | `invalid_request`, with the failing paths |
| Format not accepted by the partner, or PDF import | `unsupported` |
| Delivery by download or partner portal | `manual_action_required` |
| Email delivery: notification unavailable | `transport_unavailable` (retryable) |
| Signature on an imported file does not verify | not an error: `integrity: failed`, shown to the reviewer |
| Recording a delivery twice | `conflict` |

### Rate limits

None: no partner API is called in v1.0.

## Sandbox and mock

Nothing to call, so tests are **golden files**: a fixture transcript produces exact CSV, ELMO XML and EDC JSON-LD, each
validated against the published schema (ELMO XSDs from `emrex-eu/elmo-schemas`; the EDC validator and viewer from the
Europass open-source tools); imports of known-good, tampered and partially unmappable files; EMREX's `EMP-mockup` for
the day the API channel is built.

## Data model (summary)

Own schema `external_university_portals`; every table has `organisation_id` with row-level security.

| Entity | Key fields |
|---|---|
| exchange | id, organisation_id, connection_id (partner), exchange_key, direction, person_id, format, channel, status, document_id, sha256, integrity, unmapped (positions and reasons), caller_module, caller_reference, delivered_on, delivered_by, partner_reference |

The transcript content is not kept here after the file is written or parsed; the source of truth is the calling module.

## Personal data (DPDP Act 2023)

- A transcript is the student's personal data. Sending it to a partner is for the student's own mobility or transfer;
  the calling module records the student's request or consent before calling `send_records` (open question 4).
- **Cross-border transfer**: the DPDP Act allows transfer abroad except to countries the government restricts by
  notification; the adapter refuses delivery to a partner whose `country` is on a configured restricted list.
- Email delivery uses an expiring link, not an attachment. Imported files keep the partner's data only as long as the
  consuming module's record requires.

## Permissions and events

- `external-university-portals:exchange:read` (org-admin): `GET /exchanges`, `GET /exchanges/{id}`.
- No events of its own: the hub publishes `integration-hub.inter-institution-record.exchanged` and the delivery events.

## External dependencies (what Rooman must apply for)

| What | With whom | How | Needed for |
|---|---|---|---|
| Nothing for file, ELMO and EDC exchange in v1.0 | — | — | — |
| A signing certificate per institution for signed exports; a qualified electronic seal if a European partner requires eIDAS-level EDC | A certifying authority (India: a licensed CA under the CCA; EU: a qualified trust service provider) | Per institution | Signed ELMO and EDC (open question 2) |
| EMREX data-provider registration in EMREG | The EMREX network | https://emrex.eu ("How to join") | Joining the network (later) |
| EWP registration (manifest in the EWP registry) | The EWP network (European Commission, EUF) | https://github.com/erasmus-without-paper/ewp-specs-architecture | EWP APIs (later) |

## Out of scope (v1.0)

- EWP APIs and joining the EMREX network as a live data provider (open question 3).
- Commercial transcript networks (Parchment, Digitary, My eQuals, PESC).
- Mobility agreements and learning agreements.
- Automatic recognition of credits.

## Open questions (for review)

1. **First partners (Himanshu, lead).** Which partner institutions exist for v1.0, and what do they send and accept?
   File exchange is assumed to cover all of them.
2. **Signing.** Sign ELMO and EDC exports with an institution certificate (proposed, open question for each
   institution), ship them unsigned in v1.0, or wait for a qualified seal where a European partner needs one?
3. **EWP and EMREX network membership.** Only if an Erasmus or Nordic partner asks?
4. **Consent before sending.** Which module records the student's request to send their transcript (examinations,
   student-information)?
5. **Credit conversion.** Suggested conversions (ECTS to Indian credits) are shown to the reviewer, never applied
   automatically. Who maintains the conversion tables: each institution per partner (proposed)?
