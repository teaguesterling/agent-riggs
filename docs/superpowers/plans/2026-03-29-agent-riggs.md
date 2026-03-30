# Agent Riggs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the cross-session memory and analysis layer for the Rigged tool suite — trust scoring, failure stream aggregation, ratchet candidates, and session briefings backed by DuckDB.

**Architecture:** Composable plugin service layer where each subsystem (trust, ingest, ratchet, metrics, briefing, sandbox) is a plugin that registers CLI commands, MCP resources/tools, and schema DDL. CLI and MCP server are thin shells that auto-discover from plugins. Pull-based ingest reads from sibling tool state files.

**Tech Stack:** Python 3.11+, hatchling, Click, DuckDB, mcp[cli], tomli-w, ruff, mypy, pytest

**Spec:** `docs/superpowers/specs/2026-03-29-agent-riggs-design.md`

---

## File Structure

### New files to create

```
pyproject.toml
.gitignore
README.md
src/agent_riggs/__init__.py
src/agent_riggs/config.py
src/agent_riggs/store.py
src/agent_riggs/service.py
src/agent_riggs/assembly.py
src/agent_riggs/defaults/config.toml
src/agent_riggs/plugins/__init__.py
src/agent_riggs/plugins/base.py
src/agent_riggs/plugins/trust.py
src/agent_riggs/plugins/ingest.py
src/agent_riggs/plugins/ratchet.py
src/agent_riggs/plugins/metrics.py
src/agent_riggs/plugins/briefing.py
src/agent_riggs/plugins/sandbox.py
src/agent_riggs/trust/__init__.py
src/agent_riggs/trust/scorer.py
src/agent_riggs/trust/ewma.py
src/agent_riggs/trust/events.py
src/agent_riggs/trust/transitions.py
src/agent_riggs/ingest/__init__.py
src/agent_riggs/ingest/pipeline.py
src/agent_riggs/ingest/sources/__init__.py
src/agent_riggs/ingest/sources/base.py
src/agent_riggs/ingest/sources/kibitzer.py
src/agent_riggs/ingest/sources/blq.py
src/agent_riggs/ingest/sources/jetsam.py
src/agent_riggs/ingest/sources/fledgling.py
src/agent_riggs/ratchet/__init__.py
src/agent_riggs/ratchet/aggregator.py
src/agent_riggs/ratchet/candidates.py
src/agent_riggs/ratchet/promotions.py
src/agent_riggs/ratchet/history.py
src/agent_riggs/sandbox/__init__.py
src/agent_riggs/sandbox/grades.py
src/agent_riggs/sandbox/recommendations.py
src/agent_riggs/sandbox/integration.py
src/agent_riggs/metrics/__init__.py
src/agent_riggs/metrics/compute.py
src/agent_riggs/metrics/trends.py
src/agent_riggs/briefing/__init__.py
src/agent_riggs/briefing/session.py
src/agent_riggs/briefing/project.py
src/agent_riggs/cli.py
src/agent_riggs/mcp/__init__.py
src/agent_riggs/mcp/server.py
tests/__init__.py
tests/conftest.py
tests/test_config.py
tests/test_store.py
tests/test_service.py
tests/test_trust/__init__.py
tests/test_trust/test_scorer.py
tests/test_trust/test_ewma.py
tests/test_trust/test_events.py
tests/test_trust/test_transitions.py
tests/test_ingest/__init__.py
tests/test_ingest/test_pipeline.py
tests/test_ingest/test_kibitzer_source.py
tests/test_ratchet/__init__.py
tests/test_ratchet/test_candidates.py
tests/test_ratchet/test_promotions.py
tests/test_metrics/__init__.py
tests/test_metrics/test_compute.py
tests/test_metrics/test_trends.py
tests/test_briefing/__init__.py
tests/test_briefing/test_session.py
tests/test_cli/__init__.py
tests/test_cli/test_init.py
tests/test_cli/test_status.py
```

---

## Phase 1: Foundation

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `src/agent_riggs/__init__.py`

- [ ] **Step 1: Create pyproject.toml**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "agent-riggs"
version = "0.1.0"
description = "Cross-session memory and analysis layer for the Rigged tool suite"
requires-python = ">=3.11"
license = "MIT"
authors = [
    { name = "Teague Sterling" },
]
keywords = ["claude-code", "mcp", "agent", "trust", "ratchet", "duckdb"]

dependencies = [
    "click>=8.1",
    "duckdb>=1.0",
    "mcp[cli]>=1.0",
    "tomli-w>=1.0",
]

[project.scripts]
agent-riggs = "agent_riggs.cli:main"

[tool.hatch.build.targets.wheel]
packages = ["src/agent_riggs"]

[project.optional-dependencies]
full = []
dev = [
    "pytest>=7.0",
    "pytest-asyncio>=0.21",
    "pytest-cov>=4.0",
    "ruff>=0.1",
    "mypy>=1.0",
]

[tool.ruff]
target-version = "py311"
line-length = 99

[tool.ruff.lint]
select = ["E", "F", "W", "I", "UP", "B", "SIM", "RUF"]

[tool.mypy]
python_version = "3.11"
strict = true

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
```

- [ ] **Step 2: Create .gitignore**

```
__pycache__/
*.pyc
*.egg-info/
dist/
build/
.riggs/
.pytest_cache/
.ruff_cache/
.mypy_cache/
.venv/
.claude/
```

- [ ] **Step 3: Create src/agent_riggs/__init__.py**

```python
"""Agent Riggs — cross-session memory and analysis for the Rigged tool suite."""

__version__ = "0.1.0"
```

- [ ] **Step 4: Install in dev mode and verify**

Run: `pip install -e ".[dev]"`
Expected: Successful install

Run: `python -c "import agent_riggs; print(agent_riggs.__version__)"`
Expected: `0.1.0`

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml .gitignore src/agent_riggs/__init__.py
git commit -m "chore: project scaffolding with hatchling build"
```

---

### Task 2: Default Configuration

**Files:**
- Create: `src/agent_riggs/defaults/config.toml`
- Create: `src/agent_riggs/config.py`
- Create: `tests/conftest.py`
- Create: `tests/__init__.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Create defaults/config.toml**

```toml
[trust]
score_success = 1.0
score_suboptimal = 0.7
score_mode_switch_agent = 0.8
score_mode_switch_controller = 0.3
score_failure = 0.2
score_path_denial = 0.1
score_repeated_failure = 0.0

alpha_short = 0.4
alpha_session = 0.08
alpha_baseline = 0.02

tighten_threshold = 0.3
auto_tighten_threshold = 0.5
loosen_threshold = 0.9
loosen_sustained_turns = 20

[ratchet]
min_frequency = 5
min_sessions = 3
min_success_rate = 0.8
lookback_days = 30

[sandbox]
memory_headroom = 2.0
timeout_headroom = 3.0
cpu_headroom = 2.0
min_runs_for_tightening = 5

[metrics]
default_period_days = 30

[store]
path = ".riggs/store.duckdb"
```

- [ ] **Step 2: Write the failing test for config loading**

Create `tests/__init__.py` (empty).

Create `tests/conftest.py`:

```python
"""Shared fixtures for agent_riggs tests."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """A temporary project directory with .riggs/ created."""
    riggs_dir = tmp_path / ".riggs"
    riggs_dir.mkdir()
    return tmp_path
```

Create `tests/test_config.py`:

```python
from __future__ import annotations

from pathlib import Path

from agent_riggs.config import RiggsConfig, load_config


def test_load_defaults_when_no_user_config(tmp_project: Path) -> None:
    config = load_config(tmp_project)
    assert config.trust.score_success == 1.0
    assert config.trust.alpha_short == 0.4
    assert config.store.path == ".riggs/store.duckdb"


def test_user_config_overrides_defaults(tmp_project: Path) -> None:
    user_config = tmp_project / ".riggs" / "config.toml"
    user_config.write_text('[trust]\nscore_success = 0.9\n')
    config = load_config(tmp_project)
    assert config.trust.score_success == 0.9
    # Other defaults preserved
    assert config.trust.alpha_short == 0.4


def test_config_sections_are_typed(tmp_project: Path) -> None:
    config = load_config(tmp_project)
    assert isinstance(config.trust.score_success, float)
    assert isinstance(config.ratchet.min_frequency, int)
    assert isinstance(config.store.path, str)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_config.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_riggs.config'`

- [ ] **Step 4: Implement config.py**

```python
"""Configuration loading: merge defaults with .riggs/config.toml."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field, fields
from importlib import resources
from pathlib import Path
from typing import Any


@dataclass
class TrustConfig:
    score_success: float = 1.0
    score_suboptimal: float = 0.7
    score_mode_switch_agent: float = 0.8
    score_mode_switch_controller: float = 0.3
    score_failure: float = 0.2
    score_path_denial: float = 0.1
    score_repeated_failure: float = 0.0
    alpha_short: float = 0.4
    alpha_session: float = 0.08
    alpha_baseline: float = 0.02
    tighten_threshold: float = 0.3
    auto_tighten_threshold: float = 0.5
    loosen_threshold: float = 0.9
    loosen_sustained_turns: int = 20


@dataclass
class RatchetConfig:
    min_frequency: int = 5
    min_sessions: int = 3
    min_success_rate: float = 0.8
    lookback_days: int = 30


@dataclass
class SandboxConfig:
    memory_headroom: float = 2.0
    timeout_headroom: float = 3.0
    cpu_headroom: float = 2.0
    min_runs_for_tightening: int = 5


@dataclass
class MetricsConfig:
    default_period_days: int = 30


@dataclass
class StoreConfig:
    path: str = ".riggs/store.duckdb"


@dataclass
class RiggsConfig:
    trust: TrustConfig = field(default_factory=TrustConfig)
    ratchet: RatchetConfig = field(default_factory=RatchetConfig)
    sandbox: SandboxConfig = field(default_factory=SandboxConfig)
    metrics: MetricsConfig = field(default_factory=MetricsConfig)
    store: StoreConfig = field(default_factory=StoreConfig)


def _load_defaults() -> dict[str, Any]:
    """Load the shipped defaults/config.toml."""
    defaults_ref = resources.files("agent_riggs") / "defaults" / "config.toml"
    return tomllib.loads(defaults_ref.read_text(encoding="utf-8"))


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Merge override into base, recursing into nested dicts."""
    merged = dict(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _dict_to_dataclass(cls: type, data: dict[str, Any]) -> Any:
    """Convert a dict to a dataclass, ignoring unknown keys."""
    known = {f.name for f in fields(cls)}
    return cls(**{k: v for k, v in data.items() if k in known})


def load_config(project_root: Path) -> RiggsConfig:
    """Load config: defaults merged with .riggs/config.toml."""
    merged = _load_defaults()

    user_path = project_root / ".riggs" / "config.toml"
    if user_path.exists():
        user = tomllib.loads(user_path.read_text(encoding="utf-8"))
        merged = _deep_merge(merged, user)

    return RiggsConfig(
        trust=_dict_to_dataclass(TrustConfig, merged.get("trust", {})),
        ratchet=_dict_to_dataclass(RatchetConfig, merged.get("ratchet", {})),
        sandbox=_dict_to_dataclass(SandboxConfig, merged.get("sandbox", {})),
        metrics=_dict_to_dataclass(MetricsConfig, merged.get("metrics", {})),
        store=_dict_to_dataclass(StoreConfig, merged.get("store", {})),
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_config.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add src/agent_riggs/defaults/ src/agent_riggs/config.py tests/
git commit -m "feat: config system with defaults and user override"
```

---

### Task 3: DuckDB Store

**Files:**
- Create: `src/agent_riggs/store.py`
- Create: `tests/test_store.py`

- [ ] **Step 1: Write the failing test**

```python
from __future__ import annotations

from pathlib import Path

import duckdb
import pytest

from agent_riggs.store import Store


def test_store_creates_database_file(tmp_project: Path) -> None:
    db_path = tmp_project / ".riggs" / "store.duckdb"
    store = Store(db_path)
    assert db_path.exists()
    store.close()


def test_store_ensure_schema_is_idempotent(tmp_project: Path) -> None:
    db_path = tmp_project / ".riggs" / "store.duckdb"
    store = Store(db_path)
    ddl = ["CREATE TABLE IF NOT EXISTS test_table (id INTEGER PRIMARY KEY, name VARCHAR)"]
    store.ensure_schema(ddl)
    store.ensure_schema(ddl)  # second call should not error
    result = store.execute("SELECT count(*) FROM test_table").fetchone()
    assert result == (0,)
    store.close()


def test_store_execute_returns_results(tmp_project: Path) -> None:
    db_path = tmp_project / ".riggs" / "store.duckdb"
    store = Store(db_path)
    store.execute("CREATE TABLE t (x INTEGER)")
    store.execute("INSERT INTO t VALUES (42)")
    result = store.execute("SELECT x FROM t").fetchone()
    assert result == (42,)
    store.close()


def test_store_read_only_mode(tmp_project: Path) -> None:
    db_path = tmp_project / ".riggs" / "store.duckdb"
    # Create and populate
    store = Store(db_path)
    store.execute("CREATE TABLE t (x INTEGER)")
    store.execute("INSERT INTO t VALUES (1)")
    store.close()

    # Open read-only
    ro_store = Store(db_path, read_only=True)
    result = ro_store.execute("SELECT x FROM t").fetchone()
    assert result == (1,)
    with pytest.raises(duckdb.InvalidInputException):
        ro_store.execute("INSERT INTO t VALUES (2)")
    ro_store.close()


def test_store_context_manager(tmp_project: Path) -> None:
    db_path = tmp_project / ".riggs" / "store.duckdb"
    with Store(db_path) as store:
        store.execute("CREATE TABLE t (x INTEGER)")
        store.execute("INSERT INTO t VALUES (1)")
        result = store.execute("SELECT x FROM t").fetchone()
        assert result == (1,)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'agent_riggs.store'`

- [ ] **Step 3: Implement store.py**

```python
"""DuckDB persistence layer for .riggs/store.duckdb."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb


