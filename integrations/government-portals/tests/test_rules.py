"""Every rule has a failing fixture: the golden data, broken in exactly one way, is invalid for exactly that reason."""

import copy

import pytest
from gp_support import load_case, prepare, provider_of, put_evidence


def _case(name, mutate):
    case = copy.deepcopy(load_case(name))
    mutate(case["data"])
    return case


def _set(path, value):
    def mutate(data):
        node = data
        *parents, last = path
        for p in parents:
            node = node[p]
        node[last] = value

    return mutate


def _drop(path):
    def mutate(data):
        node = data
        *parents, last = path
        for p in parents:
            node = node[p]
        del node[last]

    return mutate


BROKEN = [
    (
        "aishe-dcf-ii",
        _set(["programmes", 0, "enrolment_by_category", "sc"], 21),
        "programmes[0].enrolment_by_category",
        "total_mismatch_gender_category",
    ),
    (
        "aishe-dcf-ii",
        _set(["examination_results", 0, "passed"], 56),
        "examination_results[0].passed",
        "passed_exceeds_appeared",
    ),
    (
        "aishe-dcf-ii",
        _set(["examination_results", 1, "programme"], "Unknown"),
        "examination_results[1].programme",
        "unknown_programme",
    ),
    (
        "aishe-dcf-ii",
        _set(["basic_details", "year_of_establishment"], 2031),
        "basic_details.year_of_establishment",
        "established_after_period",
    ),
    (
        "aishe-dcf-ii",
        _set(["basic_details", "institution_type"], "university"),
        "basic_details.institution_type",
        "form_institution_type_mismatch",
    ),
    ("aishe-dcf-ii", _set(["staff", "teaching", "male"], 13), "teachers", "teacher_count_mismatch_staff"),
    (
        "aishe-dcf-ii",
        _set(["finance", "salary_expenditure"], 40000000),
        "finance.salary_expenditure",
        "salary_exceeds_expenditure",
    ),
    (
        "aishe-dcf-ii",
        _set(["teachers", 0, "date_of_joining"], "2099-01-01"),
        "teachers[0].date_of_joining",
        "date_in_future",
    ),
    ("aishe-dcf-ii", _drop(["finance"]), "finance", "required"),
    ("aishe-dcf-ii", _set(["basic_details", "aishe_code"], "12345"), "basic_details.aishe_code", "pattern"),
    ("aishe-dcf-ii", _set(["programmes", 0, "level"], "masters"), "programmes[0].level", "enum"),
    ("aishe-dcf-ii", _set(["infrastructure", "computers"], -1), "infrastructure.computers", "minimum"),
    ("aishe-dcf-ii", _set(["infrastructure", "computers"], 2.5), "infrastructure.computers", "type"),
    ("aishe-dcf-ii", _set(["infrastructure", "computers"], True), "infrastructure.computers", "type"),
    ("aishe-dcf-ii", _set(["finance", "income_total"], float("nan")), "finance.income_total", "not_finite"),
    ("aishe-dcf-ii", _set(["finance", "income_total"], float("inf")), "finance.income_total", "not_finite"),
    (
        "aishe-dcf-ii",
        _set(["basic_details", "institution_name"], "x" * 201),
        "basic_details.institution_name",
        "length",
    ),
    ("aishe-dcf-ii", _set(["basic_details", "invented"], 1), "basic_details.invented", "unknown_field"),
    ("aishe-dcf-i", _set(["departments"], [{"name": "A", "discipline": "B"}] * 1001), "departments", "items_count"),
    ("nirf-dcs-overall", _set(["go", "placed_students"], 900), "go.placed_students", "exceeds_graduating_students"),
    ("nirf-dcs-overall", _set(["tlr", "faculty_with_phd_pct"], 101), "tlr.faculty_with_phd_pct", "maximum"),
    ("nirf-dcs-overall", _drop(["oi"]), "oi", "required"),
    (
        "nirf-dcs-overall",
        _set(["institute", "year_of_establishment"], 2030),
        "institute.year_of_establishment",
        "established_after_period",
    ),
    (
        "naac-ssr",
        _set(["criteria", 0, "metrics", 0, "metric"], "2.1.1"),
        "criteria[0].metrics[0].metric",
        "metric_not_in_criterion",
    ),
    ("naac-ssr", _set(["criteria", 1, "criterion"], 1), "criteria[1].criterion", "duplicate_criterion"),
    (
        "naac-ssr",
        _set(["criteria", 0, "metrics", 1, "value"], "six"),
        "criteria[0].metrics[1].value",
        "quantitative_value_not_numeric",
    ),
    (
        "naac-ssr",
        _set(["criteria", 0, "metrics", 0, "value"], 12),
        "criteria[0].metrics[0].value",
        "qualitative_value_not_text",
    ),
    (
        "naac-ssr",
        _set(["criteria", 0, "metrics", 1, "metric"], "1.1.1"),
        "criteria[0].metrics[1].metric",
        "duplicate_metric",
    ),
    ("naac-ssr", _set(["criteria", 0, "metrics", 0, "metric"], "8.1.1"), "criteria[0].metrics[0].metric", "pattern"),
    ("naac-dvv-response", _set(["queries"], []), "queries", "items_count"),
    ("naac-iiqa", _drop(["institute", "naac_hei_id"]), "institute.naac_hei_id", "required"),
]


