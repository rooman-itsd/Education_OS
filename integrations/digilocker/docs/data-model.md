# digilocker: data model

Own schema, tables prefixed `digilocker_`. Every table has `organisation_id` and, on Postgres, the forced
`tenant_isolation` row-level-security policy (`db/migrations/versions/20261105_0001_initial.py`). The Alembic chain
has its own version table, `digilocker_alembic_version`.

| Table | Purpose |
|---|---|
| `digilocker_issued_document` | One document the institution issued, as DigiLocker can ask for it. Unique per organisation on `issuance_key`, on (`doc_kind`, `document_number`) and on `uri`. |
| `digilocker_pull_request_log` | One row per Pull URI or Pull Doc request answered, unique on (`channel`, `txn`) so a redelivery logs once. No search values, no Aadhaar. |
| `digilocker_issuance_history` | Append-only trail of state changes (issued, replaced, withdrawn, pushed, push_failed), written in the same transaction as the change. Codes only. |

## issued_document

| Column | Notes |
|---|---|
| `uri` | `<issuer_id>-<doc_type>-<document_number>`; characters outside `A-Za-z0-9._-` in the number become `_` |
| `document_id`, `sha256` | The final signed PDF in platform/documents and its hash. The file is re-hashed every time it is served; a changed file answers Status 0 |
| `search_key_hash` | HMAC-SHA256 (key `DIGILOCKER_SEARCH_KEY_PEPPER`) over organisation, doc type and the normalised search values. The values themselves are never stored |
| `holder_name_normalised`, `holder_dob` | What a Pull URI request is matched against, together with the hash |
| `wallet_account_id` | The holder's DigiLocker id, kept only when known, because an update (`U`) or delete (`D`) push needs it. Cleared once the delete is accepted |
| `data_xml` | The machine-readable copy for doc types with `has_xml`, built from the caller's `data` at issue time |
| `push_pending` | `A`, `U` or `D` while a push has not been accepted yet; a retried operation sends it again |
| `status` | `available_for_pull`, `pushed`, `withdrawn`. `pending_holder_account` and `failed` are in the contract's vocabulary; this adapter never sets them (an unknown account leaves the document available for pull, as the PRD says) |

Never stored: Aadhaar (the `UID` element of a Pull URI request is not read), the mobile number (used once to find the
DigiLocker account), search values in clear, tokens, API keys or client secrets.

## Personal data

Holder name (normalised) and date of birth are kept to answer pulls; withdrawing a document stops it being served, and
an erasure request withdraws first. The history table holds no personal data, so it can stay.
