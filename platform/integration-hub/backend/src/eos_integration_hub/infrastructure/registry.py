"""The adapter registry and the one place the hub calls an adapter.

Adapters are found on the `eos.integration_adapters` entry-point group (contracts/ports/adapter.yaml, "registration")
and never imported by name: the hub depends on the port, never on a vendor (integrations/README.md, "Swap rule").

Calling convention (README, "Writing an adapter"). The entry point loads an adapter object, or a zero-argument
factory (a class or a function) that returns one. The adapter has `describe()` and one method per operation of
adapter.yaml and of each port it implements, named exactly as the contract names it, called as
`method(context, input)` (or `method(context)` when it takes no input). An adapter may instead offer one dispatcher,
`invoke(context, operation, input)`, for its port operations; `context.port` says which port. Every call returns a
result as adapter.yaml defines it: a mapping (or an object) with `output`, or `error` {code, retry_after_s, detail,
provider_code}, and optionally `provider_reference`. A bare mapping without either key is taken as the output.

Everything an adapter hands back is normalised here: an unknown error code becomes provider_error, the retryable flag
is the contract's (never the adapter's), strings are bounded, and an exception or a timeout is an error result, never
an exception in the hub. A broken adapter is left out of the registry with a log line; it never stops the API."""

from __future__ import annotations

import inspect
import logging
import threading
import time
from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass, field
from datetime import datetime
from importlib import metadata

from ..domain.vocabulary import (
    AUTH_KINDS,
    ERROR_CODES,
    INBOUND_KINDS,
    LINK_SCOPES,
    MAX_DETAIL,
    MAX_PROVIDER_REFERENCE,
    MODES,
    NAME_RE,
    PORTS,
)
from .config import HubConfig

log = logging.getLogger("eos.integration_hub")

GROUP = "eos.integration_adapters"
_POOL = ThreadPoolExecutor(max_workers=16, thread_name_prefix="integration-hub-adapter")


def as_dict(value) -> dict:
    """A mapping, a dataclass or a plain object, as a dict. Anything else is empty."""
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "__dataclass_fields__"):
        return {k: getattr(value, k) for k in value.__dataclass_fields__}
    if hasattr(value, "__dict__"):
        return {k: v for k, v in vars(value).items() if not k.startswith("_")}
    return {}


def _str(value, limit: int) -> str | None:
    if isinstance(value, str) and value:
        return value[:limit]
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)[:limit]
    return None


def _str_list(value, allowed: tuple[str, ...] | None = None) -> tuple[str, ...]:
    if not isinstance(value, list | tuple):
        return ()
    out = [v for v in value if isinstance(v, str) and v and len(v) <= 100]
    if allowed is not None:
        out = [v for v in out if v in allowed]
    return tuple(dict.fromkeys(out))


@dataclass(frozen=True)
class ProviderInfo:
    provider: str
    title: str
    ports: tuple[str, ...]
    modes: tuple[str, ...]
    auth: str
    link_scope: str
    inbound: tuple[str, ...]
    settings_schema: dict
    credential_names: tuple[str, ...]
    platform_credential_names: tuple[str, ...]

    @property
    def uses_authorization_code(self) -> bool:
        return self.auth == "oauth2_authorization_code"


@dataclass
class AdapterInfo:
    adapter: str
    version: str
    ports: tuple[tuple[str, int], ...]
    providers: dict[str, ProviderInfo]
    impl: object = field(repr=False)

    def provider(self, name: str) -> ProviderInfo | None:
        return self.providers.get(name)


def _provider(raw, adapter: str, adapter_ports: tuple[str, ...]) -> ProviderInfo | None:
    d = as_dict(raw)
    name = d.get("provider")
    if not isinstance(name, str) or not NAME_RE.match(name):
        log.warning("adapter %s: a provider has no valid id; skipped", adapter)
        return None
    auth = d.get("auth") if d.get("auth") in AUTH_KINDS else "none"
    schema = d.get("settings_schema") if isinstance(d.get("settings_schema"), Mapping) else {}
    return ProviderInfo(
        provider=name,
        title=_str(d.get("title"), 120) or name,
        ports=_str_list(d.get("ports"), adapter_ports) or adapter_ports,
        modes=_str_list(d.get("modes"), MODES) or ("mock",),
        auth=auth,
        link_scope=d.get("link_scope") if d.get("link_scope") in LINK_SCOPES else "organisation",
        inbound=_str_list(d.get("inbound"), INBOUND_KINDS),
        settings_schema=dict(schema),
        credential_names=_str_list(d.get("credential_names")),
        platform_credential_names=_str_list(d.get("platform_credential_names")),
    )


