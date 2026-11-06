"""publish_awards, correct_awards and publish_credits: validate every row, refuse the whole batch with row errors if
any is invalid, otherwise write the depository's upload file and return manual_action_required with the steps.

Nothing is sent: v1.0 has no API channel (the specs are not public yet). The submission, its files and, for awards,
the lodged-award keys are recorded in one transaction. A retry with the same batch_key and the same batch answers
from the record; the same key with another batch is a conflict, unless the first was rejected (it is replaced)."""

from __future__ import annotations

import hashlib
import re
from datetime import date, datetime

from eos_core.db import scoped
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain.errors import AdapterError
from ..domain.models import LodgedAward, Submission, SubmissionFile
from ..domain.rules import (
    AWARD_COLUMNS,
    CREDIT_COLUMNS,
    RowError,
    apaar_hash,
    award_row,
    credit_rows,
    payload_digest,
    render,
    validate_awards,
    validate_credits,
)
from ..infrastructure.config import KNOWN_TEMPLATE_VERSIONS, Config
from .runtime import Runtime
from .schemas import ConnectionSettings, Context, CorrectAwardsInput, PublishAwardsInput, PublishCreditsInput

NAD_PORTAL = "https://nad.digilocker.gov.in"
ABC_PORTAL = "https://www.abc.gov.in"
CHUNK = 400  # keys per IN (...) query, under SQLite's variable limit
_SAFE = re.compile(r"[^A-Za-z0-9._-]")


def _check_version(cfg: Config, which: str) -> str:
    version = cfg.awards_template_version if which == "awards" else cfg.credits_template_version
    if version not in KNOWN_TEMPLATE_VERSIONS[which]:
        # Never write a file the portal would reject: an unknown version is refused, not guessed.
        raise AdapterError("not_configured", f"this adapter does not know {which} CSV template version {version}")
    return version


def _session_ok(session: str) -> None:
    if int(session[5:]) != (int(session[:4]) + 1) % 100:
        raise AdapterError("invalid_request", "session must be two consecutive years, like 2025-26")


def _output(sub: Submission, files: list[SubmissionFile]) -> dict:
    return {
        "submission_id": sub.id,
        "status": sub.status,
        "upload_files": [{"document_id": f.document_id, "filename": f.filename, "rows": f.rows} for f in files],
        "steps": list(sub.steps or []),
        "row_errors": list(sub.row_errors or []),
    }


def _files(db: Session, sub_id: str) -> list[SubmissionFile]:
    return list(
        db.scalars(
            scoped(db, select(SubmissionFile).where(SubmissionFile.submission_id == sub_id), SubmissionFile).order_by(
                SubmissionFile.filename
            )
        )
    )


def _steps(depository: str, label: str, n_files: int) -> list[str]:
    portal = NAD_PORTAL if depository == "nad" else ABC_PORTAL
    name = "NAD" if depository == "nad" else "ABC"
    return [
        f"Download the {n_files} upload file(s) listed here from the documents store.",
        f"Sign in to the {name} portal ({portal}) as the institution's authorised person.",
        (f"Upload each file, choose the certificate template {label}, review it and publish."
         if depository == "nad" else "Upload each file under the credit upload option and submit it."),
        "Record the upload in Education OS: the date, who uploaded it and the portal's reference.",
    ]  # fmt: skip


def _split(sizes: list[int], max_rows: int) -> list[tuple[int, int]]:
    """Index ranges [start, end) over records so a file holds at most max_rows file rows (one record at least)."""
    out, start, rows = [], 0, 0
    for i, n in enumerate(sizes):
        if i > start and rows + n > max_rows:
            out.append((start, i))
            start, rows = i, 0
        rows += n
    out.append((start, len(sizes)))
    return out


def _lodged(db: Session, award_kind: str, numbers: list[str]) -> dict[str, LodgedAward]:
    found: dict[str, LodgedAward] = {}
    for i in range(0, len(numbers), CHUNK):
        q = select(LodgedAward).where(
            LodgedAward.award_kind == award_kind, LodgedAward.award_number.in_(numbers[i : i + CHUNK])
        )
        for row in db.scalars(scoped(db, q, LodgedAward)):
            found[row.award_number] = row
    return found


def _existing(db: Session, batch_key: str) -> Submission | None:
    return db.scalar(scoped(db, select(Submission).where(Submission.batch_key == batch_key), Submission))


def _replay(db: Session, existing: Submission, digest: str, kind: str) -> dict | None:
    """The answer for a retried batch, None when the earlier rejected batch is to be replaced."""
    if existing.kind != kind:
        raise AdapterError("conflict", "this batch_key was used for another kind of submission")
    if existing.payload_digest == digest:
        return _output(existing, _files(db, existing.id))
    if existing.status != "rejected":
        raise AdapterError("conflict", "this batch_key was used for a different batch")
    return None