class Store:
    """Thin wrapper around DuckDB. Plugins own their schema."""

    def __init__(self, path: Path | str, read_only: bool = False) -> None:
        self.path = Path(path)
        self.read_only = read_only
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = duckdb.connect(str(self.path), read_only=read_only)

    def ensure_schema(self, ddl_statements: list[str]) -> None:
        """Execute DDL from all plugins. Idempotent."""
        for ddl in ddl_statements:
            self.conn.execute(ddl)

    def execute(self, query: str, params: list[Any] | None = None) -> duckdb.DuckDBPyRelation:
        """Execute a query and return the result."""
        if params:
            return self.conn.execute(query, params)
        return self.conn.execute(query)

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> Store:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_store.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/agent_riggs/store.py tests/test_store.py
git commit -m "feat: DuckDB store with idempotent schema creation"
```

---

### Task 4: Plugin Protocol, Service, and Assembly

**Files:**
- Create: `src/agent_riggs/plugins/__init__.py`
- Create: `src/agent_riggs/plugins/base.py`
- Create: `src/agent_riggs/service.py`
- Create: `src/agent_riggs/assembly.py`
- Create: `tests/test_service.py`

- [ ] **Step 1: Write the failing test**

```python
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import click

from agent_riggs.config import RiggsConfig, load_config
from agent_riggs.plugins.base import ServicePlugin
from agent_riggs.service import RiggsService
from agent_riggs.store import Store


class StubPlugin:
    """Minimal plugin for testing."""

    name = "stub"

    def bind(self, service: RiggsService) -> None:
        self.service = service

    def cli_commands(self) -> list[click.Command]:
        @click.command("stub-cmd")
        def stub_cmd() -> None:
            click.echo("stub")
        return [stub_cmd]

    def mcp_resources(self) -> list[tuple[str, Callable[..., Any]]]:
        return [("riggs://stub", lambda: "stub data")]

    def mcp_tools(self) -> list[tuple[str, Callable[..., Any]]]:
        return []

    def schema_ddl(self) -> list[str]:
        return ["CREATE TABLE IF NOT EXISTS stub_table (id INTEGER PRIMARY KEY)"]


def test_service_register_plugin(tmp_project: Path) -> None:
    config = load_config(tmp_project)
    db_path = tmp_project / ".riggs" / "store.duckdb"
    with Store(db_path) as store:
        service = RiggsService(tmp_project, store, config)
        plugin = StubPlugin()
        service.register(plugin)

        assert "stub" in service.plugins
        assert service.plugin("stub") is plugin
        assert plugin.service is service


def test_service_plugin_schema_applied(tmp_project: Path) -> None:
    config = load_config(tmp_project)
    db_path = tmp_project / ".riggs" / "store.duckdb"
    with Store(db_path) as store:
        service = RiggsService(tmp_project, store, config)
        plugin = StubPlugin()
        service.register(plugin)
        store.ensure_schema(plugin.schema_ddl())

        result = store.execute("SELECT count(*) FROM stub_table").fetchone()
        assert result == (0,)


def test_service_plugin_cli_commands(tmp_project: Path) -> None:
    config = load_config(tmp_project)
    db_path = tmp_project / ".riggs" / "store.duckdb"
    with Store(db_path) as store:
        service = RiggsService(tmp_project, store, config)
        plugin = StubPlugin()
        service.register(plugin)

        commands = plugin.cli_commands()
        assert len(commands) == 1
        assert commands[0].name == "stub-cmd"


def test_service_unknown_plugin_raises(tmp_project: Path) -> None:
    config = load_config(tmp_project)
    db_path = tmp_project / ".riggs" / "store.duckdb"
    with Store(db_path) as store:
        service = RiggsService(tmp_project, store, config)
        import pytest
        with pytest.raises(KeyError):
            service.plugin("nonexistent")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_service.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement plugins/base.py**

Create `src/agent_riggs/plugins/__init__.py` (empty).

```python
"""Plugin protocol for agent_riggs service layer."""

from __future__ import annotations

from typing import Any, Callable, Protocol, runtime_checkable

import click

from agent_riggs.service import RiggsService


@runtime_checkable
class ServicePlugin(Protocol):
    """Protocol that all agent_riggs plugins implement."""

    name: str

    def bind(self, service: RiggsService) -> None:
        """Receive service reference for cross-plugin access."""
        ...

    def cli_commands(self) -> list[click.Command]:
        """Commands this plugin contributes to the CLI."""
        ...

    def mcp_resources(self) -> list[tuple[str, Callable[..., Any]]]:
        """(uri, handler) pairs for MCP resources."""
        ...

    def mcp_tools(self) -> list[tuple[str, Callable[..., Any]]]:
        """(name, handler) pairs for MCP tools."""
        ...

    def schema_ddl(self) -> list[str]:
        """DDL statements for tables this plugin owns."""
        ...
```

- [ ] **Step 4: Implement service.py**

```python
"""RiggsService: composable plugin architecture."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from agent_riggs.config import RiggsConfig
from agent_riggs.store import Store

if TYPE_CHECKING:
    from agent_riggs.plugins.base import ServicePlugin


class RiggsService:
    """Composes plugins. CLI and MCP server use this."""

    def __init__(self, project_root: Path, store: Store, config: RiggsConfig) -> None:
        self.project_root = project_root
        self.store = store
        self.config = config
        self._plugins: dict[str, ServicePlugin] = {}

    def register(self, plugin: ServicePlugin) -> None:
        """Register a plugin and bind it to this service."""
        self._plugins[plugin.name] = plugin
        plugin.bind(self)

    def plugin(self, name: str) -> ServicePlugin:
        """Get a registered plugin by name. Raises KeyError if not found."""
        return self._plugins[name]

    @property
    def plugins(self) -> dict[str, ServicePlugin]:
        return dict(self._plugins)
```

- [ ] **Step 5: Implement assembly.py**

```python
"""Build a RiggsService from discovered plugins."""

from __future__ import annotations

from pathlib import Path

from agent_riggs.config import load_config
from agent_riggs.service import RiggsService
from agent_riggs.store import Store


def assemble(project_root: Path, read_only: bool = False) -> RiggsService:
    """Build the service with all discovered plugins."""
    config = load_config(project_root)
    store_path = project_root / config.store.path
    store = Store(store_path, read_only=read_only)
    service = RiggsService(project_root, store, config)

    _register_core_plugins(service)
    _register_optional_plugins(service)

    ddl: list[str] = []
    for p in service.plugins.values():
        ddl.extend(p.schema_ddl())
    if not read_only:
        store.ensure_schema(ddl)

    return service


def _register_core_plugins(service: RiggsService) -> None:
    """Register plugins that are always available."""
    from agent_riggs.plugins.trust import TrustPlugin
    from agent_riggs.plugins.ingest import IngestPlugin
    from agent_riggs.plugins.ratchet import RatchetPlugin
    from agent_riggs.plugins.metrics import MetricsPlugin
    from agent_riggs.plugins.briefing import BriefingPlugin

    service.register(TrustPlugin())
    service.register(IngestPlugin())
    service.register(RatchetPlugin())
    service.register(MetricsPlugin())
    service.register(BriefingPlugin())


def _register_optional_plugins(service: RiggsService) -> None:
    """Register plugins whose backing tools may not be installed."""
    import shutil

    if shutil.which("blq"):
        from agent_riggs.plugins.sandbox import SandboxPlugin
        service.register(SandboxPlugin())
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_service.py -v`
Expected: 4 passed

- [ ] **Step 7: Commit**

```bash
git add src/agent_riggs/plugins/ src/agent_riggs/service.py src/agent_riggs/assembly.py tests/test_service.py
git commit -m "feat: plugin protocol, service layer, and assembly"
```

---

## Phase 2: Trust Engine

### Task 5: Trust Events and Scorer

**Files:**
- Create: `src/agent_riggs/trust/__init__.py`
- Create: `src/agent_riggs/trust/events.py`
- Create: `src/agent_riggs/trust/scorer.py`
- Create: `tests/test_trust/__init__.py`
- Create: `tests/test_trust/test_events.py`
- Create: `tests/test_trust/test_scorer.py`

- [ ] **Step 1: Write the failing tests for events**

```python
from __future__ import annotations

from datetime import datetime, timezone

from agent_riggs.trust.events import TurnEvent, EventCategory


def test_turn_event_creation() -> None:
    event = TurnEvent(
        session_id="sess-1",
        turn_number=1,
        timestamp=datetime.now(timezone.utc),
        tool_name="Read",
        tool_success=True,
        mode="implement",
        event_category=EventCategory.SUCCESS,
        metadata={},
    )
    assert event.session_id == "sess-1"
    assert event.event_category == EventCategory.SUCCESS


def test_event_category_values() -> None:
    assert EventCategory.SUCCESS.value == "success"
    assert EventCategory.PATH_DENIAL.value == "path_denial"
    assert EventCategory.EDIT_FAILURE.value == "edit_failure"
    assert EventCategory.REPEATED_FAILURE.value == "repeated_failure"
```

- [ ] **Step 2: Write the failing tests for scorer**

```python
from __future__ import annotations

from datetime import datetime, timezone

from agent_riggs.config import TrustConfig
from agent_riggs.trust.events import TurnEvent, EventCategory
from agent_riggs.trust.scorer import score_event


def _make_event(category: EventCategory) -> TurnEvent:
    return TurnEvent(
        session_id="sess-1",
        turn_number=1,
        timestamp=datetime.now(timezone.utc),
        tool_name="Read",
        tool_success=True,
        mode="implement",
        event_category=category,
        metadata={},
    )


def test_score_success() -> None:
    config = TrustConfig()
    assert score_event(_make_event(EventCategory.SUCCESS), config) == 1.0


def test_score_suboptimal() -> None:
    config = TrustConfig()
    assert score_event(_make_event(EventCategory.SUBOPTIMAL), config) == 0.7


def test_score_path_denial() -> None:
    config = TrustConfig()
    assert score_event(_make_event(EventCategory.PATH_DENIAL), config) == 0.1


def test_score_repeated_failure() -> None:
    config = TrustConfig()
    assert score_event(_make_event(EventCategory.REPEATED_FAILURE), config) == 0.0


def test_score_with_custom_config() -> None:
    config = TrustConfig(score_success=0.5)
    assert score_event(_make_event(EventCategory.SUCCESS), config) == 0.5


def test_score_all_categories_are_handled() -> None:
    """Every EventCategory should produce a valid score."""
    config = TrustConfig()
    for category in EventCategory:
        score = score_event(_make_event(category), config)
        assert 0.0 <= score <= 1.0, f"{category} produced invalid score {score}"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_trust/ -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Implement events.py**

Create `src/agent_riggs/trust/__init__.py` (empty).

```python
"""Turn events — the unit of observation for the trust engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class EventCategory(Enum):
    SUCCESS = "success"
    SUBOPTIMAL = "suboptimal"
    MODE_SWITCH_AGENT = "mode_switch_agent"
    MODE_SWITCH_CONTROLLER = "mode_switch_controller"
    FAILURE = "failure"
    PATH_DENIAL = "path_denial"
    REPEATED_FAILURE = "repeated_failure"


@dataclass(frozen=True)
class TurnEvent:
    session_id: str
    turn_number: int
    timestamp: datetime
    tool_name: str | None
    tool_success: bool | None
    mode: str | None
    event_category: EventCategory
    metadata: dict[str, Any] = field(default_factory=dict)
```

- [ ] **Step 5: Implement scorer.py**

```python
"""Per-turn scoring function. Pure, no side effects."""

from __future__ import annotations

from agent_riggs.config import TrustConfig
from agent_riggs.trust.events import EventCategory, TurnEvent

_CATEGORY_TO_CONFIG_KEY: dict[EventCategory, str] = {
    EventCategory.SUCCESS: "score_success",
    EventCategory.SUBOPTIMAL: "score_suboptimal",
    EventCategory.MODE_SWITCH_AGENT: "score_mode_switch_agent",
    EventCategory.MODE_SWITCH_CONTROLLER: "score_mode_switch_controller",
    EventCategory.FAILURE: "score_failure",
    EventCategory.PATH_DENIAL: "score_path_denial",
    EventCategory.REPEATED_FAILURE: "score_repeated_failure",
}


def score_event(event: TurnEvent, config: TrustConfig) -> float:
    """Score a turn event (0-1) based on its category and config."""
    key = _CATEGORY_TO_CONFIG_KEY[event.event_category]
    return float(getattr(config, key))
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_trust/ -v`
Expected: 8 passed

- [ ] **Step 7: Commit**

```bash
git add src/agent_riggs/trust/ tests/test_trust/
git commit -m "feat: trust events and scorer"
```

---

### Task 6: Trust EWMA

**Files:**
- Create: `src/agent_riggs/trust/ewma.py`
- Create: `tests/test_trust/test_ewma.py`

- [ ] **Step 1: Write the failing tests**

```python
from __future__ import annotations

import pytest

from agent_riggs.trust.ewma import TrustEWMA


def test_initial_values() -> None:
    ewma = TrustEWMA()
    assert ewma.t1 == 1.0
    assert ewma.t5 == 1.0
    assert ewma.t15 == 1.0


def test_update_with_perfect_score() -> None:
    ewma = TrustEWMA()
    t1, t5, t15 = ewma.update(1.0)
    # All should stay at 1.0
    assert t1 == 1.0
    assert t5 == 1.0
    assert t15 == 1.0


def test_update_with_zero_score() -> None:
    ewma = TrustEWMA()
    t1, t5, t15 = ewma.update(0.0)
    # t1 should drop the most (highest alpha)
    assert t1 == pytest.approx(0.6)   # 1.0 * (1 - 0.4) + 0 * 0.4
    assert t5 == pytest.approx(0.92)  # 1.0 * (1 - 0.08) + 0 * 0.08
    assert t15 == pytest.approx(0.98) # 1.0 * (1 - 0.02) + 0 * 0.02


def test_repeated_failures_converge_toward_zero() -> None:
    ewma = TrustEWMA()
    for _ in range(50):
        ewma.update(0.0)
    assert ewma.t1 < 0.01
    assert ewma.t5 < 0.05
    assert ewma.t15 > 0.1  # baseline moves slowly


def test_recovery_after_failures() -> None:
    ewma = TrustEWMA()
    for _ in range(10):
        ewma.update(0.0)
    low_t1 = ewma.t1
    for _ in range(10):
        ewma.update(1.0)
    assert ewma.t1 > low_t1


def test_custom_alphas() -> None:
    ewma = TrustEWMA(alpha_short=1.0, alpha_session=1.0, alpha_baseline=1.0)
    t1, t5, t15 = ewma.update(0.5)
    # With alpha=1.0, EWMA immediately takes the new value
    assert t1 == pytest.approx(0.5)
    assert t5 == pytest.approx(0.5)
    assert t15 == pytest.approx(0.5)


def test_snapshot_and_restore() -> None:
    ewma = TrustEWMA()
    ewma.update(0.5)
    ewma.update(0.8)
    snapshot = ewma.snapshot()

    restored = TrustEWMA.from_snapshot(snapshot)
    assert restored.t1 == pytest.approx(ewma.t1)
    assert restored.t5 == pytest.approx(ewma.t5)
    assert restored.t15 == pytest.approx(ewma.t15)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_trust/test_ewma.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement ewma.py**

```python
"""Three-window exponentially weighted moving average for trust."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TrustSnapshot:
    """Serializable snapshot of EWMA state."""

    t1: float
    t5: float
    t15: float
    alpha_short: float
    alpha_session: float
    alpha_baseline: float


