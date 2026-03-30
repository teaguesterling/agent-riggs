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