def _reject(
    db: Session,
    ctx: Context,
    sub: Submission | None,
    fields: dict,
    errors: list[RowError],
    bad: int,
    total: int,
    now: datetime,
) -> dict:
    """Record a refused batch (row errors only) so a retry of the same batch answers the same."""
    sub = _store(db, ctx, sub, now, {**fields, "status": "rejected", "rows": total, "accepted_rows": 0, "rejected_rows": bad,
                                "row_errors": [e.to_dict() for e in errors], "steps": []})  # fmt: skip
    db.commit()
    return _output(sub, [])


def _store(db: Session, ctx: Context, sub: Submission | None, now: datetime, fields: dict) -> Submission:
    """A new submission is stamped with the runtime clock, the same clock record_manual_upload checks
    uploaded_on against, so "prepared on" and "today" never come from two different clocks."""
    if sub is None:
        sub = Submission(organisation_id=str(ctx.organisation_id), created_at=now, **fields)
        db.add(sub)
    else:
        for key, value in fields.items():
            setattr(sub, key, value)
        db.execute(
            delete(SubmissionFile).where(
                SubmissionFile.submission_id == sub.id, SubmissionFile.organisation_id == sub.organisation_id
            )
        )
    try:
        db.flush()
    except IntegrityError as e:
        db.rollback()
        raise AdapterError("conflict", "this batch was submitted at the same moment by another call") from e
    return sub


def _write_files(
    rt: Runtime, ctx: Context, db: Session, sub: Submission, parts: list[tuple[str, int, bytes]], version: str
) -> None:
    org = str(ctx.organisation_id)
    for filename, rows, content in parts:
        document_id = rt.documents_for(ctx).put(org, filename=filename, content_type="text/csv", content=content)
        db.add(
            SubmissionFile(
                organisation_id=org,
                submission_id=sub.id,
                document_id=document_id,
                filename=filename,
                rows=rows,
                template_version=version,
            )
        )


def _name(prefix: str, label: str, session: str, batch_key: str, part: int) -> str:
    slug = hashlib.sha256(batch_key.encode()).hexdigest()[:10]
    return f"{prefix}-{_SAFE.sub('_', label)}-{session}-{slug}-{part:02d}.csv"


def publish_awards(
    rt: Runtime, ctx: Context, inp: PublishAwardsInput | CorrectAwardsInput, *, correction: bool = False
) -> tuple[dict, str | None]:
    settings = rt.settings(ctx)
    cfg = rt.config()
    rt.require_mode(ctx, cfg)
    version = _check_version(cfg, "awards")
    _session_ok(inp.session)
    template = _template(settings, inp)
    institution_id = rt.institution_id(ctx, settings, "nad")
    institution_name = settings.institution_name or institution_id
    kind = "award_corrections" if correction else "awards"
    digest = payload_digest({"kind": kind, **inp.model_dump(mode="json")})
    today: date = rt.clock().date()
    org = str(ctx.organisation_id)
    pepper = rt.pepper(ctx, cfg)
    fields = {
        "kind": kind, "depository": "nad", "channel": "manual_upload", "award_kind": inp.award_kind,
        "template_code": template.template_code, "programme_code": inp.programme.code, "session": inp.session,
        "term": None, "caller_reference": inp.batch_key, "batch_key": inp.batch_key, "payload_digest": digest,
        "reason": getattr(inp, "reason", None),
    }  # fmt: skip
    with rt.db(ctx) as db:
        existing = _existing(db, inp.batch_key)
        if existing is not None:
            replayed = _replay(db, existing, digest, kind)
            if replayed is not None:
                return replayed, existing.id
        good, bad = validate_awards(inp.records, award_kind=inp.award_kind, today=today)
        errors = list(bad.errors)
        numbers = [rec.award_number.strip() for _, rec in good]
        lodged = _lodged(db, inp.award_kind, numbers)
        not_lodged: list[int] = []
        still_good = []
        for row, rec in good:
            number = rec.award_number.strip()
            held = lodged.get(number)
            if correction:
                if held is None:
                    not_lodged.append(row)
                    continue
                if held.apaar_id_hash != apaar_hash(pepper, org, rec.learner.apaar_id.strip()):
                    bad.add(row, "learner.apaar_id", "mismatch")  # a correction must be for the same learner
                    errors.append(RowError(row, "learner.apaar_id", "mismatch"))
                    continue
            elif held is not None:
                bad.add(row, "award_number", "already_lodged")
                errors.append(RowError(row, "award_number", "already_lodged"))
                continue
            still_good.append((row, rec))
        if not_lodged:
            listed = ", ".join(str(r) for r in not_lodged[:20])
            raise AdapterError("not_found", f"row(s) {listed} correct an award that was not lodged")
        errors = errors[:1000]
        if bad.count:
            return _reject(
                db,
                ctx,
                existing,
                fields,
                sorted(errors, key=lambda e: (e.row, e.field)),
                len(bad.bad_rows),
                len(inp.records),
                rt.clock(),
            ), (existing.id if existing else None)
        columns = AWARD_COLUMNS[version]
        rows = [
            award_row(
                rec,
                programme=inp.programme,
                institution_id=institution_id,
                institution_name=institution_name,
                session=inp.session,
                correction=correction,
            )
            for _, rec in still_good
        ]
        parts = []
        for n, (a, b) in enumerate(_split([1] * len(rows), cfg.max_rows_per_file), start=1):
            parts.append(
                (
                    _name(
                        "nad-awards" if not correction else "nad-corrections",
                        template.template_code,
                        inp.session,
                        inp.batch_key,
                        n,
                    ),
                    b - a,
                    render(columns, rows[a:b]),
                )
            )
        sub = _store(db, ctx, existing, rt.clock(), {**fields, "status": "manual_action_required", "rows": len(rows), "accepted_rows": None, "rejected_rows": None,
                                         "row_errors": [], "steps": _steps("nad", template.template_code, len(parts))})  # fmt: skip
        _write_files(rt, ctx, db, sub, parts, version)
        for _, rec in still_good:
            number, hashed = rec.award_number.strip(), apaar_hash(pepper, org, rec.learner.apaar_id.strip())
            if correction:
                lodged[number].status = "corrected"
            else:
                db.add(
                    LodgedAward(
                        organisation_id=org,
                        award_number=number,
                        award_kind=inp.award_kind,
                        person_id=str(rec.learner.person_id) if rec.learner.person_id else None,
                        apaar_id_hash=hashed,
                        submission_id=sub.id,
                    )
                )
        try:
            db.commit()
        except IntegrityError as e:
            db.rollback()
            raise AdapterError(
                "conflict", "an award in this batch was lodged at the same moment by another call"
            ) from e
        return _output(sub, _files(db, sub.id)), sub.id


