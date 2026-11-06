"""A body FastAPI cannot quote back in its 422 (NaN, Infinity, 1e999, a lone surrogate) answers 422, not 500."""

import pytest
from eos_core.http_errors import install_error_handlers
from fastapi import FastAPI, Query
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field


class Item(BaseModel):
    qty: int = Field(ge=0)
    price: float = Field(ge=0, allow_inf_nan=False)
    name: str = Field(pattern=r"^[a-z]+$")
    tags: list[float] = Field(default_factory=list, max_length=0)


app = FastAPI()
install_error_handlers(app)


@app.post("/items")
def create(item: Item):
    return item.model_dump()


@app.get("/search")
def search(page: int = Query(1, ge=1), q: str = Query("", pattern=r"^[a-z]*$")):
    return {"page": page, "q": q}


client = TestClient(app, raise_server_exceptions=False)
GOOD = '{"qty": 1, "price": 2.5, "name": "abc"}'


def post(raw: str):
    return client.post(
        "/items", content=raw.encode("utf-8", "surrogatepass"), headers={"content-type": "application/json"}
    )


def test_a_valid_request_is_unaffected():
    r = post(GOOD)
    assert r.status_code == 200 and r.json()["price"] == 2.5


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-Infinity", "1e999", "-1e999"])
@pytest.mark.parametrize("field", ["qty", "price"])
def test_a_non_finite_number_in_a_body_field_answers_422(field, bad):
    body = {"qty": "1", "price": "2.5"}
    body[field] = bad
    r = post(f'{{"qty": {body["qty"]}, "price": {body["price"]}, "name": "abc"}}')
    assert r.status_code == 422
    errs = r.json()["detail"]
    assert errs and all({"type", "loc", "msg"} <= e.keys() for e in errs)
    assert any(e["loc"] == ["body", field] for e in errs)


def test_a_non_finite_number_nested_in_a_list_answers_422():
    r = post('{"qty": 1, "price": 1, "name": "abc", "tags": [NaN]}')
    assert r.status_code == 422


def test_a_lone_surrogate_in_a_string_answers_422():
    r = post('{"qty": 1, "price": 1, "name": "ab\\ud800"}')
    assert r.status_code == 422
    assert r.json()["detail"][0]["loc"] == ["body", "name"]


def test_a_lone_surrogate_as_a_key_answers_422():
    r = post('{"qty": 1, "price": 1, "name": "abc", "\\udc00": 1, "qty2": -Infinity, "tags": [1]}')
    assert r.status_code == 422


def test_an_ordinary_invalid_value_keeps_fastapis_body():
    r = post('{"qty": -1, "price": 2.5, "name": "abc"}')
    assert r.status_code == 422
    assert r.json() == {
        "detail": [
            {
                "type": "greater_than_equal",
                "loc": ["body", "qty"],
                "msg": "Input should be greater than or equal to 0",
                "input": -1,
                "ctx": {"ge": 0},
            }
        ]
    }


def test_text_that_is_not_json_still_answers_422():
    assert post("{nope").status_code == 422


def test_query_parameters_answer_422_and_valid_ones_pass():
    assert client.get("/search?page=2&q=ab").json() == {"page": 2, "q": "ab"}
    for qs in ("page=NaN", "page=Infinity", "page=1e999", "q=%ED%A0%80", "q=%FF"):
        assert client.get("/search?" + qs).status_code == 422, qs
    r = client.get("/search?page=0")
    assert r.status_code == 422 and r.json()["detail"][0]["input"] == "0"