def _instantiate(loaded):
    """The entry point's object: an adapter, or a zero-argument factory that returns one."""
    if inspect.isclass(loaded):
        return loaded()
    if callable(loaded) and not hasattr(loaded, "describe"):
        return loaded()
    return loaded


def describe_adapter(name: str, impl) -> AdapterInfo:
    describe = getattr(impl, "describe", None)
    raw = describe() if callable(describe) else describe
    d = as_dict(raw)
    if d.get("adapter") not in (None, name):
        log.warning("adapter %s describes itself as %r; the entry point name is used", name, d.get("adapter"))
    ports: list[tuple[str, int]] = []
    for p in d.get("ports") or []:
        pd = as_dict(p) if not isinstance(p, str) else {"port": p, "version": 1}
        port, version = pd.get("port"), pd.get("version", 1)
        if port in PORTS:
            ports.append((port, version if isinstance(version, int) and not isinstance(version, bool) else 1))
    port_ids = tuple(p for p, _v in ports)
    providers: dict[str, ProviderInfo] = {}
    for raw_provider in d.get("providers") or []:
        info = _provider(raw_provider, name, port_ids)
        if info is not None and info.provider not in providers:
            providers[info.provider] = info
    return AdapterInfo(
        adapter=name,
        version=_str(d.get("version"), 40) or "0.0.0",
        ports=tuple(ports),
        providers=providers,
        impl=impl,
    )


@dataclass
class Registry:
    adapters: dict[str, AdapterInfo] = field(default_factory=dict)
    skipped: list[str] = field(default_factory=list)  # adapter names that could not be loaded, for the overview

    def get(self, name: str) -> AdapterInfo | None:
        return self.adapters.get(name)


def discover(config: HubConfig | None = None) -> Registry:
    config = config or HubConfig.from_env()
    registry = Registry()
    try:
        points = list(metadata.entry_points(group=GROUP))
    except Exception as e:  # noqa: BLE001 - a broken installation reads as "no adapters", never a crash
        log.warning("could not read %s entry points: %s", GROUP, type(e).__name__)
        return registry
    by_name: dict[str, list] = {}
    for ep in points:
        by_name.setdefault(ep.name, []).append(ep)
    for name in sorted(by_name):
        if config.adapters and name not in config.adapters:
            continue
        if not NAME_RE.match(name):
            log.warning("adapter entry point %r is not a valid adapter name; skipped", name)
            registry.skipped.append(name[:60])
            continue
        if len(by_name[name]) > 1:
            # Two distributions claiming one name: refuse rather than pick, or which one runs is a coin toss.
            log.warning("adapter %s is provided by %d distributions; skipped", name, len(by_name[name]))
            registry.skipped.append(name)
            continue
        try:
            info = describe_adapter(name, _instantiate(by_name[name][0].load()))
        except Exception as e:  # noqa: BLE001 - never surface an import error's text, never stop the API
            log.warning("adapter %s failed to load: %s", name, type(e).__name__)
            registry.skipped.append(name)
            continue
        registry.adapters[name] = info
    return registry


_lock = threading.Lock()
_cached: Registry | None = None


def get_registry() -> Registry:
    """Discovered once per process; reset_cache() (tests, or an operator after installing an adapter) rediscovers."""
    global _cached
    with _lock:
        if _cached is None:
            _cached = discover()
        return _cached


def reset_cache() -> None:
    global _cached
    with _lock:
        _cached = None


# ------------------------------------------------------------------ calling an adapter


@dataclass
class AdapterContext:
    """What the hub passes to every operation (adapter.yaml, "context"). Reads as attributes or as a mapping. The
    secrets are resolved just before the call, live for that call only and are kept out of repr()."""

    organisation_id: str | None
    connection_id: str | None
    provider: str | None
    mode: str | None
    settings: dict = field(default_factory=dict)
    secrets: dict = field(default_factory=dict, repr=False)
    account_link: dict | None = None
    delivery_id: str | None = None
    attempt: int = 1
    idempotency_key: str | None = None
    deadline: datetime | None = None
    port: str | None = None
    operation: str | None = None

    def __getitem__(self, key: str):
        if key not in self.__dataclass_fields__:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key: str, default=None):
        return getattr(self, key, default) if key in self.__dataclass_fields__ else default

    def keys(self):
        return self.__dataclass_fields__.keys()


