"""Fledgling ingest source — reads Claude Code conversation JSONL logs."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from agent_riggs.trust.events import EventCategory, TurnEvent

# Tools that have structured alternatives (from kibitzer's interceptor patterns)
_BASH_PATTERNS_WITH_ALTERNATIVES = {
    "grep": "Grep/FindDefinitions",
    "find": "Glob",
    "cat": "Read",
    "head": "Read",
    "tail": "Read",
    "sed": "Edit",
    "awk": "Edit",
}


class FledglingSource:
    name = "fledgling"

    def discover(self, project_root: Path) -> bool:
        claude_dir = Path.home() / ".claude" / "projects"
        if not claude_dir.exists():
            return False
        # Check if any project dir has JSONL files
        for project_dir in claude_dir.iterdir():
            if project_dir.is_dir():
                for f in project_dir.glob("*.jsonl"):
                    return True
        return False

    def read_events(self, project_root: Path, since: datetime | None) -> list[TurnEvent]:
        jsonl_files = self._find_project_logs(project_root)
        if not jsonl_files:
            return []

        events: list[TurnEvent] = []
        turn_counter = 0
        for jsonl_path in jsonl_files:
            with jsonl_path.open() as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        continue

                    if record.get("type") != "assistant":
                        continue

                    message = record.get("message", {})
                    content = message.get("content", [])
                    if not isinstance(content, list):
                        continue

                    session_id = record.get("sessionId", "unknown")
                    ts = self._parse_timestamp(record.get("timestamp", ""))
                    if since and ts < since:
                        continue

                    for block in content:
                        if not isinstance(block, dict):
                            continue
                        if block.get("type") != "tool_use":
                            continue

                        turn_counter += 1
                        tool_name = block.get("name", "unknown")
                        tool_input = block.get("input", {})
                        category = self._classify(tool_name, tool_input)
                        events.append(
                            TurnEvent(
                                session_id=session_id,
                                turn_number=turn_counter,
                                timestamp=ts,
                                tool_name=tool_name,
                                tool_success=True,
                                mode=None,
                                event_category=category,
                                metadata={
                                    "tool_input": tool_input,
                                    "model": message.get("model"),
                                    "source": "fledgling",
                                },
                            )
                        )

        return events

    def _find_project_logs(self, project_root: Path) -> list[Path]:
        """Find JSONL files that belong to this project."""
        claude_dir = Path.home() / ".claude" / "projects"
        if not claude_dir.exists():
            return []

        project_str = str(project_root)
        matches: list[Path] = []

        for project_dir in claude_dir.iterdir():
            if not project_dir.is_dir():
                continue
            # Check first JSONL for cwd match
            for jsonl_path in sorted(project_dir.glob("*.jsonl")):
                if self._jsonl_matches_project(jsonl_path, project_str):
                    matches.extend(sorted(project_dir.glob("*.jsonl")))
                    break

        return matches

    def _jsonl_matches_project(self, jsonl_path: Path, project_str: str) -> bool:
        """Check if a JSONL file's cwd matches the project root."""
        with jsonl_path.open() as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue
                cwd = record.get("cwd", "")
                if cwd and project_str in cwd:
                    return True
                # Only check first few records
                if record.get("type") == "assistant":
                    break
        return False

    def _classify(self, tool_name: str, tool_input: dict) -> EventCategory:
        if tool_name == "Bash":
            cmd = tool_input.get("command", "")
            first_word = cmd.split()[0] if cmd.split() else ""
            if first_word in _BASH_PATTERNS_WITH_ALTERNATIVES:
                return EventCategory.SUBOPTIMAL
        return EventCategory.SUCCESS

    def _parse_timestamp(self, ts_str: str) -> datetime:
        if not ts_str:
            return datetime.now(UTC)
        ts_str = ts_str.replace("Z", "+00:00")
        # Handle millisecond timestamps
        if "." in ts_str and "+" in ts_str:
            # Trim excess precision before timezone
            parts = ts_str.split("+")
            base = parts[0]
            tz = parts[1]
            if "." in base:
                date_part, frac = base.split(".")
                frac = frac[:6]  # Max 6 digits for microseconds
                ts_str = f"{date_part}.{frac}+{tz}"
        return datetime.fromisoformat(ts_str)
