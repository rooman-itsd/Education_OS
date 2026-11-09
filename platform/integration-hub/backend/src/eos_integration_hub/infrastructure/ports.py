"""The ports, read from contracts/ports/*.yaml, so the contract stays the one source of every operation and whether it
is sync or async. Read once per process."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml
from eos_core.settings import settings

from ..domain.vocabulary import PORTS


@dataclass(frozen=True)
class PortSpec:
    id: str
    name: str
    version: int
    operations: dict[str, str]  # operation -> sync | async
    inbound_kinds: tuple[str, ...]


def _contracts_dir() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / "contracts" / "ports"
        if (candidate / "adapter.yaml").is_file():
            return candidate
    return settings.repo_root / "platform" / "integration-hub" / "contracts" / "ports"


@lru_cache(maxsize=1)
def load_ports() -> dict[str, PortSpec]:
    out: dict[str, PortSpec] = {}
    base = _contracts_dir()
    for port_id in PORTS:
        data = yaml.safe_load((base / f"{port_id}.yaml").read_text(encoding="utf-8")) or {}
        operations = {
            op["name"]: op.get("mode", "sync")
            for op in data.get("operations") or []
            if isinstance(op, dict) and isinstance(op.get("name"), str)
        }
        kinds = tuple(i["kind"] for i in data.get("inbound") or [] if isinstance(i, dict) and "kind" in i)
        out[port_id] = PortSpec(
            id=port_id,
            name=str(data.get("port") or port_id),
            version=int(data.get("version") or 1),
            operations=operations,
            inbound_kinds=kinds,
        )
    return out