@dataclass
class Outcome:
    """A normalised adapter result. Exactly one of output and error_code is set."""

    output: dict | None = None
    error_code: str | None = None
    retry_after_s: int | None = None
    detail: str | None = None
    provider_code: str | None = None
    provider_reference: str | None = None
    duration_ms: int = 0

    @property
    def ok(self) -> bool:
        return self.error_code is None

    @property
    def retryable(self) -> bool:
        return bool(self.error_code and ERROR_CODES.get(self.error_code, False))

    @classmethod
    def failure(cls, code: str, detail: str, provider_code: str | None = None) -> Outcome:
        return cls(
            error_code=code if code in ERROR_CODES else "provider_error",
            detail=detail[:MAX_DETAIL],
            provider_code=provider_code,
        )


def normalise(raw) -> Outcome:
    d = as_dict(raw) if not isinstance(raw, Mapping) else dict(raw)
    if raw is not None and not d and not isinstance(raw, Mapping):
        return Outcome.failure("provider_error", "adapter returned something that is not a result")
    reference = _str(d.get("provider_reference"), MAX_PROVIDER_REFERENCE)
    error = d.get("error")
    if error:
        e = as_dict(error) if not isinstance(error, str) else {"code": error}
        code = e.get("code") if e.get("code") in ERROR_CODES else "provider_error"
        retry_after = e.get("retry_after_s")
        if isinstance(retry_after, bool) or not isinstance(retry_after, int) or retry_after <= 0:
            retry_after = None
        else:
            retry_after = min(retry_after, 86_400)
        return Outcome(
            error_code=code,
            retry_after_s=retry_after,
            detail=_str(e.get("detail"), MAX_DETAIL),
            provider_code=_str(e.get("provider_code"), 40),
            provider_reference=reference,
        )
    if "output" in d or "error" in d:
        output = d.get("output")
        output = as_dict(output) if output is not None and not isinstance(output, Mapping) else dict(output or {})
        return Outcome(output=output, provider_reference=reference)
    d.pop("provider_reference", None)
    return Outcome(output=d, provider_reference=reference)


def _method(impl, name: str):
    fn = getattr(impl, name, None)
    return fn if callable(fn) else None


def _takes_input(fn) -> bool:
    try:
        params = [
            p
            for p in inspect.signature(fn).parameters.values()
            if p.kind in (p.POSITIONAL_ONLY, p.POSITIONAL_OR_KEYWORD, p.VAR_POSITIONAL)
        ]
    except (TypeError, ValueError):
        return True
    return len(params) >= 2 or any(p.kind == p.VAR_POSITIONAL for p in params)


def has_operation(info: AdapterInfo, name: str, *, port_operation: bool = False) -> bool:
    if port_operation and _method(info.impl, "invoke"):
        return True
    return _method(info.impl, name) is not None


def _run(fn, args: tuple, timeout_s: float | None):
    if timeout_s is None:
        return fn(*args)
    return _POOL.submit(fn, *args).result(timeout=timeout_s)


def call(
    info: AdapterInfo,
    operation: str,
    ctx: AdapterContext,
    payload: dict | None = None,
    *,
    timeout_s: float | None,
    port_operation: bool = False,
) -> Outcome:
    """Call one operation and return a normalised Outcome. Never raises for anything the adapter does."""
    payload = payload or {}
    started = time.monotonic()
    dispatcher = _method(info.impl, "invoke") if port_operation else None
    fn = dispatcher or _method(info.impl, operation)
    if fn is None:
        return Outcome.failure("unsupported", f"adapter {info.adapter} does not offer {operation}")
    if dispatcher is not None:
        args: tuple = (ctx, operation, payload)
    else:
        args = (ctx, payload) if _takes_input(fn) else (ctx,)
    try:
        raw = _run(fn, args, timeout_s)
    except FutureTimeout:
        out = Outcome.failure("transport_unavailable", f"{operation} did not answer in time")
    except Exception as e:  # noqa: BLE001 - an adapter must never take the hub down; its text may hold data
        code = getattr(e, "code", None)
        log.warning("adapter %s raised %s in %s", info.adapter, type(e).__name__, operation)
        out = Outcome.failure(code if code in ERROR_CODES else "provider_error", f"adapter raised {type(e).__name__}")
    else:
        out = normalise(raw)
    out.duration_ms = int((time.monotonic() - started) * 1000)
    return out