class TrustEWMA:
    """Three-window EWMA. Three multiplications per update."""

    def __init__(
        self,
        alpha_short: float = 0.4,
        alpha_session: float = 0.08,
        alpha_baseline: float = 0.02,
    ) -> None:
        self.alpha_short = alpha_short
        self.alpha_session = alpha_session
        self.alpha_baseline = alpha_baseline
        self.t1 = 1.0
        self.t5 = 1.0
        self.t15 = 1.0

    def update(self, score: float) -> tuple[float, float, float]:
        """Update all three windows. Returns (t1, t5, t15)."""
        self.t1 = self.t1 * (1 - self.alpha_short) + score * self.alpha_short
        self.t5 = self.t5 * (1 - self.alpha_session) + score * self.alpha_session
        self.t15 = self.t15 * (1 - self.alpha_baseline) + score * self.alpha_baseline
        return (self.t1, self.t5, self.t15)

    def snapshot(self) -> TrustSnapshot:
        """Serialize current state."""
        return TrustSnapshot(
            t1=self.t1,
            t5=self.t5,
            t15=self.t15,
            alpha_short=self.alpha_short,
            alpha_session=self.alpha_session,
            alpha_baseline=self.alpha_baseline,
        )

    @classmethod
    def from_snapshot(cls, snap: TrustSnapshot) -> TrustEWMA:
        """Restore from a snapshot."""
        ewma = cls(
            alpha_short=snap.alpha_short,
            alpha_session=snap.alpha_session,
            alpha_baseline=snap.alpha_baseline,
        )
        ewma.t1 = snap.t1
        ewma.t5 = snap.t5
        ewma.t15 = snap.t15
        return ewma
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_trust/test_ewma.py -v`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add src/agent_riggs/trust/ewma.py tests/test_trust/test_ewma.py
git commit -m "feat: three-window EWMA for trust scoring"
```

---

### Task 7: Trust Transitions

**Files:**
- Create: `src/agent_riggs/trust/transitions.py`
- Create: `tests/test_trust/test_transitions.py`

- [ ] **Step 1: Write the failing tests**