@pytest.mark.parametrize(("name", "mutate", "path", "code"), BROKEN, ids=[f"{b[0]}:{b[3]}:{b[2]}" for b in BROKEN])
def test_a_broken_fixture_is_invalid_for_its_reason(adapter, docs, org, name, mutate, path, code):
    case = _case(name, mutate)
    r = prepare(adapter, org, docs, case)
    assert r.ok, r.error  # an invalid package is an output with status invalid, with its package row
    assert r.output["status"] == "invalid" and r.output["files"] == [] and r.output["checklist"] == []
    assert {"path": path, "code": code, "severity": "error"} in r.output["issues"]
    check = adapter.validate(
        org.ctx(provider_of(case["form_code"])), form_code=case["form_code"], period=case["period"], data=case["data"]
    )
    assert check.output["valid"] is False
    assert {"path": path, "code": code, "severity": "error"} in check.output["issues"]


def test_valid_data_validates_without_preparing_anything(adapter, org):
    case = load_case("aishe-dcf-iii")
    r = adapter.validate(org.ctx("aishe"), form_code=case["form_code"], period=case["period"], data=case["data"])
    assert r.output == {"valid": True, "issues": []}


def test_issues_never_carry_a_value(adapter, docs, org):
    case = _case("aishe-dcf-ii", _set(["teachers", 0, "name"], "Secret Person " + "x" * 300))
    r = prepare(adapter, org, docs, case)
    assert "Secret Person" not in repr(r)


def test_warnings_do_not_block_a_package(adapter, docs, org):
    case = _case("nirf-dcs-overall", _set(["go", "higher_studies_students"], 400))
    r = prepare(adapter, org, docs, case)
    assert r.output["status"] == "prepared"
    assert any(i["severity"] == "warning" for i in r.output["issues"])


def test_period_must_be_consecutive_academic_years(adapter, docs, org):
    r = prepare(adapter, org, docs, load_case("naac-aqar"), period="2025-27")
    assert (
        r.output["status"] == "invalid"
        and {"path": "period", "code": "period_format", "severity": "error"} in r.output["issues"]
    )


# ----------------------------------------------------------------- evidence


def _ssr_with(adapter, docs, org, evidence_docs, **kw):
    case = load_case("naac-ssr")
    case["evidence"] = []
    evidence = put_evidence(docs, org.id, evidence_docs)
    return prepare(adapter, org, docs, case, evidence=evidence, **kw)


def test_a_missing_evidence_document_is_an_issue_on_that_metric(adapter, docs, org):
    case = load_case("naac-ssr")
    case["evidence"] = []
    bad = [{"metric": "1.1.1", "document_id": "00000000-0000-4000-8000-000000000000", "title": "Gone"}]
    r = prepare(adapter, org, docs, case, evidence=bad)
    assert r.output["status"] == "invalid"
    assert {"path": "evidence[0].document_id", "code": "evidence_missing", "severity": "error"} in r.output["issues"]


