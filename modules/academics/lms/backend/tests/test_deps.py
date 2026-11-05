"""Who is calling: a bearer token signed by the platform, with a subject and an organisation."""

import jwt
import pytest
from conftest import BASE, STUDENT
from eos_core.security import create_token
from eos_core.settings import settings
from eos_lms.api.deps import require
from eos_lms.infrastructure.models import new_id


def test_tokens_without_a_subject_or_an_organisation_are_refused(client):
    no_sub = jwt.encode(
        {"org": new_id(), "roles": [STUDENT], "exp": 4_102_444_800}, settings.jwt_secret, algorithm="HS256"
    )
    r = client.get(f"{BASE}/me/course-materials", headers={"Authorization": f"Bearer {no_sub}"})
    assert r.status_code == 401 and r.json()["detail"]["code"] == "unauthenticated"
    platform_user = create_token(user_id=new_id(), organisation_id=None, roles=[STUDENT])
    r = client.get(f"{BASE}/me/course-materials", headers={"Authorization": f"Bearer {platform_user}"})
    assert r.status_code == 403 and r.json()["detail"]["code"] == "forbidden"
    expired = create_token(user_id=new_id(), organisation_id=new_id(), roles=[STUDENT], ttl_minutes=-5)
    assert client.get(f"{BASE}/me/course-materials", headers={"Authorization": f"Bearer {expired}"}).status_code == 401


def test_require_takes_only_catalogue_keys():
    with pytest.raises(ValueError):
        require("lms:course:read")
    with pytest.raises(ValueError):
        require()
    assert require("lms:grade:read-own").permissions == frozenset({"lms:grade:read-own"})