```python
from __future__ import annotations

from agent_riggs.config import TrustConfig
from agent_riggs.trust.transitions import (
    TransitionAction,
    Recommendation,
    recommend_transition,
)


def test_no_recommendation_when_healthy() -> None:
    config = TrustConfig()
    result = recommend_transition(t1=0.9, t5=0.8, t15=0.85, turn_count=10, config=config)
    assert result is None


def test_recommend_tighten_when_t1_low() -> None:
    config = TrustConfig()
    result = recommend_transition(t1=0.2, t5=0.6, t15=0.8, turn_count=10, config=config)
    assert result is not None
    assert result.action == TransitionAction.TIGHTEN


def test_auto_tighten_when_both_low() -> None:
    config = TrustConfig()
    result = recommend_transition(t1=0.2, t5=0.4, t15=0.7, turn_count=10, config=config)
    assert result is not None
    assert result.action == TransitionAction.AUTO_TIGHTEN


def test_suggest_loosen_when_sustained_high() -> None:
    config = TrustConfig()
    result = recommend_transition(t1=0.95, t5=0.85, t15=0.9, turn_count=25, config=config)
    assert result is not None
    assert result.action == TransitionAction.LOOSEN


def test_no_loosen_if_not_sustained() -> None:
    config = TrustConfig()
    result = recommend_transition(t1=0.95, t5=0.85, t15=0.9, turn_count=10, config=config)
    assert result is None


def test_flag_project_when_baseline_low() -> None:
    config = TrustConfig()
    result = recommend_transition(t1=0.8, t5=0.6, t15=0.4, turn_count=10, config=config)
    assert result is not None
    assert result.action == TransitionAction.FLAG_PROJECT
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_trust/test_transitions.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement transitions.py**

```python
"""Trust-informed mode transition recommendations."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from agent_riggs.config import TrustConfig


class TransitionAction(Enum):
    TIGHTEN = "tighten"
    AUTO_TIGHTEN = "auto_tighten"
    LOOSEN = "loosen"
    FLAG_PROJECT = "flag_project"


@dataclass(frozen=True)
class Recommendation:
    action: TransitionAction
    reason: str
    trust_1: float
    trust_5: float


def recommend_transition(
    t1: float,
    t5: float,
    t15: float,
    turn_count: int,
    config: TrustConfig,
) -> Recommendation | None:
    """Evaluate trust state and return a recommendation, or None if healthy.

    Rules are evaluated in priority order (most urgent first).
    """
    # Auto-tighten: both short and session windows are bad
    if t1 < config.tighten_threshold and t5 < config.auto_tighten_threshold:
        return Recommendation(
            action=TransitionAction.AUTO_TIGHTEN,
            reason=f"trust_1={t1:.2f} < {config.tighten_threshold} "
            f"and trust_5={t5:.2f} < {config.auto_tighten_threshold}",
            trust_1=t1,
            trust_5=t5,
        )

    # Tighten: short window is bad
    if t1 < config.tighten_threshold:
        return Recommendation(
            action=TransitionAction.TIGHTEN,
            reason=f"trust_1={t1:.2f} < {config.tighten_threshold}",
            trust_1=t1,
            trust_5=t5,
        )

    # Flag project: baseline is bad
    if t15 < config.auto_tighten_threshold:
        return Recommendation(
            action=TransitionAction.FLAG_PROJECT,
            reason=f"trust_15={t15:.2f} < {config.auto_tighten_threshold}: "
            "project configuration needs review",
            trust_1=t1,
            trust_5=t5,
        )

    # Loosen: sustained high trust
    if (
        t1 > config.loosen_threshold
        and t5 > config.loosen_threshold - 0.1
        and turn_count >= config.loosen_sustained_turns
    ):
        return Recommendation(
            action=TransitionAction.LOOSEN,
            reason=f"trust_1={t1:.2f} and trust_5={t5:.2f} sustained "
            f"for {turn_count} turns",
            trust_1=t1,
            trust_5=t5,
        )

    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_trust/test_transitions.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/agent_riggs/trust/transitions.py tests/test_trust/test_transitions.py
git commit -m "feat: trust-informed transition recommendations"
```

---

### Task 8: Trust Plugin

**Files:**
- Create: `src/agent_riggs/plugins/trust.py`

This wires the trust engine into the service layer. We test it through the service tests and integration tests later — the trust engine itself is already tested.

- [ ] **Step 1: Implement the trust plugin**

```python
"""Trust plugin — wires trust engine into the service layer."""

from __future__ import annotations

from typing import Any, Callable, TYPE_CHECKING

import click

if TYPE_CHECKING:
    from agent_riggs.service import RiggsService

TRUST_DDL = [
    """
    CREATE TABLE IF NOT EXISTS turns (
        turn_id         BIGINT PRIMARY KEY,
        session_id      VARCHAR NOT NULL,
        project         VARCHAR NOT NULL,
        turn_number     INTEGER NOT NULL,
        timestamp       TIMESTAMPTZ NOT NULL,
        tool_name       VARCHAR,
        tool_success    BOOLEAN,
        mode            VARCHAR,
        trust_score     DOUBLE,
        trust_1         DOUBLE,
        trust_5         DOUBLE,
        trust_15        DOUBLE,
        event_category  VARCHAR,
        metadata        JSON
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS failure_stream (
        failure_id       BIGINT PRIMARY KEY,
        turn_id          BIGINT,
        session_id       VARCHAR NOT NULL,
        project          VARCHAR NOT NULL,
        occurred_at      TIMESTAMPTZ NOT NULL,
        failure_category VARCHAR NOT NULL,
        tool_name        VARCHAR,
        mode             VARCHAR,
        trust_at_failure DOUBLE,
        detail           JSON
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS session_summaries (
        session_id      VARCHAR PRIMARY KEY,
        project         VARCHAR NOT NULL,
        started_at      TIMESTAMPTZ,
        ended_at        TIMESTAMPTZ,
        duration        INTERVAL,
        total_turns     INTEGER,
        total_failures  INTEGER,
        failure_rate    DOUBLE,
        trust_start     DOUBLE,
        trust_end       DOUBLE,
        trust_delta     DOUBLE,
        modes_used      VARCHAR[],
        mode_switches   INTEGER,
        computation_channel_fraction DOUBLE,
        structured_tool_fraction     DOUBLE
    )
    """,
]

_FAILURE_CATEGORIES = frozenset({
    "failure", "path_denial", "edit_failure", "repeated_failure",
    "timeout", "mode_forced", "sandbox_violation", "trust_drop",
})


class TrustPlugin:
    name = "trust"

    def bind(self, service: RiggsService) -> None:
        self.service = service
        self.store = service.store
        self.config = service.config.trust

    def schema_ddl(self) -> list[str]:
        return list(TRUST_DDL)

    def cli_commands(self) -> list[click.Command]:
        return []  # Added in Task 14 (CLI)

    def mcp_resources(self) -> list[tuple[str, Callable[..., Any]]]:
        return [("riggs://trust", self._trust_resource)]

    def mcp_tools(self) -> list[tuple[str, Callable[..., Any]]]:
        return [("RiggsTrust", self._trust_tool)]

    def current(self) -> dict[str, Any]:
        """Get the most recent trust scores for the current project."""
        row = self.store.execute(
            """
            SELECT trust_1, trust_5, trust_15, session_id, turn_number
            FROM turns
            WHERE project = ?
            ORDER BY timestamp DESC
            LIMIT 1
            """,
            [self._project_name()],
        ).fetchone()
        if row is None:
            return {"trust_1": 1.0, "trust_5": 1.0, "trust_15": 1.0, "has_data": False}
        return {
            "trust_1": row[0],
            "trust_5": row[1],
            "trust_15": row[2],
            "session_id": row[3],
            "turn_number": row[4],
            "has_data": True,
        }

    def history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Get trust score history."""
        rows = self.store.execute(
            """
            SELECT trust_1, trust_5, trust_15, session_id, turn_number, timestamp
            FROM turns
            WHERE project = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            [self._project_name(), limit],
        ).fetchall()
        return [
            {
                "trust_1": r[0], "trust_5": r[1], "trust_15": r[2],
                "session_id": r[3], "turn_number": r[4], "timestamp": r[5],
            }
            for r in rows
        ]

    def _project_name(self) -> str:
        return self.service.project_root.name

    def _trust_resource(self) -> str:
        data = self.current()
        if not data["has_data"]:
            return "No trust data yet. Run `agent-riggs ingest` after a session."
        return (
            f"trust: {data['trust_1']:.2f} / {data['trust_5']:.2f} / {data['trust_15']:.2f}\n"
            f"       now    session  baseline"
        )

    def _trust_tool(self, window: int | None = None) -> dict[str, Any]:
        if window:
            return {"current": self.current(), "history": self.history(limit=window)}
        return {"current": self.current()}
```

- [ ] **Step 2: Verify trust module imports cleanly**

Run: `python -c "from agent_riggs.plugins.trust import TrustPlugin; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/agent_riggs/plugins/trust.py
git commit -m "feat: trust plugin with schema DDL and query methods"
```

---

## Phase 3: Ingest Pipeline

### Task 9: Source Protocol and Kibitzer Source

**Files:**
- Create: `src/agent_riggs/ingest/__init__.py`
- Create: `src/agent_riggs/ingest/sources/__init__.py`
- Create: `src/agent_riggs/ingest/sources/base.py`
- Create: `src/agent_riggs/ingest/sources/kibitzer.py`
- Create: `tests/test_ingest/__init__.py`
- Create: `tests/test_ingest/test_kibitzer_source.py`

- [ ] **Step 1: Write the failing tests**

```python
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from agent_riggs.ingest.sources.kibitzer import KibitzerSource
from agent_riggs.trust.events import EventCategory


def _write_kibitzer_state(project: Path, state: dict) -> None:
    kib_dir = project / ".kibitzer"
    kib_dir.mkdir(exist_ok=True)
    (kib_dir / "state.json").write_text(json.dumps(state))


def _write_intercept_log(project: Path, entries: list[dict]) -> None:
    kib_dir = project / ".kibitzer"
    kib_dir.mkdir(exist_ok=True)
    with (kib_dir / "intercept.log").open("w") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")


def test_discover_when_kibitzer_present(tmp_project: Path) -> None:
    _write_kibitzer_state(tmp_project, {"mode": "implement", "turn_count": 5})
    source = KibitzerSource()
    assert source.discover(tmp_project) is True


def test_discover_when_kibitzer_absent(tmp_project: Path) -> None:
    source = KibitzerSource()
    assert source.discover(tmp_project) is False


def test_read_events_from_intercept_log(tmp_project: Path) -> None:
    _write_kibitzer_state(tmp_project, {
        "mode": "implement",
        "turn_count": 3,
        "session_id": "sess-abc",
    })
    _write_intercept_log(tmp_project, [
        {
            "timestamp": "2026-03-29T10:00:00Z",
            "tool": "Bash",
            "command": "grep -rn 'def ' src/",
            "suggestion": "Use FindDefinitions",
            "action": "suggest",
        },
        {
            "timestamp": "2026-03-29T10:01:00Z",
            "tool": "Edit",
            "success": False,
            "error": "old_string not found",
        },
    ])

    source = KibitzerSource()
    events = source.read_events(tmp_project, since=None)
    assert len(events) >= 2
    # Check that event categories are assigned
    categories = {e.event_category for e in events}
    assert EventCategory.SUBOPTIMAL in categories or EventCategory.FAILURE in categories


def test_read_events_respects_since(tmp_project: Path) -> None:
    _write_kibitzer_state(tmp_project, {
        "mode": "implement",
        "turn_count": 2,
        "session_id": "sess-abc",
    })
    _write_intercept_log(tmp_project, [
        {
            "timestamp": "2026-03-28T10:00:00Z",
            "tool": "Read",
            "success": True,
        },
        {
            "timestamp": "2026-03-29T10:00:00Z",
            "tool": "Edit",
            "success": True,
        },
    ])

    source = KibitzerSource()
    since = datetime(2026, 3, 29, tzinfo=timezone.utc)
    events = source.read_events(tmp_project, since=since)
    assert len(events) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_ingest/test_kibitzer_source.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement source base protocol and stub sources**

Create `src/agent_riggs/ingest/__init__.py` and `src/agent_riggs/ingest/sources/__init__.py` (both empty).

Create stub source files for tools not yet implemented (`blq.py`, `jetsam.py`, `fledgling.py`):

```python
"""Stub source — not yet implemented."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from agent_riggs.trust.events import TurnEvent


class BlqSource:  # or JetsamSource, FledglingSource
    name = "blq"  # or "jetsam", "fledgling"

    def discover(self, project_root: Path) -> bool:
        return False  # Not yet implemented

    def read_events(
        self, project_root: Path, since: datetime | None
    ) -> list[TurnEvent]:
        return []
```

Create `src/agent_riggs/ingest/sources/base.py`:

```python
"""Source protocol for ingest pipeline."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Protocol

from agent_riggs.trust.events import TurnEvent


class Source(Protocol):
    """A data source that produces TurnEvents from a sibling tool."""

    name: str

    def discover(self, project_root: Path) -> bool:
        """Is this tool's state present in the project?"""
        ...

    def read_events(
        self, project_root: Path, since: datetime | None
    ) -> list[TurnEvent]:
        """Read events, optionally filtering to those after `since`."""
        ...
```

- [ ] **Step 4: Implement kibitzer source**

```python
"""Kibitzer ingest source — reads .kibitzer/state.json and intercept.log."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from agent_riggs.trust.events import EventCategory, TurnEvent


class KibitzerSource:
    name = "kibitzer"

    def discover(self, project_root: Path) -> bool:
        return (project_root / ".kibitzer" / "state.json").exists()

    def read_events(
        self, project_root: Path, since: datetime | None
    ) -> list[TurnEvent]:
        events: list[TurnEvent] = []
        state = self._read_state(project_root)
        session_id = state.get("session_id", "unknown")
        mode = state.get("mode")

        log_path = project_root / ".kibitzer" / "intercept.log"
        if log_path.exists():
            events.extend(
                self._parse_intercept_log(log_path, session_id, mode, since)
            )

        return events

    def _read_state(self, project_root: Path) -> dict:
        state_path = project_root / ".kibitzer" / "state.json"
        if state_path.exists():
            return json.loads(state_path.read_text())
        return {}

    def _parse_intercept_log(
        self,
        log_path: Path,
        session_id: str,
        mode: str | None,
        since: datetime | None,
    ) -> list[TurnEvent]:
        events: list[TurnEvent] = []
        with log_path.open() as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                ts = self._parse_timestamp(entry.get("timestamp", ""))
                if since and ts < since:
                    continue
                events.append(TurnEvent(
                    session_id=session_id,
                    turn_number=i + 1,
                    timestamp=ts,
                    tool_name=entry.get("tool"),
                    tool_success=entry.get("success"),
                    mode=mode,
                    event_category=self._classify(entry),
                    metadata=entry,
                ))
        return events

    def _classify(self, entry: dict) -> EventCategory:
        """Classify an intercept log entry into an EventCategory."""
        if entry.get("success") is False:
            error = entry.get("error", "")
            if "old_string not found" in error:
                return EventCategory.FAILURE
            return EventCategory.FAILURE

        if entry.get("suggestion"):
            return EventCategory.SUBOPTIMAL

        if entry.get("action") == "redirect":
            return EventCategory.SUBOPTIMAL

        return EventCategory.SUCCESS

    def _parse_timestamp(self, ts_str: str) -> datetime:
        """Parse ISO timestamp, defaulting to UTC."""
        if not ts_str:
            return datetime.now(timezone.utc)
        ts_str = ts_str.replace("Z", "+00:00")
        return datetime.fromisoformat(ts_str)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_ingest/test_kibitzer_source.py -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add src/agent_riggs/ingest/ tests/test_ingest/
git commit -m "feat: ingest source protocol and kibitzer source"
```

---

### Task 10: Ingest Pipeline and Plugin

**Files:**
- Create: `src/agent_riggs/ingest/pipeline.py`
- Create: `src/agent_riggs/plugins/ingest.py`
- Create: `tests/test_ingest/test_pipeline.py`

- [ ] **Step 1: Write the failing tests**

```python
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from agent_riggs.config import load_config
from agent_riggs.ingest.pipeline import ingest, IngestResult
from agent_riggs.ingest.sources.kibitzer import KibitzerSource
from agent_riggs.store import Store


def _setup_kibitzer(project: Path) -> None:
    kib_dir = project / ".kibitzer"
    kib_dir.mkdir(exist_ok=True)
    (kib_dir / "state.json").write_text(json.dumps({
        "mode": "implement",
        "turn_count": 3,
        "session_id": "sess-test",
    }))
    with (kib_dir / "intercept.log").open("w") as f:
        for i in range(3):
            f.write(json.dumps({
                "timestamp": f"2026-03-29T10:0{i}:00Z",
                "tool": "Read",
                "success": True,
            }) + "\n")


def test_ingest_stores_turns(tmp_project: Path) -> None:
    _setup_kibitzer(tmp_project)
    config = load_config(tmp_project)
    db_path = tmp_project / ".riggs" / "store.duckdb"

    with Store(db_path) as store:
        # Need trust schema
        from agent_riggs.plugins.trust import TRUST_DDL
        store.ensure_schema(TRUST_DDL)

        result = ingest(
            store=store,
            project_root=tmp_project,
            sources=[KibitzerSource()],
            trust_config=config.trust,
        )
        assert result.turns_ingested == 3
        assert result.sources_read == ["kibitzer"]

        count = store.execute("SELECT count(*) FROM turns").fetchone()
        assert count == (3,)


def test_ingest_computes_trust_scores(tmp_project: Path) -> None:
    _setup_kibitzer(tmp_project)
    config = load_config(tmp_project)
    db_path = tmp_project / ".riggs" / "store.duckdb"

    with Store(db_path) as store:
        from agent_riggs.plugins.trust import TRUST_DDL
        store.ensure_schema(TRUST_DDL)

        ingest(
            store=store,
            project_root=tmp_project,
            sources=[KibitzerSource()],
            trust_config=config.trust,
        )

        row = store.execute(
            "SELECT trust_1, trust_5, trust_15 FROM turns ORDER BY turn_number DESC LIMIT 1"
        ).fetchone()
        assert row is not None
        # All success events, trust should stay near 1.0
        assert row[0] > 0.9
        assert row[1] > 0.9
        assert row[2] > 0.9


def test_ingest_skips_missing_sources(tmp_project: Path) -> None:
    # No kibitzer dir
    config = load_config(tmp_project)
    db_path = tmp_project / ".riggs" / "store.duckdb"

    with Store(db_path) as store:
        from agent_riggs.plugins.trust import TRUST_DDL
        store.ensure_schema(TRUST_DDL)

        result = ingest(
            store=store,
            project_root=tmp_project,
            sources=[KibitzerSource()],
            trust_config=config.trust,
        )
        assert result.turns_ingested == 0
        assert result.sources_read == []


def test_ingest_records_failures(tmp_project: Path) -> None:
    kib_dir = tmp_project / ".kibitzer"
    kib_dir.mkdir(exist_ok=True)
    (kib_dir / "state.json").write_text(json.dumps({
        "mode": "implement",
        "session_id": "sess-fail",
    }))
    with (kib_dir / "intercept.log").open("w") as f:
        f.write(json.dumps({
            "timestamp": "2026-03-29T10:00:00Z",
            "tool": "Edit",
            "success": False,
            "error": "old_string not found",
        }) + "\n")

    config = load_config(tmp_project)
    db_path = tmp_project / ".riggs" / "store.duckdb"

    with Store(db_path) as store:
        from agent_riggs.plugins.trust import TRUST_DDL
        store.ensure_schema(TRUST_DDL)

        ingest(
            store=store,
            project_root=tmp_project,
            sources=[KibitzerSource()],
            trust_config=config.trust,
        )

        failures = store.execute("SELECT count(*) FROM failure_stream").fetchone()
        assert failures is not None
        assert failures[0] >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_ingest/test_pipeline.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement pipeline.py**

```python
"""Ingest pipeline: discover sources, read events, score, store."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from agent_riggs.config import TrustConfig
from agent_riggs.ingest.sources.base import Source
from agent_riggs.store import Store
from agent_riggs.trust.events import EventCategory, TurnEvent
from agent_riggs.trust.ewma import TrustEWMA
from agent_riggs.trust.scorer import score_event


_FAILURE_CATEGORIES = frozenset({
    EventCategory.FAILURE,
    EventCategory.PATH_DENIAL,
    EventCategory.REPEATED_FAILURE,
})

_next_turn_id = 0


def _gen_turn_id() -> int:
    global _next_turn_id
    _next_turn_id += 1
    return _next_turn_id


@dataclass
class IngestResult:
    turns_ingested: int = 0
    failures_recorded: int = 0
    sources_read: list[str] = field(default_factory=list)


def ingest(
    store: Store,
    project_root: Path,
    sources: list[Source],
    trust_config: TrustConfig,
    since: object | None = None,
) -> IngestResult:
    """Pull events from all discovered sources, score, and store."""
    result = IngestResult()
    project = project_root.name

    # Resume EWMA from last stored state, or start fresh
    ewma = _load_or_create_ewma(store, project, trust_config)

    for source in sources:
        if not source.discover(project_root):
            continue
        result.sources_read.append(source.name)
        events = source.read_events(project_root, since)

        for event in events:
            score = score_event(event, trust_config)
            t1, t5, t15 = ewma.update(score)
            turn_id = _gen_turn_id()

            _store_turn(store, turn_id, project, event, score, t1, t5, t15)
            result.turns_ingested += 1

            if event.event_category in _FAILURE_CATEGORIES:
                _store_failure(store, turn_id, project, event, score)
                result.failures_recorded += 1

    return result


def _load_or_create_ewma(
    store: Store, project: str, config: TrustConfig
) -> TrustEWMA:
    """Load last EWMA state from store, or create fresh."""
    row = store.execute(
        """
        SELECT trust_1, trust_5, trust_15
        FROM turns
        WHERE project = ?
        ORDER BY timestamp DESC
        LIMIT 1
        """,
        [project],
    ).fetchone()

    ewma = TrustEWMA(
        alpha_short=config.alpha_short,
        alpha_session=config.alpha_session,
        alpha_baseline=config.alpha_baseline,
    )
    if row:
        ewma.t1 = row[0]
        ewma.t5 = row[1]
        ewma.t15 = row[2]
    return ewma


def _store_turn(
    store: Store,
    turn_id: int,
    project: str,
    event: TurnEvent,
    score: float,
    t1: float,
    t5: float,
    t15: float,
) -> None:
    store.execute(
        """
        INSERT INTO turns (
            turn_id, session_id, project, turn_number, timestamp,
            tool_name, tool_success, mode, trust_score,
            trust_1, trust_5, trust_15, event_category, metadata
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            turn_id, event.session_id, project, event.turn_number,
            event.timestamp, event.tool_name, event.tool_success,
            event.mode, score, t1, t5, t15,
            event.event_category.value, str(event.metadata),
        ],
    )


def _store_failure(
    store: Store,
    turn_id: int,
    project: str,
    event: TurnEvent,
    trust_at_failure: float,
) -> None:
    store.execute(
        """
        INSERT INTO failure_stream (
            failure_id, turn_id, session_id, project, occurred_at,
            failure_category, tool_name, mode, trust_at_failure, detail
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            turn_id, turn_id, event.session_id, project,
            event.timestamp, event.event_category.value,
            event.tool_name, event.mode, trust_at_failure,
            str(event.metadata),
        ],
    )
```

- [ ] **Step 4: Implement plugins/ingest.py**

```python
"""Ingest plugin — wires ingest pipeline into the service layer."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, TYPE_CHECKING

import click

from agent_riggs.ingest.pipeline import IngestResult, ingest
from agent_riggs.ingest.sources.kibitzer import KibitzerSource

if TYPE_CHECKING:
    from agent_riggs.service import RiggsService


class IngestPlugin:
    name = "ingest"

    def bind(self, service: RiggsService) -> None:
        self.service = service

    def schema_ddl(self) -> list[str]:
        return []  # Trust plugin owns the tables we write to

    def cli_commands(self) -> list[click.Command]:
        return []  # Added in CLI task

    def mcp_resources(self) -> list[tuple[str, Callable[..., Any]]]:
        return []

    def mcp_tools(self) -> list[tuple[str, Callable[..., Any]]]:
        return []

    def run(self, since: datetime | None = None) -> IngestResult:
        """Execute ingest from all discovered sources."""
        sources = self._discover_sources()
        return ingest(
            store=self.service.store,
            project_root=self.service.project_root,
            sources=sources,
            trust_config=self.service.config.trust,
            since=since,
        )

    def _discover_sources(self) -> list[Any]:
        """Return all available sources."""
        return [KibitzerSource()]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_ingest/ -v`
Expected: All passed

- [ ] **Step 6: Commit**

```bash
git add src/agent_riggs/ingest/pipeline.py src/agent_riggs/plugins/ingest.py tests/test_ingest/test_pipeline.py
git commit -m "feat: ingest pipeline with kibitzer source and trust scoring"
```

---

## Phase 4: CLI MVP

### Task 11: CLI Shell with init and status

**Files:**
- Create: `src/agent_riggs/cli.py`
- Create: `tests/test_cli/__init__.py`
- Create: `tests/test_cli/test_init.py`
- Create: `tests/test_cli/test_status.py`

- [ ] **Step 1: Write the failing tests for init**

```python
from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from agent_riggs.cli import main


def test_init_creates_riggs_dir(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["init"])
    assert result.exit_code == 0
    assert (tmp_path / ".riggs").is_dir()
    assert (tmp_path / ".riggs" / "config.toml").exists()
    assert (tmp_path / ".riggs" / "store.duckdb").exists()


def test_init_idempotent(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    runner.invoke(main, ["init"])
    result = runner.invoke(main, ["init"])
    assert result.exit_code == 0
```

- [ ] **Step 2: Write the failing tests for status**

```python
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from agent_riggs.cli import main


def test_status_no_data(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    runner.invoke(main, ["init"])
    result = runner.invoke(main, ["status"])
    assert result.exit_code == 0
    assert "trust" in result.output.lower()


def test_status_with_data(tmp_path: Path, monkeypatch: object) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    runner.invoke(main, ["init"])

    # Set up kibitzer data
    kib_dir = tmp_path / ".kibitzer"
    kib_dir.mkdir(exist_ok=True)
    (kib_dir / "state.json").write_text(json.dumps({
        "mode": "implement",
        "session_id": "sess-1",
    }))
    with (kib_dir / "intercept.log").open("w") as f:
        f.write(json.dumps({
            "timestamp": "2026-03-29T10:00:00Z",
            "tool": "Read",
            "success": True,
        }) + "\n")

    runner.invoke(main, ["ingest"])
    result = runner.invoke(main, ["status"])
    assert result.exit_code == 0
    assert "trust" in result.output.lower()
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_cli/ -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Implement cli.py**

```python
"""CLI entry point for agent-riggs."""

from __future__ import annotations

import shutil
from importlib import resources
from pathlib import Path

import click

from agent_riggs import __version__


def find_project_root() -> Path:
    """Find the project root (cwd for now)."""
    return Path.cwd()


@click.group()
@click.version_option(__version__, prog_name="agent-riggs")
@click.pass_context
def main(ctx: click.Context) -> None:
    """agent-riggs -- cross-session memory and analysis for the Rigged tool suite."""
    ctx.ensure_object(dict)


@main.command()
def init() -> None:
    """Initialize .riggs/ directory and store."""
    project_root = find_project_root()
    riggs_dir = project_root / ".riggs"
    riggs_dir.mkdir(exist_ok=True)

    # Copy default config if not present
    config_path = riggs_dir / "config.toml"
    if not config_path.exists():
        defaults_ref = resources.files("agent_riggs") / "defaults" / "config.toml"
        config_path.write_text(defaults_ref.read_text(encoding="utf-8"))

    # Create store (schema will be created on assembly)
    from agent_riggs.assembly import assemble

    service = assemble(project_root)

    # Discover tools
    tools = []
    for name in ("kibitzer", "blq", "jetsam", "fledgling"):
        if shutil.which(name) or (project_root / f".{name}").exists():
            tools.append(name)

    click.echo(f"Initialized .riggs/ in {project_root}")
    if tools:
        click.echo(f"Discovered tools: {', '.join(tools)}")
    else:
        click.echo("No sibling tools discovered yet.")

    service.store.close()


@main.command()
def ingest() -> None:
    """Ingest session data from sibling tools."""
    from agent_riggs.assembly import assemble

    project_root = find_project_root()
    service = assemble(project_root)

    ingest_plugin = service.plugin("ingest")
    result = ingest_plugin.run()

    click.echo(f"Ingested {result.turns_ingested} turns from {result.sources_read}")
    if result.failures_recorded:
        click.echo(f"Recorded {result.failures_recorded} failures")

    service.store.close()


@main.command()
def status() -> None:
    """Show trust scores, mode, and ratchet summary."""
    from agent_riggs.assembly import assemble

    project_root = find_project_root()
    service = assemble(project_root)

    trust_plugin = service.plugin("trust")
    data = trust_plugin.current()

    if not data["has_data"]:
        click.echo("trust: no data yet")
        click.echo("\nRun `agent-riggs ingest` after a session.")
    else:
        click.echo(
            f"trust: {data['trust_1']:.2f} / {data['trust_5']:.2f} / {data['trust_15']:.2f}"
        )
        click.echo("       now    session  baseline")

    service.store.close()
```

- [ ] **Step 5: Create stub plugins so assembly works**

We need stub implementations of the remaining plugins so `assemble()` can import them. Create minimal stubs for `ratchet`, `metrics`, `briefing`, and `sandbox` plugins.

Create `src/agent_riggs/plugins/ratchet.py`:

```python
"""Ratchet plugin — stub, implemented in Task 12."""

from __future__ import annotations
from typing import Any, Callable, TYPE_CHECKING
import click

if TYPE_CHECKING:
    from agent_riggs.service import RiggsService

RATCHET_DDL = [
    """
    CREATE TABLE IF NOT EXISTS ratchet_decisions (
        decision_id     BIGINT PRIMARY KEY,
        decided_at      TIMESTAMPTZ NOT NULL,
        candidate_type  VARCHAR NOT NULL,
        candidate_key   VARCHAR NOT NULL,
        decision        VARCHAR NOT NULL,
        reason          VARCHAR,
        evidence        JSON,
        config_change   JSON
    )
    """,
]

class RatchetPlugin:
    name = "ratchet"
    def bind(self, service: RiggsService) -> None:
        self.service = service
    def schema_ddl(self) -> list[str]:
        return list(RATCHET_DDL)
    def cli_commands(self) -> list[click.Command]:
        return []
    def mcp_resources(self) -> list[tuple[str, Callable[..., Any]]]:
        return []
    def mcp_tools(self) -> list[tuple[str, Callable[..., Any]]]:
        return []
```

Create `src/agent_riggs/plugins/metrics.py`:

```python
"""Metrics plugin — stub, implemented in Task 13."""

from __future__ import annotations
from typing import Any, Callable, TYPE_CHECKING
import click

if TYPE_CHECKING:
    from agent_riggs.service import RiggsService

class MetricsPlugin:
    name = "metrics"
    def bind(self, service: RiggsService) -> None:
        self.service = service
    def schema_ddl(self) -> list[str]:
        return []
    def cli_commands(self) -> list[click.Command]:
        return []
    def mcp_resources(self) -> list[tuple[str, Callable[..., Any]]]:
        return []
    def mcp_tools(self) -> list[tuple[str, Callable[..., Any]]]:
        return []
```

Create `src/agent_riggs/plugins/briefing.py`:

```python
"""Briefing plugin — stub, implemented in Task 14."""

from __future__ import annotations
from typing import Any, Callable, TYPE_CHECKING
import click

if TYPE_CHECKING:
    from agent_riggs.service import RiggsService

class BriefingPlugin:
    name = "briefing"
    def bind(self, service: RiggsService) -> None:
        self.service = service
    def schema_ddl(self) -> list[str]:
        return []
    def cli_commands(self) -> list[click.Command]:
        return []
    def mcp_resources(self) -> list[tuple[str, Callable[..., Any]]]:
        return []
    def mcp_tools(self) -> list[tuple[str, Callable[..., Any]]]:
        return []
```

Create `src/agent_riggs/plugins/sandbox.py`:

```python
"""Sandbox plugin — stub, implemented in Task 15."""

from __future__ import annotations
from typing import Any, Callable, TYPE_CHECKING
import click

if TYPE_CHECKING:
    from agent_riggs.service import RiggsService

SANDBOX_DDL = [
    """
    CREATE TABLE IF NOT EXISTS sandbox_profiles (
        command         VARCHAR NOT NULL,
        project         VARCHAR NOT NULL,
        updated_at      TIMESTAMPTZ NOT NULL,
        total_runs      INTEGER,
        memory_p50      BIGINT,
        memory_p95      BIGINT,
        memory_max      BIGINT,
        duration_p50    INTERVAL,
        duration_p95    INTERVAL,
        duration_max    INTERVAL,
        current_spec    JSON,
        current_grade_w VARCHAR,
        current_effects_ceiling INTEGER,
        PRIMARY KEY (command, project)
    )
    """,
]

class SandboxPlugin:
    name = "sandbox"
    def bind(self, service: RiggsService) -> None:
        self.service = service
    def schema_ddl(self) -> list[str]:
        return list(SANDBOX_DDL)
    def cli_commands(self) -> list[click.Command]:
        return []
    def mcp_resources(self) -> list[tuple[str, Callable[..., Any]]]:
        return []
    def mcp_tools(self) -> list[tuple[str, Callable[..., Any]]]:
        return []
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_cli/ -v`
Expected: All passed

Run: `pytest -v`
Expected: All tests pass

- [ ] **Step 7: Verify CLI works end-to-end**

Run (from a temp dir): `cd /tmp && mkdir test-riggs && cd test-riggs && agent-riggs init && agent-riggs status`
Expected: Initializes .riggs/ and shows trust status

- [ ] **Step 8: Commit**

```bash
git add src/agent_riggs/cli.py src/agent_riggs/plugins/ratchet.py src/agent_riggs/plugins/metrics.py src/agent_riggs/plugins/briefing.py src/agent_riggs/plugins/sandbox.py tests/test_cli/
git commit -m "feat: CLI with init, ingest, and status commands"
```

---

## Phase 5: Ratchet

### Task 12: Ratchet Candidates and Aggregation

**Files:**
- Create: `src/agent_riggs/ratchet/__init__.py`
- Create: `src/agent_riggs/ratchet/aggregator.py`
- Create: `src/agent_riggs/ratchet/candidates.py`
- Create: `tests/test_ratchet/__init__.py`
- Create: `tests/test_ratchet/test_candidates.py`
- Modify: `src/agent_riggs/plugins/ratchet.py`

- [ ] **Step 1: Write the failing tests**

```python
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from agent_riggs.config import RatchetConfig, load_config
from agent_riggs.ratchet.candidates import (
    Candidate,
    find_constraint_candidates,
    find_tool_candidates,
)
from agent_riggs.ratchet.aggregator import failure_summary
from agent_riggs.store import Store
from agent_riggs.plugins.trust import TRUST_DDL


def _seed_turns(store: Store, project: str, count: int, tool: str = "Bash",
                category: str = "success", session_count: int = 5,
                metadata_command: str = "grep -rn 'def ' src/") -> None:
    """Seed the turns table with test data."""
    for i in range(count):
        session = f"sess-{i % session_count}"
        store.execute(
            """
            INSERT INTO turns (
                turn_id, session_id, project, turn_number, timestamp,
                tool_name, tool_success, mode, trust_score,
                trust_1, trust_5, trust_15, event_category, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                i + 10000, session, project, i + 1,
                datetime(2026, 3, 29, 10, 0, 0, tzinfo=timezone.utc),
                tool, category != "failure", "implement", 1.0,
                1.0, 1.0, 1.0, category,
                f'{{"command": "{metadata_command}"}}',
            ],
        )


def _seed_failures(store: Store, project: str, count: int,
                   category: str = "edit_failure", tool: str = "Edit",
                   mode: str = "implement", session_count: int = 5) -> None:
    """Seed the failure_stream table with test data."""
    for i in range(count):
        session = f"sess-{i % session_count}"
        store.execute(
            """
            INSERT INTO failure_stream (
                failure_id, turn_id, session_id, project, occurred_at,
                failure_category, tool_name, mode, trust_at_failure, detail
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                i + 20000, i + 10000, session, project,
                datetime(2026, 3, 29, 10, 0, 0, tzinfo=timezone.utc),
                category, tool, mode, 0.5, "{}",
            ],
        )


def test_find_constraint_candidates(tmp_project: Path) -> None:
    db_path = tmp_project / ".riggs" / "store.duckdb"
    config = RatchetConfig(min_frequency=3, min_sessions=2)

    with Store(db_path) as store:
        store.ensure_schema(TRUST_DDL)
        project = tmp_project.name

        _seed_failures(store, project, count=10, session_count=5)

        candidates = find_constraint_candidates(store, project, config)
        assert len(candidates) >= 1
        assert candidates[0].candidate_type == "constraint_promotion"
        assert candidates[0].evidence["occurrences"] == 10


def test_no_candidates_below_threshold(tmp_project: Path) -> None:
    db_path = tmp_project / ".riggs" / "store.duckdb"
    config = RatchetConfig(min_frequency=20, min_sessions=10)

    with Store(db_path) as store:
        store.ensure_schema(TRUST_DDL)
        project = tmp_project.name

        _seed_failures(store, project, count=5, session_count=2)

        candidates = find_constraint_candidates(store, project, config)
        assert len(candidates) == 0


def test_failure_summary(tmp_project: Path) -> None:
    db_path = tmp_project / ".riggs" / "store.duckdb"

    with Store(db_path) as store:
        store.ensure_schema(TRUST_DDL)
        project = tmp_project.name

        _seed_failures(store, project, count=10, category="edit_failure")
        _seed_failures(store, project, count=5, category="path_denial")

        summary = failure_summary(store, project)
        assert len(summary) >= 2
        total = sum(s["count"] for s in summary)
        assert total == 15
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_ratchet/ -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement aggregator.py**

Create `src/agent_riggs/ratchet/__init__.py` (empty).

```python
"""Cross-session failure stream aggregation."""

from __future__ import annotations

from typing import Any

from agent_riggs.store import Store


def failure_summary(
    store: Store, project: str, days: int = 30
) -> list[dict[str, Any]]:
    """Aggregate failures by category for the given project."""
    rows = store.execute(
        """
        SELECT
            failure_category,
            count(*) AS count,
            count(DISTINCT session_id) AS sessions_affected,
            round(avg(trust_at_failure), 2) AS avg_trust
        FROM failure_stream
        WHERE project = ?
          AND occurred_at > current_timestamp - make_interval(days => ?)
        GROUP BY failure_category
        ORDER BY count DESC
        """,
        [project, days],
    ).fetchall()

    return [
        {
            "category": r[0],
            "count": r[1],
            "sessions_affected": r[2],
            "avg_trust": r[3],
        }
        for r in rows
    ]
```

- [ ] **Step 4: Implement candidates.py**

```python
"""Identify ratchet promotion candidates from cross-session data."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent_riggs.config import RatchetConfig
from agent_riggs.store import Store


@dataclass
class Candidate:
    candidate_type: str   # tool_promotion, constraint_promotion, sandbox_tightening
    candidate_key: str
    evidence: dict[str, Any]
    recommendation: str


def find_tool_candidates(
    store: Store, project: str, config: RatchetConfig
) -> list[Candidate]:
    """Find bash patterns that have structured alternatives."""
    rows = store.execute(
        """
        SELECT
            metadata,
            count(*) AS frequency,
            count(DISTINCT session_id) AS sessions,
            round(avg(CASE WHEN tool_success THEN 1.0 ELSE 0.0 END), 2) AS success_rate
        FROM turns
        WHERE project = ?
          AND tool_name = 'Bash'
          AND timestamp > current_timestamp - make_interval(days => ?)
        GROUP BY metadata
        HAVING count(*) >= ?
           AND count(DISTINCT session_id) >= ?
        ORDER BY frequency DESC
        """,
        [project, config.lookback_days, config.min_frequency, config.min_sessions],
    ).fetchall()

    candidates = []
    for row in rows:
        metadata_str = row[0]
        frequency = row[1]
        sessions = row[2]
        success_rate = row[3]

        if success_rate < config.min_success_rate:
            continue

        alternative = _find_alternative(metadata_str)
        if alternative is None:
            continue

        candidates.append(Candidate(
            candidate_type="tool_promotion",
            candidate_key=f"bash-to-{alternative.lower().replace(' ', '-')}",
            evidence={
                "frequency": frequency,
                "sessions": sessions,
                "success_rate": success_rate,
                "command_pattern": metadata_str,
            },
            recommendation=f"Graduate {alternative} interceptor",
        ))

    return candidates


def find_constraint_candidates(
    store: Store, project: str, config: RatchetConfig
) -> list[Candidate]:
    """Find repeated failures at boundaries."""
    rows = store.execute(
        """
        SELECT
            failure_category,
            tool_name,
            mode,
            count(*) AS occurrences,
            count(DISTINCT session_id) AS sessions_affected,
            round(avg(trust_at_failure), 2) AS avg_trust
        FROM failure_stream
        WHERE project = ?
          AND occurred_at > current_timestamp - make_interval(days => ?)
        GROUP BY failure_category, tool_name, mode
        HAVING count(*) >= ?
        ORDER BY occurrences DESC
        """,
        [project, config.lookback_days, config.min_frequency],
    ).fetchall()

    candidates = []
    for row in rows:
        category, tool, mode, occurrences, sessions, avg_trust = row
        severity = (
            "systemic" if sessions >= config.min_sessions
            else "frequent" if occurrences >= config.min_frequency * 2
            else "occasional"
        )
        candidates.append(Candidate(
            candidate_type="constraint_promotion",
            candidate_key=f"{category}-{tool or 'unknown'}-{mode or 'any'}",
            evidence={
                "occurrences": occurrences,
                "sessions_affected": sessions,
                "avg_trust": avg_trust,
                "severity": severity,
            },
            recommendation=_constraint_recommendation(category, tool, mode),
        ))

    return candidates


def _find_alternative(metadata_str: str) -> str | None:
    """Match bash command patterns to structured alternatives."""
    s = metadata_str.lower()
    if "grep" in s and ("def " in s or "class " in s):
        return "FindDefinitions"
    if "pytest" in s:
        return "blq run test"
    if "git add" in s and "git commit" in s:
        return "jetsam save"
    if "git push" in s:
        return "jetsam sync"
    return None


def _constraint_recommendation(category: str, tool: str | None, mode: str | None) -> str:
    """Generate a recommendation string for a constraint candidate."""
    parts = [f"Repeated {category}"]
    if tool:
        parts.append(f"on {tool}")
    if mode:
        parts.append(f"in {mode} mode")
    parts.append("— review configuration or add documentation")
    return " ".join(parts)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_ratchet/ -v`
Expected: All passed

- [ ] **Step 6: Commit**

```bash
git add src/agent_riggs/ratchet/ tests/test_ratchet/
git commit -m "feat: ratchet aggregation and candidate identification"
```

---

### Task 13: Ratchet Promotions and History

**Files:**
- Create: `src/agent_riggs/ratchet/promotions.py`
- Create: `src/agent_riggs/ratchet/history.py`
- Create: `tests/test_ratchet/test_promotions.py`
- Modify: `src/agent_riggs/plugins/ratchet.py`

- [ ] **Step 1: Write the failing tests**

```python
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from agent_riggs.plugins.ratchet import RATCHET_DDL
from agent_riggs.ratchet.candidates import Candidate
from agent_riggs.ratchet.history import get_history
from agent_riggs.ratchet.promotions import record_decision
from agent_riggs.store import Store


def test_record_promote_decision(tmp_project: Path) -> None:
    db_path = tmp_project / ".riggs" / "store.duckdb"
    with Store(db_path) as store:
        store.ensure_schema(RATCHET_DDL)

        candidate = Candidate(
            candidate_type="tool_promotion",
            candidate_key="bash-to-finddefinitions",
            evidence={"frequency": 89, "sessions": 23},
            recommendation="Graduate fledgling interceptor",
        )
        record_decision(store, candidate, decision="promoted", reason="enough evidence")

        row = store.execute("SELECT count(*) FROM ratchet_decisions").fetchone()
        assert row == (1,)


def test_record_reject_decision(tmp_project: Path) -> None:
    db_path = tmp_project / ".riggs" / "store.duckdb"
    with Store(db_path) as store:
        store.ensure_schema(RATCHET_DDL)

        candidate = Candidate(
            candidate_type="tool_promotion",
            candidate_key="bash-to-blq-run-test",
            evidence={"frequency": 10},
            recommendation="Graduate blq interceptor",
        )
        record_decision(store, candidate, decision="rejected", reason="agents need raw pytest output")

        row = store.execute(
            "SELECT decision, reason FROM ratchet_decisions WHERE candidate_key = ?",
            ["bash-to-blq-run-test"],
        ).fetchone()
        assert row[0] == "rejected"
        assert row[1] == "agents need raw pytest output"


def test_get_history(tmp_project: Path) -> None:
    db_path = tmp_project / ".riggs" / "store.duckdb"
    with Store(db_path) as store:
        store.ensure_schema(RATCHET_DDL)

        for i in range(3):
            candidate = Candidate(
                candidate_type="tool_promotion",
                candidate_key=f"key-{i}",
                evidence={},
                recommendation="test",
            )
            record_decision(store, candidate, decision="promoted")

        history = get_history(store)
        assert len(history) == 3
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_ratchet/test_promotions.py -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement promotions.py**

```python
"""Apply and record ratchet promotion decisions."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from agent_riggs.ratchet.candidates import Candidate
from agent_riggs.store import Store

_next_decision_id = 0


def _gen_decision_id() -> int:
    global _next_decision_id
    _next_decision_id += 1
    return _next_decision_id


def record_decision(
    store: Store,
    candidate: Candidate,
    decision: str,
    reason: str | None = None,
    config_change: dict | None = None,
) -> None:
    """Record a promotion/rejection decision in the store."""
    store.execute(
        """
        INSERT INTO ratchet_decisions (
            decision_id, decided_at, candidate_type, candidate_key,
            decision, reason, evidence, config_change
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            _gen_decision_id(),
            datetime.now(timezone.utc),
            candidate.candidate_type,
            candidate.candidate_key,
            decision,
            reason,
            json.dumps(candidate.evidence),
            json.dumps(config_change) if config_change else None,
        ],
    )
```

- [ ] **Step 4: Implement history.py**

```python
"""Ratchet decision history queries."""

from __future__ import annotations

from typing import Any

from agent_riggs.store import Store


def get_history(store: Store, limit: int = 50) -> list[dict[str, Any]]:
    """Get recent ratchet decisions."""
    rows = store.execute(
        """
        SELECT
            decided_at, candidate_type, candidate_key,
            decision, reason, evidence, config_change
        FROM ratchet_decisions
        ORDER BY decided_at DESC
        LIMIT ?
        """,
        [limit],
    ).fetchall()

    return [
        {
            "decided_at": r[0],
            "candidate_type": r[1],
            "candidate_key": r[2],
            "decision": r[3],
            "reason": r[4],
            "evidence": r[5],
            "config_change": r[6],
        }
        for r in rows
    ]
```

- [ ] **Step 5: Update ratchet plugin with full functionality**

Update `src/agent_riggs/plugins/ratchet.py`:

```python
"""Ratchet plugin — candidates, promotions, history."""

from __future__ import annotations

from typing import Any, Callable, TYPE_CHECKING

import click

from agent_riggs.ratchet.aggregator import failure_summary
from agent_riggs.ratchet.candidates import (
    Candidate,
    find_constraint_candidates,
    find_tool_candidates,
)
from agent_riggs.ratchet.history import get_history
from agent_riggs.ratchet.promotions import record_decision

if TYPE_CHECKING:
    from agent_riggs.service import RiggsService


RATCHET_DDL = [
    """
    CREATE TABLE IF NOT EXISTS ratchet_decisions (
        decision_id     BIGINT PRIMARY KEY,
        decided_at      TIMESTAMPTZ NOT NULL,
        candidate_type  VARCHAR NOT NULL,
        candidate_key   VARCHAR NOT NULL,
        decision        VARCHAR NOT NULL,
        reason          VARCHAR,
        evidence        JSON,
        config_change   JSON
    )
    """,
]


class RatchetPlugin:
    name = "ratchet"

    def bind(self, service: RiggsService) -> None:
        self.service = service

    def schema_ddl(self) -> list[str]:
        return list(RATCHET_DDL)

    def cli_commands(self) -> list[click.Command]:
        return []  # Added in CLI task

    def mcp_resources(self) -> list[tuple[str, Callable[..., Any]]]:
        return [("riggs://ratchet", self._ratchet_resource)]

    def mcp_tools(self) -> list[tuple[str, Callable[..., Any]]]:
        return [("RiggsFailures", self._failures_tool)]

    def candidates(self) -> list[Candidate]:
        """Get all ratchet candidates."""
        project = self.service.project_root.name
        config = self.service.config.ratchet
        store = self.service.store

        tool_cands = find_tool_candidates(store, project, config)
        constraint_cands = find_constraint_candidates(store, project, config)
        return tool_cands + constraint_cands

    def promote(self, key: str, reason: str | None = None) -> None:
        """Promote a candidate."""
        candidates = self.candidates()
        for c in candidates:
            if c.candidate_key == key:
                record_decision(self.service.store, c, "promoted", reason)
                return
        raise KeyError(f"No candidate with key: {key}")

    def reject(self, key: str, reason: str) -> None:
        """Reject a candidate with reason."""
        candidates = self.candidates()
        for c in candidates:
            if c.candidate_key == key:
                record_decision(self.service.store, c, "rejected", reason)
                return
        raise KeyError(f"No candidate with key: {key}")

    def history(self) -> list[dict[str, Any]]:
        return get_history(self.service.store)

    def failures(self, category: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        return failure_summary(self.service.store, self.service.project_root.name)

    def _ratchet_resource(self) -> str:
        candidates = self.candidates()
        if not candidates:
            return "No ratchet candidates pending."
        lines = ["RATCHET CANDIDATES\n"]
        for c in candidates:
            lines.append(f"  [{c.candidate_type}] {c.candidate_key}")
            lines.append(f"    {c.recommendation}")
            lines.append(f"    Evidence: {c.evidence}\n")
        return "\n".join(lines)

    def _failures_tool(
        self, category: str | None = None, limit: int = 20
    ) -> dict[str, Any]:
        return {"failures": self.failures(category, limit)}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_ratchet/ -v`
Expected: All passed

- [ ] **Step 7: Commit**

```bash
git add src/agent_riggs/ratchet/ src/agent_riggs/plugins/ratchet.py tests/test_ratchet/
git commit -m "feat: ratchet promotions, history, and full plugin"
```

---

## Phase 6: Metrics

### Task 14: Metrics Compute and Trends

**Files:**
- Create: `src/agent_riggs/metrics/__init__.py`
- Create: `src/agent_riggs/metrics/compute.py`
- Create: `src/agent_riggs/metrics/trends.py`
- Create: `tests/test_metrics/__init__.py`
- Create: `tests/test_metrics/test_compute.py`
- Create: `tests/test_metrics/test_trends.py`
- Modify: `src/agent_riggs/plugins/metrics.py`

- [ ] **Step 1: Write the failing tests for compute**

```python
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from agent_riggs.metrics.compute import RatchetMetrics, compute_metrics
from agent_riggs.plugins.ratchet import RATCHET_DDL
from agent_riggs.plugins.trust import TRUST_DDL
from agent_riggs.store import Store


def _seed_session_data(store: Store, project: str) -> None:
    """Seed turns and session summaries for metrics testing."""
    # 20 turns across 3 sessions
    for i in range(20):
        session = f"sess-{i % 3}"
        store.execute(
            """
            INSERT INTO turns (
                turn_id, session_id, project, turn_number, timestamp,
                tool_name, tool_success, mode, trust_score,
                trust_1, trust_5, trust_15, event_category, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                i + 30000, session, project, i + 1,
                datetime(2026, 3, 29, 10, i, 0, tzinfo=timezone.utc),
                "Read" if i % 3 != 0 else "Bash", True, "implement",
                1.0 if i % 3 != 0 else 0.7,
                0.9, 0.85, 0.87,
                "success" if i % 3 != 0 else "suboptimal",
                "{}",
            ],
        )

    # 3 session summaries
    for i in range(3):
        store.execute(
            """
            INSERT INTO session_summaries (
                session_id, project, total_turns, total_failures,
                failure_rate, trust_start, trust_end, trust_delta,
                modes_used, mode_switches,
                computation_channel_fraction, structured_tool_fraction
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                f"sess-{i}", project, 7, 1, 0.14,
                0.85, 0.90, 0.05,
                ["implement", "debug"], 1,
                0.35, 0.65,
            ],
        )


def test_compute_metrics(tmp_project: Path) -> None:
    db_path = tmp_project / ".riggs" / "store.duckdb"
    with Store(db_path) as store:
        store.ensure_schema(TRUST_DDL + RATCHET_DDL)
        project = tmp_project.name

        _seed_session_data(store, project)

        metrics = compute_metrics(store, project, period_days=30)
        assert isinstance(metrics, RatchetMetrics)
        assert metrics.total_sessions == 3
        assert metrics.total_turns == 20
        assert 0 <= metrics.structured_tool_fraction <= 1


def test_compute_metrics_empty_store(tmp_project: Path) -> None:
    db_path = tmp_project / ".riggs" / "store.duckdb"
    with Store(db_path) as store:
        store.ensure_schema(TRUST_DDL + RATCHET_DDL)
        project = tmp_project.name

        metrics = compute_metrics(store, project, period_days=30)
        assert metrics.total_sessions == 0
        assert metrics.total_turns == 0
```

- [ ] **Step 2: Write the failing tests for trends**

```python
from __future__ import annotations

from agent_riggs.metrics.trends import Trend, detect_trends


def test_detect_improving_trend() -> None:
    current = {"structured_tool_fraction": 0.72}
    previous = {"structured_tool_fraction": 0.58}
    trends = detect_trends(current, previous)
    assert any(t.metric == "structured_tool_fraction" and t.direction == "improving" for t in trends)


def test_detect_declining_trend() -> None:
    current = {"structured_tool_fraction": 0.40}
    previous = {"structured_tool_fraction": 0.60}
    trends = detect_trends(current, previous)
    assert any(t.metric == "structured_tool_fraction" and t.direction == "declining" for t in trends)


def test_no_trend_when_stable() -> None:
    current = {"structured_tool_fraction": 0.71}
    previous = {"structured_tool_fraction": 0.70}
    trends = detect_trends(current, previous)
    assert len(trends) == 0
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_metrics/ -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 4: Implement compute.py**

Create `src/agent_riggs/metrics/__init__.py` (empty).

```python
"""Ratchet metrics computation from the store."""

from __future__ import annotations

from dataclasses import dataclass

from agent_riggs.store import Store


@dataclass
class RatchetMetrics:
    total_sessions: int
    total_turns: int
    total_failures: int
    failure_rate: float
    ratchet_velocity: int
    structured_tool_fraction: float
    computation_channel_fraction: float
    trust_trajectory_start: float
    trust_trajectory_end: float
    mode_distribution: dict[str, float]


def compute_metrics(store: Store, project: str, period_days: int = 30) -> RatchetMetrics:
    """Compute ratchet metrics from the store."""
    # Session-level aggregates
    session_row = store.execute(
        """
        SELECT
            count(*) AS sessions,
            coalesce(sum(total_turns), 0) AS turns,
            coalesce(sum(total_failures), 0) AS failures,
            coalesce(avg(structured_tool_fraction), 0) AS structured_frac,
            coalesce(avg(computation_channel_fraction), 0) AS compute_frac
        FROM session_summaries
        WHERE project = ?
        """,
        [project],
    ).fetchone()

    total_sessions = session_row[0]
    total_turns = session_row[1]
    total_failures = session_row[2]
    structured_frac = session_row[3]
    compute_frac = session_row[4]

    failure_rate = total_failures / total_turns if total_turns > 0 else 0.0

    # Trust trajectory
    trust_row = store.execute(
        """
        SELECT
            first(trust_5 ORDER BY timestamp ASC) AS trust_start,
            last(trust_5 ORDER BY timestamp ASC) AS trust_end
        FROM turns
        WHERE project = ?
        """,
        [project],
    ).fetchone()

    trust_start = trust_row[0] if trust_row and trust_row[0] is not None else 1.0
    trust_end = trust_row[1] if trust_row and trust_row[1] is not None else 1.0

    # Ratchet velocity (promotions in period)
    ratchet_row = store.execute(
        """
        SELECT count(*)
        FROM ratchet_decisions
        WHERE decision = 'promoted'
          AND decided_at > current_timestamp - make_interval(days => ?)
        """,
        [period_days],
    ).fetchone()
    ratchet_velocity = ratchet_row[0] if ratchet_row else 0

    # Mode distribution from turns
    mode_rows = store.execute(
        """
        SELECT mode, count(*) AS cnt
        FROM turns
        WHERE project = ?
          AND mode IS NOT NULL
        GROUP BY mode
        """,
        [project],
    ).fetchall()

    total_mode_turns = sum(r[1] for r in mode_rows) if mode_rows else 1
    mode_distribution = {r[0]: r[1] / total_mode_turns for r in mode_rows} if mode_rows else {}

    return RatchetMetrics(
        total_sessions=total_sessions,
        total_turns=total_turns,
        total_failures=total_failures,
        failure_rate=failure_rate,
        ratchet_velocity=ratchet_velocity,
        structured_tool_fraction=structured_frac,
        computation_channel_fraction=compute_frac,
        trust_trajectory_start=trust_start,
        trust_trajectory_end=trust_end,
        mode_distribution=mode_distribution,
    )
```

- [ ] **Step 5: Implement trends.py**

```python
"""Trend detection over configurable windows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Minimum absolute change to count as a trend
_SIGNIFICANCE_THRESHOLD = 0.05


@dataclass
class Trend:
    metric: str
    direction: str  # "improving" or "declining"
    current: float
    previous: float
    delta: float


_IMPROVING_DIRECTION: dict[str, str] = {
    "structured_tool_fraction": "up",
    "computation_channel_fraction": "down",
    "failure_rate": "down",
    "trust_trajectory_end": "up",
}


def detect_trends(
    current: dict[str, Any],
    previous: dict[str, Any],
    threshold: float = _SIGNIFICANCE_THRESHOLD,
) -> list[Trend]:
    """Compare current and previous period metrics, return significant trends."""
    trends: list[Trend] = []
    for metric, good_direction in _IMPROVING_DIRECTION.items():
        cur = current.get(metric)
        prev = previous.get(metric)
        if cur is None or prev is None:
            continue
        delta = cur - prev
        if abs(delta) < threshold:
            continue

        if good_direction == "up":
            direction = "improving" if delta > 0 else "declining"
        else:
            direction = "improving" if delta < 0 else "declining"

        trends.append(Trend(
            metric=metric,
            direction=direction,
            current=cur,
            previous=prev,
            delta=delta,
        ))

    return trends
```

- [ ] **Step 6: Update metrics plugin**

```python
"""Metrics plugin — ratchet velocity, self-service ratio, trends."""

from __future__ import annotations

from typing import Any, Callable, TYPE_CHECKING

import click

from agent_riggs.metrics.compute import RatchetMetrics, compute_metrics

if TYPE_CHECKING:
    from agent_riggs.service import RiggsService


class MetricsPlugin:
    name = "metrics"

    def bind(self, service: RiggsService) -> None:
        self.service = service

    def schema_ddl(self) -> list[str]:
        return []

    def cli_commands(self) -> list[click.Command]:
        return []

    def mcp_resources(self) -> list[tuple[str, Callable[..., Any]]]:
        return [("riggs://metrics", self._metrics_resource)]

    def mcp_tools(self) -> list[tuple[str, Callable[..., Any]]]:
        return [("RiggsMetrics", self._metrics_tool)]

    def compute(self, period_days: int | None = None) -> RatchetMetrics:
        period = period_days or self.service.config.metrics.default_period_days
        return compute_metrics(self.service.store, self.service.project_root.name, period)

    def _metrics_resource(self) -> str:
        m = self.compute()
        return (
            f"RATCHET METRICS (last {self.service.config.metrics.default_period_days} days, "
            f"{m.total_sessions} sessions)\n\n"
            f"  Ratchet velocity:        {m.ratchet_velocity} promotions\n"
            f"  Self-service ratio:      {m.structured_tool_fraction:.0%} structured\n"
            f"  Computation channel %:   {m.computation_channel_fraction:.0%}\n"
            f"  Trust trajectory:        {m.trust_trajectory_start:.2f} -> "
            f"{m.trust_trajectory_end:.2f}\n"
            f"  Failure rate:            {m.failure_rate:.0%}\n"
        )

    def _metrics_tool(self, period: int | None = None) -> dict[str, Any]:
        m = self.compute(period)
        return {
            "total_sessions": m.total_sessions,
            "total_turns": m.total_turns,
            "ratchet_velocity": m.ratchet_velocity,
            "structured_tool_fraction": m.structured_tool_fraction,
            "computation_channel_fraction": m.computation_channel_fraction,
            "trust_trajectory": [m.trust_trajectory_start, m.trust_trajectory_end],
            "failure_rate": m.failure_rate,
            "mode_distribution": m.mode_distribution,
        }
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/test_metrics/ -v`
Expected: All passed

- [ ] **Step 8: Commit**

```bash
git add src/agent_riggs/metrics/ src/agent_riggs/plugins/metrics.py tests/test_metrics/
git commit -m "feat: ratchet metrics computation and trend detection"
```

---

## Phase 7: Briefing

### Task 15: Session Briefing

**Files:**
- Create: `src/agent_riggs/briefing/__init__.py`
- Create: `src/agent_riggs/briefing/session.py`
- Create: `src/agent_riggs/briefing/project.py`
- Create: `tests/test_briefing/__init__.py`
- Create: `tests/test_briefing/test_session.py`
- Modify: `src/agent_riggs/plugins/briefing.py`

- [ ] **Step 1: Write the failing tests**

```python
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from agent_riggs.briefing.session import SessionBriefing, generate_briefing
from agent_riggs.config import load_config
from agent_riggs.plugins.ratchet import RATCHET_DDL
from agent_riggs.plugins.trust import TRUST_DDL
from agent_riggs.store import Store


def test_briefing_no_data(tmp_project: Path) -> None:
    db_path = tmp_project / ".riggs" / "store.duckdb"
    config = load_config(tmp_project)
    with Store(db_path) as store:
        store.ensure_schema(TRUST_DDL + RATCHET_DDL)
        briefing = generate_briefing(store, tmp_project.name, config)
        assert isinstance(briefing, SessionBriefing)
        assert briefing.trust_baseline is None
        assert briefing.last_session is None


def test_briefing_with_data(tmp_project: Path) -> None:
    db_path = tmp_project / ".riggs" / "store.duckdb"
    config = load_config(tmp_project)
    with Store(db_path) as store:
        store.ensure_schema(TRUST_DDL + RATCHET_DDL)

        # Seed a session summary
        store.execute(
            """
            INSERT INTO session_summaries (
                session_id, project, started_at, ended_at,
                total_turns, total_failures, failure_rate,
                trust_start, trust_end, trust_delta,
                modes_used, mode_switches,
                computation_channel_fraction, structured_tool_fraction
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                "sess-1", tmp_project.name,
                datetime(2026, 3, 29, 8, 0, tzinfo=timezone.utc),
                datetime(2026, 3, 29, 10, 0, tzinfo=timezone.utc),
                34, 2, 0.06, 0.85, 0.91, 0.06,
                ["implement"], 0, 0.3, 0.7,
            ],
        )

        # Seed a trust turn for baseline
        store.execute(
            """
            INSERT INTO turns (
                turn_id, session_id, project, turn_number, timestamp,
                tool_name, tool_success, mode, trust_score,
                trust_1, trust_5, trust_15, event_category, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                50000, "sess-1", tmp_project.name, 34,
                datetime(2026, 3, 29, 10, 0, tzinfo=timezone.utc),
                "Read", True, "implement", 1.0,
                0.91, 0.88, 0.87, "success", "{}",
            ],
        )

        briefing = generate_briefing(store, tmp_project.name, config)
        assert briefing.trust_baseline == 0.87
        assert briefing.last_session is not None
        assert briefing.last_session["session_id"] == "sess-1"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_briefing/ -v`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement session.py**

Create `src/agent_riggs/briefing/__init__.py` (empty).

```python
"""Generate session briefings from cross-session data."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from agent_riggs.config import RiggsConfig
from agent_riggs.store import Store


@dataclass
class SessionBriefing:
    trust_baseline: float | None
    last_session: dict[str, Any] | None
    known_issues: list[str]
    active_candidates: int

    def format(self) -> str:
        """Format as human-readable text."""
        lines: list[str] = []

        if self.trust_baseline is not None:
            lines.append(f"Trust baseline: {self.trust_baseline:.2f}")
        else:
            lines.append("Trust baseline: no data")

        if self.last_session:
            s = self.last_session
            lines.append(
                f"Last session: {s['session_id']}, "
                f"{s['total_turns']} turns, trust {s['trust_end']:.2f}"
            )
        else:
            lines.append("Last session: none")

        if self.known_issues:
            lines.append("\nKnown issues:")
            for issue in self.known_issues:
                lines.append(f"  - {issue}")

        if self.active_candidates > 0:
            lines.append(f"\nActive ratchet candidates: {self.active_candidates}")

        return "\n".join(lines)


def generate_briefing(
    store: Store, project: str, config: RiggsConfig
) -> SessionBriefing:
    """Generate a session briefing from cross-session data."""
    # Trust baseline (trust_15 from most recent turn)
    trust_row = store.execute(
        """
        SELECT trust_15
        FROM turns
        WHERE project = ?
        ORDER BY timestamp DESC
        LIMIT 1
        """,
        [project],
    ).fetchone()
    trust_baseline = trust_row[0] if trust_row else None

    # Last session
    session_row = store.execute(
        """
        SELECT session_id, total_turns, total_failures, trust_end, ended_at
        FROM session_summaries
        WHERE project = ?
        ORDER BY ended_at DESC
        LIMIT 1
        """,
        [project],
    ).fetchone()
    last_session = None
    if session_row:
        last_session = {
            "session_id": session_row[0],
            "total_turns": session_row[1],
            "total_failures": session_row[2],
            "trust_end": session_row[3],
            "ended_at": session_row[4],
        }

    # Known issues (top failure patterns)
    failure_rows = store.execute(
        """
        SELECT failure_category, count(*) AS cnt
        FROM failure_stream
        WHERE project = ?
        GROUP BY failure_category
        HAVING count(*) >= 3
        ORDER BY cnt DESC
        LIMIT 5
        """,
        [project],
    ).fetchall()
    known_issues = [f"{r[0]} ({r[1]} occurrences)" for r in failure_rows]

    # Active ratchet candidates count
    # (simple: count failures meeting ratchet thresholds)
    candidate_row = store.execute(
        """
        SELECT count(DISTINCT failure_category || coalesce(tool_name, '') || coalesce(mode, ''))
        FROM failure_stream
        WHERE project = ?
        GROUP BY project
        HAVING count(*) >= ?
        """,
        [project, config.ratchet.min_frequency],
    ).fetchone()
    active_candidates = candidate_row[0] if candidate_row else 0

    return SessionBriefing(
        trust_baseline=trust_baseline,
        last_session=last_session,
        known_issues=known_issues,
        active_candidates=active_candidates,
    )
```

- [ ] **Step 4: Create project.py**

```python
"""Project-level health assessment."""

from __future__ import annotations

from typing import Any

from agent_riggs.store import Store


def project_health(store: Store, project: str) -> dict[str, Any]:
    """Compute project-level health metrics."""
    row = store.execute(
        """
        SELECT
            count(*) AS sessions,
            coalesce(avg(trust_end), 1.0) AS avg_trust,
            coalesce(avg(failure_rate), 0.0) AS avg_failure_rate
        FROM session_summaries
        WHERE project = ?
        """,
        [project],
    ).fetchone()

    return {
        "total_sessions": row[0],
        "avg_trust": row[1],
        "avg_failure_rate": row[2],
        "healthy": row[1] >= 0.7 and row[2] <= 0.3,
    }
```

- [ ] **Step 5: Update briefing plugin**

```python
"""Briefing plugin — session and project briefings."""

from __future__ import annotations

from typing import Any, Callable, TYPE_CHECKING

import click

from agent_riggs.briefing.session import SessionBriefing, generate_briefing

if TYPE_CHECKING:
    from agent_riggs.service import RiggsService


class BriefingPlugin:
    name = "briefing"

    def bind(self, service: RiggsService) -> None:
        self.service = service

    def schema_ddl(self) -> list[str]:
        return []

    def cli_commands(self) -> list[click.Command]:
        return []

    def mcp_resources(self) -> list[tuple[str, Callable[..., Any]]]:
        return [("riggs://briefing", self._briefing_resource)]

    def mcp_tools(self) -> list[tuple[str, Callable[..., Any]]]:
        return []

    def brief(self) -> SessionBriefing:
        return generate_briefing(
            self.service.store,
            self.service.project_root.name,
            self.service.config,
        )

    def _briefing_resource(self) -> str:
        return self.brief().format()
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `pytest tests/test_briefing/ -v`
Expected: All passed

- [ ] **Step 7: Commit**

```bash
git add src/agent_riggs/briefing/ src/agent_riggs/plugins/briefing.py tests/test_briefing/
git commit -m "feat: session briefing and project health assessment"
```

---

## Phase 8: Sandbox Stubs

### Task 15.5: Sandbox Module Stubs

**Files:**
- Create: `src/agent_riggs/sandbox/__init__.py`
- Create: `src/agent_riggs/sandbox/grades.py`
- Create: `src/agent_riggs/sandbox/recommendations.py`
- Create: `src/agent_riggs/sandbox/integration.py`

These are stubs for when blq is available. The sandbox plugin (already created as a stub in Task 11) will delegate to these modules.

- [ ] **Step 1: Create stub sandbox modules**

Create `src/agent_riggs/sandbox/__init__.py` (empty).

Create `src/agent_riggs/sandbox/grades.py`:

```python
"""Read blq sandbox grades and aggregate across sessions. Stub — requires blq."""

from __future__ import annotations

from typing import Any

from agent_riggs.store import Store


def get_grades(store: Store, project: str) -> list[dict[str, Any]]:
    """Query sandbox_profiles table. Returns empty if no data."""
    rows = store.execute(
        """
        SELECT command, current_grade_w, current_effects_ceiling,
               total_runs, memory_p95, memory_max
        FROM sandbox_profiles
        WHERE project = ?
        ORDER BY command
        """,
        [project],
    ).fetchall()
    return [
        {
            "command": r[0], "grade": r[1], "effects_ceiling": r[2],
            "runs": r[3], "memory_p95": r[4], "memory_max": r[5],
        }
        for r in rows
    ]
```

Create `src/agent_riggs/sandbox/recommendations.py`:

```python
"""Sandbox tightening recommendations. Stub — requires blq."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent_riggs.config import SandboxConfig


@dataclass
class SandboxRecommendation:
    command: str
    metric: str
    current: int
    suggested: int
    reason: str


def recommend_tightening(
    grades: list[dict[str, Any]], config: SandboxConfig
) -> list[SandboxRecommendation]:
    """Recommend tightening based on headroom. Returns empty if no grades."""
    return []  # Requires blq integration for meaningful recommendations
```

Create `src/agent_riggs/sandbox/integration.py`:

```python
"""Bridge to blq sandbox commands. Stub — requires blq."""

from __future__ import annotations

import subprocess


def profile_command(command: str) -> str:
    """Delegate to blq sandbox profile. Requires blq on PATH."""
    result = subprocess.run(
        ["blq", "sandbox", "profile", command],
        capture_output=True, text=True,
    )
    return result.stdout


def apply_recommendation(command: str) -> str:
    """Delegate to blq sandbox tighten. Requires blq on PATH."""
    result = subprocess.run(
        ["blq", "sandbox", "tighten", command],
        capture_output=True, text=True,
    )
    return result.stdout
```

- [ ] **Step 2: Commit**

```bash
git add src/agent_riggs/sandbox/
git commit -m "feat: sandbox module stubs for blq integration"
```

---

### Task 16: MCP Server

**Files:**
- Create: `src/agent_riggs/mcp/__init__.py`
- Create: `src/agent_riggs/mcp/server.py`

- [ ] **Step 1: Implement the MCP server**

Create `src/agent_riggs/mcp/__init__.py` (empty).

```python
"""MCP server for agent-riggs — auto-discovers resources and tools from plugins."""

from __future__ import annotations

from pathlib import Path

from mcp.server import Server

from agent_riggs.assembly import assemble


def create_server(project_root: Path | None = None) -> Server:
    """Create an MCP server with all plugin resources and tools registered."""
    if project_root is None:
        project_root = Path.cwd()

    service = assemble(project_root, read_only=True)
    server = Server("agent-riggs")

    # Register resources from all plugins
    for plugin in service.plugins.values():
        for uri, handler in plugin.mcp_resources():
            server.read_resource(uri)(handler)

    # Register tools from all plugins
    for plugin in service.plugins.values():
        for name, handler in plugin.mcp_tools():
            server.call_tool(name)(handler)

    return server
```

- [ ] **Step 2: Verify it imports cleanly**

Run: `python -c "from agent_riggs.mcp.server import create_server; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/agent_riggs/mcp/
git commit -m "feat: MCP server with auto-discovered plugin resources and tools"
```

---

## Phase 9: Remaining CLI Commands

### Task 17: Full CLI Command Set

**Files:**
- Modify: `src/agent_riggs/cli.py`

- [ ] **Step 1: Add trust, ratchet, metrics, brief, and sandbox commands to cli.py**

Add the following to `cli.py` after the existing commands:

```python
# --- Trust commands ---

@main.group("trust")
def trust_group() -> None:
    """Trust score commands."""


@trust_group.command("current")
def trust_current() -> None:
    """Show current trust scores."""
    from agent_riggs.assembly import assemble
    service = assemble(find_project_root())
    data = service.plugin("trust").current()
    if not data["has_data"]:
        click.echo("No trust data yet.")
    else:
        click.echo(f"trust_1 (now):      {data['trust_1']:.4f}")
        click.echo(f"trust_5 (session):  {data['trust_5']:.4f}")
        click.echo(f"trust_15 (baseline):{data['trust_15']:.4f}")
    service.store.close()


@trust_group.command("history")
@click.option("--limit", default=20, help="Number of entries")
def trust_history(limit: int) -> None:
    """Show trust score history."""
    from agent_riggs.assembly import assemble
    service = assemble(find_project_root())
    history = service.plugin("trust").history(limit=limit)
    if not history:
        click.echo("No trust history.")
    else:
        for entry in history:
            click.echo(
                f"  [{entry['session_id']}:{entry['turn_number']}] "
                f"{entry['trust_1']:.2f} / {entry['trust_5']:.2f} / {entry['trust_15']:.2f}"
            )
    service.store.close()


# --- Ratchet commands ---

@main.group("ratchet")
def ratchet_group() -> None:
    """Ratchet candidate commands."""


@ratchet_group.command("candidates")
def ratchet_candidates() -> None:
    """Show pending ratchet candidates."""
    from agent_riggs.assembly import assemble
    service = assemble(find_project_root())
    candidates = service.plugin("ratchet").candidates()
    if not candidates:
        click.echo("No ratchet candidates.")
    else:
        for c in candidates:
            click.echo(f"\n  [{c.candidate_type}] {c.candidate_key}")
            click.echo(f"    {c.recommendation}")
            click.echo(f"    Evidence: {c.evidence}")
    service.store.close()


@ratchet_group.command("promote")
@click.argument("key")
@click.option("--reason", default=None, help="Reason for promotion")
def ratchet_promote(key: str, reason: str | None) -> None:
    """Promote a ratchet candidate."""
    from agent_riggs.assembly import assemble
    service = assemble(find_project_root())
    try:
        service.plugin("ratchet").promote(key, reason)
        click.echo(f"Promoted: {key}")
    except KeyError:
        click.echo(f"No candidate with key: {key}", err=True)
    service.store.close()


@ratchet_group.command("reject")
@click.argument("key")
@click.option("--reason", required=True, help="Reason for rejection")
def ratchet_reject(key: str, reason: str) -> None:
    """Reject a ratchet candidate with reason."""
    from agent_riggs.assembly import assemble
    service = assemble(find_project_root())
    try:
        service.plugin("ratchet").reject(key, reason)
        click.echo(f"Rejected: {key}")
    except KeyError:
        click.echo(f"No candidate with key: {key}", err=True)
    service.store.close()


@ratchet_group.command("history")
def ratchet_history() -> None:
    """Show ratchet decision history."""
    from agent_riggs.assembly import assemble
    service = assemble(find_project_root())
    history = service.plugin("ratchet").history()
    if not history:
        click.echo("No ratchet decisions recorded.")
    else:
        for h in history:
            click.echo(
                f"  [{h['decided_at']}] {h['decision']}: "
                f"{h['candidate_key']} — {h.get('reason', '')}"
            )
    service.store.close()


# --- Metrics command ---

@main.command("metrics")
@click.option("--period", default=None, type=int, help="Period in days")
def metrics_cmd(period: int | None) -> None:
    """Show ratchet metrics dashboard."""
    from agent_riggs.assembly import assemble
    service = assemble(find_project_root())
    m = service.plugin("metrics").compute(period)
    click.echo(f"RATCHET METRICS ({m.total_sessions} sessions)\n")
    click.echo(f"  Ratchet velocity:        {m.ratchet_velocity} promotions")
    click.echo(f"  Self-service ratio:      {m.structured_tool_fraction:.0%} structured")
    click.echo(f"  Computation channel %:   {m.computation_channel_fraction:.0%}")
    click.echo(
        f"  Trust trajectory:        {m.trust_trajectory_start:.2f} -> "
        f"{m.trust_trajectory_end:.2f}"
    )
    click.echo(f"  Failure rate:            {m.failure_rate:.0%}")
    if m.mode_distribution:
        click.echo(f"\n  Mode distribution:")
        for mode, frac in sorted(m.mode_distribution.items(), key=lambda x: -x[1]):
            click.echo(f"    {mode}: {frac:.0%}")
    service.store.close()


# --- Brief command ---

@main.command("brief")
def brief_cmd() -> None:
    """Full session briefing."""
    from agent_riggs.assembly import assemble
    service = assemble(find_project_root())
    briefing = service.plugin("briefing").brief()
    click.echo(f"PROJECT BRIEFING: {find_project_root().name}\n")
    click.echo(briefing.format())
    service.store.close()
```

- [ ] **Step 2: Run full test suite**

Run: `pytest -v`
Expected: All tests pass

- [ ] **Step 3: Verify CLI commands**

Run: `agent-riggs --help`
Expected: Shows all commands: init, ingest, status, trust, ratchet, metrics, brief

Run: `agent-riggs trust --help`
Expected: Shows trust subcommands: current, history

Run: `agent-riggs ratchet --help`
Expected: Shows ratchet subcommands: candidates, promote, reject, history

- [ ] **Step 4: Commit**

```bash
git add src/agent_riggs/cli.py
git commit -m "feat: complete CLI with trust, ratchet, metrics, and brief commands"
```

---

## Phase 10: Remaining CLI and Polish

### Task 18: README and Final Integration Test

**Files:**
- The README.md provided by the user should be placed at the project root
- Run a full integration test

- [ ] **Step 1: Copy the README.md to the project root**

Copy the user's provided README content to `README.md`.

- [ ] **Step 2: Run the full test suite**

Run: `pytest -v --tb=short`
Expected: All tests pass

- [ ] **Step 3: Run ruff linting**

Run: `ruff check src/ tests/`
Expected: No errors (or fix any that appear)

- [ ] **Step 4: Verify end-to-end workflow**

```bash
cd /tmp && rm -rf e2e-riggs && mkdir e2e-riggs && cd e2e-riggs
agent-riggs init
agent-riggs status
agent-riggs trust current
agent-riggs metrics
agent-riggs brief
agent-riggs ratchet candidates
```

Expected: All commands run without error, showing appropriate "no data" messages.

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "docs: add README"
```

---

## Summary

| Phase | Tasks | What it produces |
|-------|-------|-----------------|
| 1. Foundation | 1-4 | Scaffolding, config, store, plugin protocol, service, assembly |
| 2. Trust Engine | 5-8 | Events, scorer, EWMA, transitions, trust plugin |
| 3. Ingest | 9-10 | Source protocol, kibitzer source, pipeline, ingest plugin |
| 4. CLI MVP | 11 | init, ingest, status commands + stub plugins |
| 5. Ratchet | 12-13 | Aggregation, candidates, promotions, history, ratchet plugin |
| 6. Metrics | 14 | Compute, trends, metrics plugin |
| 7. Briefing | 15 | Session briefing, project health, briefing plugin |
| 8. MCP | 16 | MCP server with auto-discovered resources/tools |
| 9. CLI | 17 | Full CLI command set |
| 10. Polish | 18 | README, linting, integration test |

After Phase 4 (Task 11), you have a working `agent-riggs init && agent-riggs ingest && agent-riggs status` flow. Every subsequent phase adds capabilities incrementally.
