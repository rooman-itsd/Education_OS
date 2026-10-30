"""HTTP surface of athlete-performance, as described in contracts/openapi.yaml. The host app mounts `router` under
/api/v1/athlete-performance. Handlers only map HTTP to the use cases in application/service.py."""

from __future__ import annotations

from datetime import date

from eos_core.db import get_db
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..application import service as svc
from ..application.service import Actor, ServiceError
from . import schemas as s
from .deps import require

router = APIRouter(tags=["athlete-performance"])

LIMIT = Query(50, ge=1, le=200)
OFFSET = Query(0, ge=0)
FROM = Query(None, alias="from")
TO = Query(None, alias="to")


def _run(fn, *args):
    try:
        return fn(*args)
    except ServiceError as e:
        raise HTTPException(e.status, e.body()) from e


def _period(start: date | None, end: date | None) -> None:
    if start and end and start > end:
        raise HTTPException(400, {"code": "invalid_period", "message": "from must not be after to"})


# ---------------------------------------------------------------- disciplines


@router.get("/disciplines")
def list_disciplines(
    active: bool | None = None,
    limit: int = LIMIT,
    offset: int = OFFSET,
    _: Actor = Depends(require(svc.CATALOGUE_READ)),
    db: Session = Depends(get_db),
):
    return svc.list_disciplines(db, active, limit, offset)


@router.post("/disciplines", status_code=201)
def create_discipline(
    body: s.DisciplineIn, a: Actor = Depends(require(svc.CATALOGUE_WRITE)), db: Session = Depends(get_db)
):
    return _run(svc.create_discipline, db, a, s.dump(body))


@router.get("/disciplines/{discipline_id}")
def get_discipline(discipline_id: str, _: Actor = Depends(require(svc.CATALOGUE_READ)), db: Session = Depends(get_db)):
    return _run(svc.get_discipline, db, discipline_id)


@router.patch("/disciplines/{discipline_id}")
def update_discipline(
    discipline_id: str,
    body: s.DisciplinePatch,
    a: Actor = Depends(require(svc.CATALOGUE_WRITE)),
    db: Session = Depends(get_db),
):
    return _run(svc.update_discipline, db, a, discipline_id, s.dump(body, partial=True))


# ---------------------------------------------------------------- metrics


@router.get("/metrics")
def list_metrics(
    discipline_id: str | None = None,
    limit: int = LIMIT,
    offset: int = OFFSET,
    _: Actor = Depends(require(svc.CATALOGUE_READ)),
    db: Session = Depends(get_db),
):
    return svc.list_metrics(db, discipline_id, limit, offset)


@router.post("/metrics", status_code=201)
def create_metric(body: s.MetricIn, a: Actor = Depends(require(svc.CATALOGUE_WRITE)), db: Session = Depends(get_db)):
    return _run(svc.create_metric, db, a, s.dump(body))


@router.get("/metrics/{metric_id}")
def get_metric(metric_id: str, _: Actor = Depends(require(svc.CATALOGUE_READ)), db: Session = Depends(get_db)):
    return _run(svc.get_metric, db, metric_id)


@router.patch("/metrics/{metric_id}")
def update_metric(
    metric_id: str, body: s.MetricPatch, a: Actor = Depends(require(svc.CATALOGUE_WRITE)), db: Session = Depends(get_db)
):
    return _run(svc.update_metric, db, a, metric_id, s.dump(body, partial=True))


# ---------------------------------------------------------------- athletes


@router.get("/athletes")
def list_athletes(
    discipline_id: str | None = None,
    coach_id: str | None = None,
    squad: str | None = None,
    status: s.AthleteStatus | None = None,
    q: str | None = None,
    limit: int = LIMIT,
    offset: int = OFFSET,
    a: Actor = Depends(require(svc.ATHLETE_READ)),
    db: Session = Depends(get_db),
):
    filters = {"discipline_id": discipline_id, "coach_id": coach_id, "squad": squad, "status": status, "q": q}
    return svc.list_athletes(db, a, filters, limit, offset)


