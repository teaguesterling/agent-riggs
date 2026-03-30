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
