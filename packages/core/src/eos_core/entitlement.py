"""entitlement = profile.modules ∩ plan.modules ∪ overrides − disabled (ADR-0005).
Mirrors apps/frontend/src/tenant/entitlements.ts; the two are kept identical on purpose."""

from __future__ import annotations

PLATFORM_MODULES = {
    "identity",
    "tenancy",
    "billing",
    "audit",
    "workflow",
    "reporting",
    "notification",
    "documents",
    "search",
    "scheduler",
    "event-bus",
    "api-gateway",
    "integration-hub",
    # Integrations whose routes are platform-level (super admin only, no organisation): the gate must let them
    # through, or every caller is refused before the route's own permission check.
    "messaging-providers",
}


def _suite(m: str) -> str:
    return m.split("/")[0]


def _name(m: str) -> str:
    return m.split("/")[-1]


def compute_entitlement(
    profile: dict, plan: dict, overrides: list[str] | None = None, disabled: list[str] | None = None
) -> dict:
    overrides = overrides or []
    disabled = disabled or []
    all_suites = "*" in plan["suites"]
    specialized = profile["suites"].get("specialized", [])
    allowed_specialized = set(
        specialized if plan["specialized_suites"] == "all" else specialized[: int(plan["specialized_suites"])]
    )

    def allowed(m: str) -> bool:
        s = _suite(m)
        if m in plan.get("modules", []):
            return True
        if s in specialized:
            return all_suites or s in allowed_specialized
        return all_suites or s in plan["suites"]

    on = [m for m in profile["modules"] if (allowed(m) or m in overrides) and m not in disabled]
    off = [m for m in profile["modules"] if m not in on]
    plan_integrations = plan.get("integrations", [])
    integrations = [i for i in profile.get("integrations", []) if "*" in plan_integrations or i in plan_integrations]
    return {
        "academy_type": profile["profile"],
        "plan": plan["id"],
        "modules": on,
        "module_names": sorted({_name(m) for m in on}),
        "integrations": integrations,
        "limits": plan.get("limits", {}),
        "upgradable_modules": off,
    }


def module_entitled(entitlement: dict, module_name: str) -> bool:
    if module_name in PLATFORM_MODULES:
        return True
    return module_name in set(entitlement["module_names"]) or module_name in set(entitlement["integrations"])
