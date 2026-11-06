"""Clocks, tickets and the breaches statistics through the HTTP API: filters, order, paging, hostile query values."""

import base64
from datetime import timedelta

from conftest import NOW, OTHER_CATEGORY, at, new_uuid


def b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode()


def test_list_soonest_due_first_with_filters(desk, clock):
    desk.policy()
    desk.policy(priority="urgent", response_target_minutes=10, resolution_target_minutes=20)
    high = desk.ticket(number="HD-1")
    urgent = desk.ticket(priority="urgent", number="HD-2", category_id=OTHER_CATEGORY)
    desk.assign(high, desk.agent_id)
    clock.set(NOW + timedelta(minutes=15))
    body = desk.ok(desk.get("/clocks", desk.viewer))
    assert [(c["ticket_number"], c["kind"]) for c in body["items"]] == [
        ("HD-2", "response"),
        ("HD-2", "resolution"),
        ("HD-1", "response"),
        ("HD-1", "resolution"),
    ]
    assert body["next_cursor"] is None

    def numbers(query: str) -> list[tuple[str, str]]:
        return [(c["ticket_number"], c["kind"]) for c in desk.ok(desk.get(f"/clocks?{query}", desk.agent))["items"]]

    assert numbers("kind=resolution") == [("HD-2", "resolution"), ("HD-1", "resolution")]
    assert numbers("priority=urgent&breached=true") == [("HD-2", "response")]
    assert numbers("breached=false&kind=response") == [("HD-1", "response")]
    assert numbers("at_risk=true") == [("HD-2", "resolution")]  # 15 of 20, warning at 10
    assert numbers("assignee=me") == [("HD-1", "response"), ("HD-1", "resolution")]
    assert numbers(f"assignee={desk.agent_id}&kind=response") == [("HD-1", "response")]
    assert numbers(f"category_id={OTHER_CATEGORY}&kind=response") == [("HD-2", "response")]
    assert numbers("ticket_number=HD-1&kind=response") == [("HD-1", "response")]
    desk.send("responded", {"ticket_id": urgent, "responded_at": at(5)})
    assert numbers("state=stopped") == [("HD-2", "response")]
    assert len(numbers("state=running,stopped")) == 4
    assert numbers("state=paused,cancelled") == []


def test_paging(desk):
    desk.policy()
    for _ in range(3):
        desk.ticket()
    first = desk.ok(desk.get("/clocks?limit=4"))
    second = desk.ok(desk.get(f"/clocks?limit=4&cursor={first['next_cursor']}"))
    assert (len(first["items"]), len(second["items"]), second["next_cursor"]) == (4, 2, None)
    assert not {c["id"] for c in first["items"]} & {c["id"] for c in second["items"]}


def test_hostile_query_values_are_422(desk):
    for query in [
        "kind=response,resolution",
        "priority=high,low",
        "state=running,forever",
        "state=,",
        "breached=maybe",
        "category_id=nope",
        "assignee=somebody",
        f"ticket_number={'x' * 41}",
        "limit=0",
        "limit=101",
        "limit=100000000000",
        f"limit={2**63}",
        "cursor=garbage!!",
        f"cursor={b64(str(10**6 + 1))}",
        f"cursor={b64(str(2**63))}",
        f"cursor={b64('-5')}",
        f"cursor={'A' * 10_000}",
    ]:
        response = desk.get(f"/clocks?{query}", desk.viewer)
        assert response.status_code == 422, (query, response.text)
    assert desk.get(f"/clocks?cursor={b64(str(10**6))}", desk.viewer).status_code == 200


def test_clock_and_ticket_lookups(desk):
    desk.policy()
    ticket = desk.ticket()
    clocks = desk.clocks(ticket)
    detail = desk.ok(desk.get(f"/clocks/{clocks['response']['id']}", desk.viewer))
    assert detail["escalations"] == [] and detail["kind"] == "response"
    assert desk.get(f"/clocks/{new_uuid()}", desk.viewer).status_code == 404
    assert desk.get(f"/tickets/{new_uuid()}", desk.viewer).status_code == 404
    assert desk.get("/clocks/123", desk.viewer).status_code == 422
    assert desk.get(f"/tickets/{'9' * 10_000}", desk.viewer).status_code == 422
    sla = desk.ok(desk.get(f"/tickets/{ticket.upper()}", desk.viewer))
    assert (sla["ticket_id"], [c["kind"] for c in sla["clocks"]]) == (ticket, ["response", "resolution"])


def test_breach_stats_for_the_widget(desk, clock, monkeypatch):
    desk.policy()
    mine, _others, late = (
        desk.ticket(number="HD-1"),
        desk.ticket(number="HD-2"),
        desk.ticket(number="HD-3", created=-200),
    )
    desk.assign(mine, desk.agent_id)
    desk.send("responded", {"ticket_id": late, "responded_at": at(-100)})  # response breached at -140, stopped
    clock.set(NOW + timedelta(minutes=70))
    body = desk.ok(desk.get("/stats/breaches", desk.viewer))
    assert body["scope"] == "all"
    # running past due: HD-1 and HD-2 responses, HD-3 resolution (due at 40)
    assert (body["breached_open"], body["at_risk"], body["breached_last_24h"]) == (3, 0, 4)
    overdue = [(i["ticket_number"], i["kind"]) for i in body["most_overdue"]]
    assert overdue[0] == ("HD-3", "resolution")  # due at 40; HD-1 and HD-2 both at 60
    assert set(overdue[1:]) == {("HD-1", "response"), ("HD-2", "response")}
    first = body["most_overdue"][0]
    assert set(first) == {
        "clock_id",
        "ticket_id",
        "ticket_number",
        "kind",
        "priority",
        "assignee_id",
        "due_at",
        "overdue_business_minutes",
    }
    assert (first["due_at"], first["overdue_business_minutes"]) == (at(40), 30)
    own = desk.ok(desk.get("/stats/breaches?scope=mine", desk.agent))
    assert (own["scope"], own["breached_open"], own["at_risk"]) == ("mine", 1, 0)
    clock.set(NOW + timedelta(minutes=125))  # HD-1 and HD-2 resolution warnings (at 120) passed
    assert desk.ok(desk.get("/stats/breaches?scope=mine", desk.agent))["at_risk"] == 1
    assert desk.ok(desk.get("/stats/breaches"))["at_risk"] == 2
    assert len(desk.ok(desk.get("/stats/breaches?limit=1"))["most_overdue"]) == 1
    monkeypatch.setenv("SLA_MANAGEMENT_BREACH_LIST_LIMIT", "2")
    assert len(desk.ok(desk.get("/stats/breaches"))["most_overdue"]) == 2
    for query in ["scope=everyone", "scope=mine,all", "limit=0", "limit=51", f"limit={2**63}"]:
        assert desk.get(f"/stats/breaches?{query}").status_code == 422, query
    clock.set(NOW + timedelta(days=2))
    assert desk.ok(desk.get("/stats/breaches"))["breached_last_24h"] == 0