@router.post("/athletes", status_code=201)
def create_athlete(body: s.AthleteIn, a: Actor = Depends(require(svc.ATHLETE_WRITE)), db: Session = Depends(get_db)):
    return _run(svc.create_athlete, db, a, s.dump(body))


@router.get("/athletes/{athlete_id}")
def get_athlete(athlete_id: str, a: Actor = Depends(require(svc.ATHLETE_READ)), db: Session = Depends(get_db)):
    return _run(svc.get_athlete, db, a, athlete_id)


@router.patch("/athletes/{athlete_id}")
def update_athlete(
    athlete_id: str, body: s.AthletePatch, a: Actor = Depends(require(svc.ATHLETE_WRITE)), db: Session = Depends(get_db)
):
    return _run(svc.update_athlete, db, a, athlete_id, s.dump(body, partial=True))


# ---------------------------------------------------------------- results


@router.get("/results")
def list_results(
    athlete_id: str | None = None,
    metric_id: str | None = None,
    context: s.Context | None = None,
    start: date | None = FROM,
    end: date | None = TO,
    limit: int = LIMIT,
    offset: int = OFFSET,
    a: Actor = Depends(require(svc.RESULT_READ)),
    db: Session = Depends(get_db),
):
    _period(start, end)
    filters = {"athlete_id": athlete_id, "metric_id": metric_id, "context": context, "from": start, "to": end}
    return svc.list_results(db, a, filters, limit, offset)


@router.post("/results", status_code=201)
def record_result(body: s.ResultIn, a: Actor = Depends(require(svc.RESULT_RECORD)), db: Session = Depends(get_db)):
    return _run(svc.record_result, db, a, s.dump(body))


@router.get("/results/{result_id}")
def get_result(result_id: str, a: Actor = Depends(require(svc.RESULT_READ)), db: Session = Depends(get_db)):
    return _run(svc.get_result, db, a, result_id)


@router.patch("/results/{result_id}")
def update_result(
    result_id: str, body: s.ResultPatch, a: Actor = Depends(require(svc.RESULT_RECORD)), db: Session = Depends(get_db)
):
    return _run(svc.update_result, db, a, result_id, s.dump(body, partial=True))


# ---------------------------------------------------------------- fitness tests


@router.get("/fitness-tests")
def list_fitness_tests(
    limit: int = LIMIT,
    offset: int = OFFSET,
    _: Actor = Depends(require(svc.CATALOGUE_READ)),
    db: Session = Depends(get_db),
):
    return svc.list_fitness_tests(db, limit, offset)


@router.post("/fitness-tests", status_code=201)
def create_fitness_test(
    body: s.FitnessTestIn, a: Actor = Depends(require(svc.CATALOGUE_WRITE)), db: Session = Depends(get_db)
):
    return _run(svc.create_fitness_test, db, a, s.dump(body))


@router.get("/fitness-tests/{fitness_test_id}")
def get_fitness_test(
    fitness_test_id: str, _: Actor = Depends(require(svc.CATALOGUE_READ)), db: Session = Depends(get_db)
):
    return _run(svc.get_fitness_test, db, fitness_test_id)


@router.patch("/fitness-tests/{fitness_test_id}")
def update_fitness_test(
    fitness_test_id: str,
    body: s.FitnessTestPatch,
    a: Actor = Depends(require(svc.CATALOGUE_WRITE)),
    db: Session = Depends(get_db),
):
    return _run(svc.update_fitness_test, db, a, fitness_test_id, s.dump(body, partial=True))


# ---------------------------------------------------------------- assessments


@router.get("/assessments")
def list_assessments(
    athlete_id: str | None = None,
    fitness_test_id: str | None = None,
    start: date | None = FROM,
    end: date | None = TO,
    limit: int = LIMIT,
    offset: int = OFFSET,
    a: Actor = Depends(require(svc.ASSESSMENT_READ)),
    db: Session = Depends(get_db),
):
    _period(start, end)
    filters = {"athlete_id": athlete_id, "fitness_test_id": fitness_test_id, "from": start, "to": end}
    return svc.list_assessments(db, a, filters, limit, offset)