def _template(settings: ConnectionSettings, inp: PublishAwardsInput):
    if not settings.award_templates:
        raise AdapterError("not_configured", "the connection has no award_templates")
    match = [
        t for t in settings.award_templates if t.template_code == inp.template_code and t.award_kind == inp.award_kind
    ]
    if not match:
        raise AdapterError(
            "invalid_request", "template_code is not one of the connection's templates for this award kind"
        )
    if match[0].programme_level and match[0].programme_level != inp.programme.level:
        raise AdapterError("invalid_request", "the template is for another programme level")
    return match[0]


def correct_awards(rt: Runtime, ctx: Context, inp: CorrectAwardsInput) -> tuple[dict, str | None]:
    return publish_awards(rt, ctx, inp, correction=True)


def publish_credits(rt: Runtime, ctx: Context, inp: PublishCreditsInput) -> tuple[dict, str | None]:
    settings = rt.settings(ctx)
    cfg = rt.config()
    rt.require_mode(ctx, cfg)
    version = _check_version(cfg, "credits")
    _session_ok(inp.session)
    institution_id = rt.institution_id(ctx, settings, "abc")
    digest = payload_digest({"kind": "credits", **inp.model_dump(mode="json")})
    fields = {
        "kind": "credits", "depository": "abc", "channel": "manual_upload", "award_kind": None, "template_code": None,
        "programme_code": None, "session": inp.session, "term": inp.term, "caller_reference": inp.batch_key,
        "batch_key": inp.batch_key, "payload_digest": digest, "reason": None,
    }  # fmt: skip
    with rt.db(ctx) as db:
        existing = _existing(db, inp.batch_key)
        if existing is not None:
            replayed = _replay(db, existing, digest, "credits")
            if replayed is not None:
                return replayed, existing.id
        good, bad = validate_credits(inp.records, today=rt.clock().date())
        if bad.count:
            errors = sorted(bad.errors, key=lambda e: (e.row, e.field))
            return _reject(db, ctx, existing, fields, errors, len(bad.bad_rows), len(inp.records), rt.clock()), (
                existing.id if existing else None
            )
        per_record = [
            credit_rows(rec, institution_id=institution_id, session=inp.session, term=inp.term) for _, rec in good
        ]
        parts = []
        for n, (a, b) in enumerate(_split([len(r) for r in per_record], cfg.max_rows_per_file), start=1):
            rows = [row for group in per_record[a:b] for row in group]
            parts.append(
                (
                    _name("abc-credits", inp.term, inp.session, inp.batch_key, n),
                    len(rows),
                    render(CREDIT_COLUMNS[version], rows),
                )
            )
        sub = _store(db, ctx, existing, rt.clock(), {**fields, "status": "manual_action_required", "rows": len(good), "accepted_rows": None, "rejected_rows": None,
                                         "row_errors": [], "steps": _steps("abc", "", len(parts))})  # fmt: skip
        _write_files(rt, ctx, db, sub, parts, version)
        db.commit()
        return _output(sub, _files(db, sub.id)), sub.id