def test_another_organisations_evidence_is_missing_not_readable(adapter, docs, org, other_org):
    doc_id = docs.put(other_org.id, filename="x.pdf", content_type="application/pdf", content=b"secret")
    case = load_case("naac-ssr")
    case["evidence"] = []
    r = prepare(adapter, org, docs, case, evidence=[{"metric": "1.1.1", "document_id": doc_id, "title": "Theirs"}])
    assert r.output["status"] == "invalid"
    assert r.output["issues"][0]["code"] == "evidence_missing"


def test_oversized_evidence_is_flagged_not_compressed(adapter, docs, org, monkeypatch):
    monkeypatch.setenv("GOVERNMENT_PORTALS_MAX_EVIDENCE_FILE_BYTES", "10")
    r = _ssr_with(adapter, docs, org, [{"metric": "1.1.1", "title": "Big", "filename": "big.pdf", "content": "x" * 11}])
    assert r.output["status"] == "invalid"
    assert {"path": "evidence[0].document_id", "code": "evidence_too_large", "severity": "error"} in r.output["issues"]


def test_the_package_size_limit_applies_to_all_evidence_together(adapter, docs, org, monkeypatch):
    monkeypatch.setenv("GOVERNMENT_PORTALS_MAX_PACKAGE_BYTES", "15")
    ev = [{"metric": "1.1.1", "title": f"F{i}", "filename": f"f{i}.pdf", "content": "x" * 8} for i in range(2)]
    r = _ssr_with(adapter, docs, org, ev)
    assert {"path": "evidence", "code": "package_too_large", "severity": "error"} in r.output["issues"]


def test_an_evidence_type_the_portal_does_not_take_is_refused(adapter, docs, org):
    r = _ssr_with(adapter, docs, org, [{"metric": "1.1.1", "title": "Prog", "filename": "run.exe", "content": "MZ"}])
    assert {"path": "evidence[0].document_id", "code": "evidence_type_not_accepted", "severity": "error"} in r.output[
        "issues"
    ]


def test_evidence_for_an_unknown_metric_is_a_warning(adapter, docs, org):
    r = _ssr_with(adapter, docs, org, [{"metric": "4.4.4", "title": "Stray", "filename": "s.pdf", "content": "x"}])
    assert r.output["status"] == "prepared"
    assert r.output["issues"] == [
        {"path": "evidence[0].metric", "code": "evidence_metric_not_in_data", "severity": "warning"}
    ]


def test_dvv_needs_evidence_for_every_query(adapter, docs, org):
    case = load_case("naac-dvv-response")
    case["evidence"] = case["evidence"][:1]  # 2.6.3 has none
    r = prepare(adapter, org, docs, case)
    assert {"path": "queries[1].metric", "code": "evidence_required", "severity": "error"} in r.output["issues"]


def test_forms_without_evidence_refuse_it(adapter, docs, org):
    case = load_case("aishe-dcf-i")
    case["evidence"] = [{"metric": "1.1.1", "title": "x", "filename": "x.pdf", "content": "x"}]
    r = prepare(adapter, org, docs, case)
    assert r.output["status"] == "invalid" and r.output["issues"][0]["code"] == "evidence_not_accepted_for_form"


def test_malformed_evidence_is_invalid_request(adapter, docs, org):
    for bad in (
        "x",
        [1],
        [{"metric": "1.1.1"}],
        [{"metric": "zz", "document_id": "nope", "title": "t"}],
        [{"metric": "1.1.1", "document_id": "00000000-0000-4000-8000-000000000000", "title": "t", "extra": 1}],
    ):
        r = prepare(adapter, org, docs, load_case("naac-ssr"), evidence=bad)
        assert r.error and r.error.code == "invalid_request", bad


def test_evidence_is_arranged_by_metric_and_referenced_not_copied(adapter, docs, org):
    case = load_case("naac-ssr")
    r = prepare(adapter, org, docs, case)
    evidence = [f for f in r.output["files"] if f["role"] == "evidence"]
    assert [f["filename"] for f in evidence] == [
        "evidence/1.1.1/01-board-of-studies-minutes-2025.pdf",
        "evidence/1.1.1/02-curriculum-revision-notice.pdf",
        "evidence/2.6.3/01-pass-percentage-statement.xlsx",
    ]
    originals = {d[1] for d in docs._docs}  # the evidence entries are the callers' own documents
    assert {f["document_id"] for f in evidence} <= originals
