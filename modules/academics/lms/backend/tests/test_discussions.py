"""Discussion threads, posts and moderation (FR-14, FR-15)."""

from conftest import FACULTY, NOW, STUDENT, audit_actions, outbox
from eos_lms.infrastructure.models import new_id


def test_threads_and_posts(course):
    c = course
    base = f"/course-spaces/{c.space['id']}/threads"
    t = c.post(base, {"title": "Help with loops", "body": "Why?"}, 201, c.student)
    assert (t["state"], t["post_count"], t["created_by"]) == ("open", 0, c.student_id)
    assert outbox("lms.discussion-thread.created", c.org.id) == [
        {
            "organisation_id": c.org.id,
            "thread_id": t["id"],
            "course_space_id": c.space["id"],
            "title": "Help with loops",
            "created_by": c.student_id,
            "created_at": NOW.isoformat(),
        }
    ]
    c.post(f"/threads/{t['id']}/posts", {"body": "Because"}, 201, c.teacher)
    c.post(f"/threads/{t['id']}/posts", {"body": "Thanks"}, 201, c.student_b)
    listed = c.get(base, c.student2)
    assert listed["total"] == 1 and listed["items"][0]["post_count"] == 2
    page = c.get(f"/threads/{t['id']}?limit=1", c.student2)
    assert page["total"] == 2 and [p["body"] for p in page["posts"]] == ["Because"]
    assert c.get(f"/threads/{t['id']}?limit=1&offset=1", c.student2)["posts"][0]["body"] == "Thanks"
    assert c.get(base, c.viewer)["total"] == 1  # readers read
    assert c.call("POST", base, {"title": "x", "body": "y"}, c.viewer).status_code == 403  # but hold no post key
    for bad in ({"title": "", "body": "x"}, {"title": "x"}, {"title": "x", "body": "y" * 20_001}):
        assert c.call("POST", base, bad, c.student).status_code == 400


def test_only_members_take_part_while_the_space_is_active(course, org):
    c = course
    base = f"/course-spaces/{c.space['id']}/threads"
    _, outsider = org.user(STUDENT)
    assert c.call("POST", base, {"title": "x", "body": "y"}, outsider).status_code == 403
    _, other_teacher = org.user(FACULTY)
    r = c.call("POST", base, {"title": "x", "body": "y"}, other_teacher)
    assert r.status_code == 403
    assert c.post(base, {"title": "Admin note", "body": "y"}, 201, c.admin)["created_by"]
    t = c.post(base, {"title": "x", "body": "y"}, 201, c.student)
    c.post(f"/course-spaces/{c.space['id']}/status", {"status": "archived"})
    r = c.call("POST", f"/threads/{t['id']}/posts", {"body": "late"}, c.student)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "course_space_not_active"
    assert c.call("POST", base, {"title": "x", "body": "y"}, c.student).status_code == 409


def test_moderation_locks_and_hides_but_keeps_content(course):
    c = course
    t = c.post(f"/course-spaces/{c.space['id']}/threads", {"title": "Off topic", "body": "spam"}, 201, c.student)
    p = c.post(f"/threads/{t['id']}/posts", {"body": "more spam"}, 201, c.student2)
    path = f"/threads/{t['id']}/moderation"
    assert c.call("POST", path, {"action": "lock"}, c.student).status_code == 403
    assert c.post(path, {"action": "lock", "reason": "Closed"}, headers=c.teacher)["state"] == "locked"
    r = c.call("POST", path, {"action": "lock"}, c.teacher)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "invalid_status"
    r = c.call("POST", f"/threads/{t['id']}/posts", {"body": "x"}, c.student)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "thread_closed"
    assert c.post(path, {"action": "hide"}, headers=c.teacher)["state"] == "hidden"
    assert c.get(f"/course-spaces/{c.space['id']}/threads", c.student)["items"] == []
    assert c.call("GET", f"/threads/{t['id']}", headers=c.student).status_code == 404
    assert c.get(f"/threads/{t['id']}", c.teacher)["thread"]["state"] == "hidden"
    # Unhiding restores the lock it had.
    assert c.post(path, {"action": "unhide"}, headers=c.teacher)["state"] == "locked"
    assert c.post(path, {"action": "unlock"}, headers=c.teacher)["state"] == "open"
    assert c.call("POST", path, {"action": "delete"}, c.teacher).status_code == 400
    # Posts.
    post_path = f"/posts/{p['id']}/moderation"
    assert c.post(post_path, {"action": "hide"}, headers=c.teacher)["state"] == "hidden"
    assert c.post(post_path, {"action": "hide"}, headers=c.teacher)["state"] == "hidden"  # no change, no error
    student_view = c.get(f"/threads/{t['id']}", c.student)
    assert student_view["posts"] == [] and student_view["total"] == 0 and student_view["thread"]["post_count"] == 0
    assert [x["state"] for x in c.get(f"/threads/{t['id']}", c.teacher)["posts"]] == ["hidden"]
    assert c.call("POST", post_path, {"action": "hide"}, c.student).status_code == 403
    assert c.call("POST", f"/posts/{new_id()}/moderation", {"action": "hide"}, c.teacher).status_code == 404
    assert audit_actions(c.org.id, p["id"]) == ["discussion-post.created", "discussion-post.hidden"]
    assert c.post(path, {"action": "hide"}, headers=c.admin)["state"] == "hidden"  # moderate-all
