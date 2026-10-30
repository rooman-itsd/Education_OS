"""config/modules.enabled.yaml decides what the host mounts: enabled feature modules are served behind the
entitlement gate, health lists them, and a listed entry that is not installed stops start-up."""

import importlib.util
import sys
from pathlib import Path

import pytest
import yaml
from eos_backend import modules
from eos_backend.main import create_app
from eos_backend.modules import CONFIG, Entry, enabled, middleware_only, router_for

ROOT = Path(__file__).resolve().parents[3]
FRONTEND_CONFIG = ROOT / "apps/frontend/config/modules.enabled.yaml"


def _features():
    """The enabled feature modules and integrations, or skip: a host may compose none."""
    found = [e for e in enabled() if e.kind != "platform"]
    if not found:
        pytest.skip("modules.enabled.yaml enables no feature module")
    return found


def _paths(app) -> set[str]:
    """Every path the app serves (from its OpenAPI schema: included routers are not flattened into app.routes)."""
    return set(app.openapi()["paths"])


def _yaml(tmp_path, text: str) -> Path:
    p = tmp_path / "modules.enabled.yaml"
    p.write_text(text, encoding="utf-8")
    return p


def test_enabled_modules_are_mounted_under_their_name(client):
    paths = _paths(client.app)
    for e in _features():
        assert any(p.startswith(f"/api/v1/{e.name}/") for p in paths), f"{e.entry} is not mounted"


def test_health_lists_the_mounted_modules(client):
    body = client.get("/api/v1/health").json()
    assert body["status"] == "ok"
    assert body["modules"] == sorted(e.name for e in enabled() if e.kind != "platform")


def test_a_mounted_module_sits_behind_the_entitlement_gate(client):
    prefix = f"/api/v1/{_features()[0].name}/"
    route = next(p for p in _paths(client.app) if p.startswith(prefix) and "{" not in p)
    assert client.get(route).status_code == 401  # no bearer token: refused by the gate, not served


def test_every_frontend_module_with_an_api_is_enabled_here():
    """apps/frontend/config/modules.enabled.yaml decides which widgets the dashboard shows; a module whose backend
    has api/router.py must be mounted too, or those widgets' requests 404 for an entitled organisation."""
    frontend = (yaml.safe_load(FRONTEND_CONFIG.read_text(encoding="utf-8")) or {}).get("modules") or []
    backend = {e.entry for e in enabled() if e.kind == "modules"}
    with_api = [
        m
        for m in frontend
        if (
            ROOT
            / "modules"
            / m
            / "backend"
            / "src"
            / f"eos_{m.rsplit('/', 1)[-1].replace('-', '_')}"
            / "api"
            / "router.py"
        ).is_file()
    ]
    assert with_api, "the frontend enables at least one module with a backend"
    missing = sorted(set(with_api) - backend)
    assert not missing, f"enabled in apps/frontend but not in apps/backend/config/modules.enabled.yaml: {missing}"


def test_a_listed_module_that_is_not_installed_stops_start_up(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "EOS_MODULES_FILE", str(_yaml(tmp_path, "modules: [academics/not-a-module]\nplatform: [identity]\n"))
    )
    with pytest.raises(RuntimeError, match=r"modules/academics/not-a-module .* eos_not_a_module is not installed"):
        create_app()


def test_a_platform_service_marked_router_false_is_installed_but_mounts_nothing(tmp_path, monkeypatch):
    """api-gateway is middleware only (`router: false` in its module.yaml): enabled so py-setup.sh and the API
    image install it, no routes."""
    gateway = Entry("platform", "api-gateway")
    assert middleware_only(gateway) and router_for(gateway) is None
    assert not middleware_only(Entry("platform", "identity"))
    monkeypatch.setenv("EOS_MODULES_FILE", str(_yaml(tmp_path, "platform: [api-gateway, identity]\n")))
    app = create_app()
    assert not any(p.startswith("/api/v1/api-gateway") for p in _paths(app))
    assert any(p.startswith("/api/v1/identity/") for p in _paths(app))


