"""Which engine answers. `SEARCH_ENGINE=memory` (dev and CI) or `opensearch`; the fake is refused outside dev mode."""

from __future__ import annotations

import threading

from ..application.ports import SearchEngine
from .config import SearchConfig
from .memory_engine import InMemoryEngine
from .opensearch_engine import OpenSearchEngine

_lock = threading.Lock()
_engine: SearchEngine | None = None


def create_engine(config: SearchConfig | None = None) -> SearchEngine:
    config = (config or SearchConfig.from_env()).validate()
    if config.engine == "memory":
        return InMemoryEngine(config.index_environment)
    return OpenSearchEngine(config)


def get_engine() -> SearchEngine:
    global _engine
    with _lock:
        if _engine is None:
            _engine = create_engine()
        return _engine


def set_engine(engine: SearchEngine | None) -> None:
    """Install an engine (tests, or a host that builds its own); None forgets it so the next call builds one."""
    global _engine
    with _lock:
        _engine = engine