@router.post("/assessments", status_code=201)
def record_assessment(
    body: s.AssessmentIn, a: Actor = Depends(require(svc.ASSESSMENT_RECORD)), db: Session = Depends(get_db)
):
    return _run(svc.record_assessment, db, a, s.dump(body))


@router.get("/assessments/{assessment_id}")
def get_assessment(assessment_id: str, a: Actor = Depends(require(svc.ASSESSMENT_READ)), db: Session = Depends(get_db)):
    return _run(svc.get_assessment, db, a, assessment_id)


# ---------------------------------------------------------------- benchmarks


@router.get("/benchmarks")
def list_benchmarks(
    metric_id: str | None = None,
    discipline_id: str | None = None,
    limit: int = LIMIT,
    offset: int = OFFSET,
    _: Actor = Depends(require(svc.BENCHMARK_READ)),
    db: Session = Depends(get_db),
):
    return svc.list_benchmarks(db, {"metric_id": metric_id, "discipline_id": discipline_id}, limit, offset)


@router.post("/benchmarks", status_code=201)
def create_benchmark(
    body: s.BenchmarkIn, a: Actor = Depends(require(svc.BENCHMARK_WRITE)), db: Session = Depends(get_db)
):
    return _run(svc.create_benchmark, db, a, s.dump(body))


@router.get("/benchmarks/{benchmark_id}")
def get_benchmark(benchmark_id: str, _: Actor = Depends(require(svc.BENCHMARK_READ)), db: Session = Depends(get_db)):
    return _run(svc.get_benchmark, db, benchmark_id)


@router.patch("/benchmarks/{benchmark_id}")
def update_benchmark(
    benchmark_id: str,
    body: s.BenchmarkPatch,
    a: Actor = Depends(require(svc.BENCHMARK_WRITE)),
    db: Session = Depends(get_db),
):
    return _run(svc.update_benchmark, db, a, benchmark_id, s.dump(body, partial=True))


# ---------------------------------------------------------------- history, comparison, clearance


@router.get("/athletes/{athlete_id}/history")
def get_performance_history(
    athlete_id: str,
    metric_id: str,
    start: date | None = FROM,
    end: date | None = TO,
    a: Actor = Depends(require(svc.RESULT_READ)),
    db: Session = Depends(get_db),
):
    _period(start, end)
    return _run(svc.performance_history, db, a, athlete_id, metric_id, start, end)


@router.get("/athletes/{athlete_id}/benchmark-comparison")
def compare_with_benchmarks(
    athlete_id: str,
    level: str | None = None,
    a: Actor = Depends(require(svc.BENCHMARK_READ)),
    db: Session = Depends(get_db),
):
    return _run(svc.compare_with_benchmarks, db, a, athlete_id, level)


@router.get("/athletes/{athlete_id}/clearance")
def get_clearance(athlete_id: str, a: Actor = Depends(require(svc.CLEARANCE_READ)), db: Session = Depends(get_db)):
    return _run(svc.get_clearance, db, a, athlete_id)


@router.put("/athletes/{athlete_id}/clearance")
def set_clearance(
    athlete_id: str,
    body: s.ClearanceIn,
    a: Actor = Depends(require(svc.CLEARANCE_WRITE)),
    db: Session = Depends(get_db),
):
    return _run(svc.set_clearance, db, a, athlete_id, s.dump(body))


# ---------------------------------------------------------------- reports


@router.get("/reports/squad-summary")
def get_squad_summary(
    discipline_id: str | None = None,
    coach_id: str | None = None,
    squad: str | None = None,
    a: Actor = Depends(require(svc.REPORT_READ)),
    db: Session = Depends(get_db),
):
    return svc.squad_summary(db, a, {"discipline_id": discipline_id, "coach_id": coach_id, "squad": squad})