def _installed_service_without_router(tmp_path, monkeypatch, manifest: str) -> None:
    """An installed package eos_quiet_service with no api/router.py, and its module.yaml under a fake repo."""
    pkg = tmp_path / "site" / "eos_quiet_service"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    monkeypatch.syspath_prepend(str(tmp_path / "site"))
    service = tmp_path / "repo" / "platform" / "quiet-service"
    service.mkdir(parents=True)
    (service / "module.yaml").write_text(manifest, encoding="utf-8")
    monkeypatch.setattr(modules, "MANIFESTS", tmp_path / "repo")
    monkeypatch.setenv("EOS_MODULES_FILE", str(_yaml(tmp_path, "platform: [quiet-service, identity]\n")))


def test_a_platform_service_without_a_router_and_without_the_flag_stops_start_up(tmp_path, monkeypatch):
    """Review of PR 363, point 3: a renamed or deleted router must not start the API with its routes 404ing."""
    _installed_service_without_router(tmp_path, monkeypatch, "name: quiet-service\nkind: platform\n")
    with pytest.raises(RuntimeError, match=r"platform/quiet-service has no eos_quiet_service/api/router\.py"):
        create_app()


def test_the_router_false_flag_lets_a_service_without_a_router_start(tmp_path, monkeypatch):
    _installed_service_without_router(tmp_path, monkeypatch, "name: quiet-service\nrouter: false\n")
    app = create_app()
    assert not any(p.startswith("/api/v1/quiet-service") for p in _paths(app))


def test_a_router_false_service_must_still_be_installed(tmp_path, monkeypatch):
    service = tmp_path / "repo" / "platform" / "absent-service"
    service.mkdir(parents=True)
    (service / "module.yaml").write_text("router: false\n", encoding="utf-8")
    monkeypatch.setattr(modules, "MANIFESTS", tmp_path / "repo")
    with pytest.raises(RuntimeError, match=r"platform/absent-service .* eos_absent_service is not installed"):
        router_for(Entry("platform", "absent-service"))


def test_an_integration_is_resolved_like_a_module(tmp_path, monkeypatch):
    monkeypatch.setenv("EOS_MODULES_FILE", str(_yaml(tmp_path, "integrations: [no-such-adapter]\n")))
    with pytest.raises(RuntimeError, match=r"integrations/no-such-adapter .* eos_no_such_adapter is not installed"):
        create_app()


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("modules: [hostel]\n", "is not <domain>/<module>"),
        ("integrations: [payment/sbiepay]\n", "is not <name>"),
        ("modules: campus-life/hostel\n", "must be a list"),
        ("modules: [campus-life/hostel, sports/hostel]\n", "same path: hostel"),
    ],
)
def test_malformed_entries_are_refused(tmp_path, text, message):
    with pytest.raises(RuntimeError, match=message):
        enabled(_yaml(tmp_path, text))


def test_the_install_script_reads_the_same_list():
    """tools/scripts/enabled-modules.py installs, migrates and tests exactly what the host mounts."""
    spec = importlib.util.spec_from_file_location("enabled_modules", ROOT / "tools/scripts/enabled-modules.py")
    script = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = script  # dataclasses look their module up here
    spec.loader.exec_module(script)
    assert [(e.kind, e.entry) for e in script.entries(CONFIG, ROOT)] == [(e.kind, e.entry) for e in enabled()]
    for e in script.entries(CONFIG, ROOT):
        assert (e.package / "pyproject.toml").is_file(), e.entry


def test_every_routed_platform_service_is_covered_by_the_permissions_check():
    """PLATFORM_ROUTERS (tests/test_platform_permissions.py) leaves out only `router: false` services."""
    from eos_backend.main import PLATFORM_ROUTERS

    platform = {e.name for e in enabled() if e.kind == "platform"}
    assert set(PLATFORM_ROUTERS) == platform - {"api-gateway"}
    assert {"identity", "tenancy", "billing"} <= set(PLATFORM_ROUTERS)
