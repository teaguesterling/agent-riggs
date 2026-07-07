"""Append-only, HMAC-chained trust ledger.

The ledger is the authoritative record of trust state. It addresses three
tamper paths (see the project's security advisory):

* **rm-to-reset** — the ledger lives outside the project tree
  (:mod:`agent_riggs.statedir`), so deleting ``.riggs/store.duckdb`` does
  not touch it. Deleting the ledger itself reads as ``absent``, which
  consumers must treat as *low* trust (fail closed), not max.
* **direct edits** — every record carries an HMAC over its payload chained
  to the previous record's MAC. Any edit breaks verification and the state
  reads as ``tampered`` (fail closed).
* **truncation** — a MAC'd head file pins the expected last record; cutting
  trailing (low-trust) records without the key reads as ``tampered``.

Known residual risk: an adversary who can read the key, or who snapshots
the *entire* state directory at a high-trust moment and later restores it,
defeats the chain. The key and ledger are created ``0600`` inside a ``0700``
directory; deployments wanting a hard boundary must keep the state
directory outside the subject's write (and ideally read) scope.
"""

from __future__ import annotations

import hmac
import json
import os
import secrets
from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256
from pathlib import Path

from agent_riggs.statedir import state_dir_for

_GENESIS = "0" * 64

_KEY_FILE = "ledger.key"
_LEDGER_FILE = "trust-ledger.jsonl"
_HEAD_FILE = "trust-ledger.head"

_PAYLOAD_FIELDS = (
    "seq",
    "timestamp",
    "session_id",
    "event_uid",
    "category",
    "score",
    "t1",
    "t5",
    "t15",
    "observed",
    "prev_mac",
)


class LedgerIntegrityError(Exception):
    """Raised when an operation would run on top of unverifiable trust state."""


@dataclass(frozen=True)
class LedgerRecord:
    seq: int
    timestamp: str
    session_id: str
    event_uid: str
    category: str
    score: float
    t1: float
    t5: float
    t15: float
    observed: bool
    prev_mac: str
    mac: str


@dataclass
class LedgerState:
    """Result of verifying the ledger. ``records`` is populated only for ``ok``."""

    status: str  # "ok" | "absent" | "tampered"
    records: list[LedgerRecord] = field(default_factory=list)
    detail: str = ""

    @property
    def last(self) -> LedgerRecord | None:
        return self.records[-1] if self.records else None


def _canonical(payload: dict) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


class TrustLedger:
    """Reads and appends the per-project trust ledger."""

    def __init__(self, project_root: Path | str, state_dir: Path | None = None) -> None:
        self.dir = Path(state_dir) if state_dir is not None else state_dir_for(project_root)
        self.key_path = self.dir / _KEY_FILE
        self.ledger_path = self.dir / _LEDGER_FILE
        self.head_path = self.dir / _HEAD_FILE

    # -- key handling ------------------------------------------------------

    def ensure_initialized(self) -> None:
        """Create the state directory and signing key if they don't exist."""
        self._ensure_key()

    def _ensure_key(self) -> bytes:
        key = self._load_key()
        if key is not None:
            return key
        self.dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.dir, 0o700)
        key = secrets.token_bytes(32)
        fd = os.open(self.key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(fd, key.hex().encode())
        finally:
            os.close(fd)
        return key

    def _load_key(self) -> bytes | None:
        try:
            return bytes.fromhex(self.key_path.read_text().strip())
        except FileNotFoundError:
            return None
        except ValueError:
            return None  # corrupt key: treated as missing; verify() reports tampered

    # -- mac helpers ---------------------------------------------------------

    def _record_mac(self, key: bytes, payload: dict) -> str:
        return hmac.new(key, _canonical(payload), sha256).hexdigest()

    def _head_mac(self, key: bytes, seq: int, mac: str) -> str:
        return hmac.new(key, f"head:{seq}:{mac}".encode(), sha256).hexdigest()

    def _read_head(self, key: bytes) -> tuple[int, str] | None:
        """Return (seq, mac) if the head file exists and its MAC verifies."""
        try:
            head = json.loads(self.head_path.read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            return None
        seq, mac, head_mac = head.get("seq"), head.get("mac"), head.get("head_mac")
        if not isinstance(seq, int) or not isinstance(mac, str) or not isinstance(head_mac, str):
            return None
        if not hmac.compare_digest(head_mac, self._head_mac(key, seq, mac)):
            return None
        return seq, mac

    def _write_head(self, key: bytes, seq: int, mac: str) -> None:
        payload = {"seq": seq, "mac": mac, "head_mac": self._head_mac(key, seq, mac)}
        tmp = self.head_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload))
        os.replace(tmp, self.head_path)

    # -- public API ----------------------------------------------------------

    def append(
        self,
        *,
        event_uid: str,
        session_id: str,
        category: str,
        score: float,
        t1: float,
        t5: float,
        t15: float,
        observed: bool,
        timestamp: datetime,
    ) -> LedgerRecord:
        """Append one trust record, chained to the current head."""
        key = self._ensure_key()
        head = self._read_head(key)
        if head is not None:
            seq, prev_mac = head[0] + 1, head[1]
        else:
            seq, prev_mac = 1, _GENESIS

        payload = {
            "seq": seq,
            "timestamp": timestamp.isoformat(),
            "session_id": session_id,
            "event_uid": event_uid,
            "category": category,
            "score": score,
            "t1": t1,
            "t5": t5,
            "t15": t15,
            "observed": observed,
            "prev_mac": prev_mac,
        }
        mac = self._record_mac(key, payload)
        record = LedgerRecord(mac=mac, **payload)

        with self.ledger_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({**payload, "mac": mac}) + "\n")
        os.chmod(self.ledger_path, 0o600)
        self._write_head(key, seq, mac)
        return record

    def verify(self) -> LedgerState:
        """Verify the full chain. Any inconsistency reads as ``tampered``.

        ``absent`` is returned only when neither ledger nor head exist —
        a genuinely new project. Everything else that fails to verify is
        ``tampered`` and must be treated as low trust by consumers.
        """
        ledger_exists = self.ledger_path.exists()
        head_exists = self.head_path.exists()
        if not ledger_exists and not head_exists:
            return LedgerState(status="absent")

        key = self._load_key()
        if key is None:
            return LedgerState(status="tampered", detail="trust state present but key missing")
        head = self._read_head(key)
        if head is None:
            return LedgerState(status="tampered", detail="head record missing or forged")
        if not ledger_exists:
            return LedgerState(status="tampered", detail="head present but ledger missing")

        records: list[LedgerRecord] = []
        prev_mac = _GENESIS
        with self.ledger_path.open(encoding="utf-8") as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    payload = {name: obj[name] for name in _PAYLOAD_FIELDS}
                    mac = obj["mac"]
                except (json.JSONDecodeError, KeyError, TypeError):
                    return LedgerState(status="tampered", detail=f"unreadable record {i + 1}")
                if payload["seq"] != len(records) + 1 or payload["prev_mac"] != prev_mac:
                    return LedgerState(status="tampered", detail=f"broken chain at record {i + 1}")
                if not hmac.compare_digest(mac, self._record_mac(key, payload)):
                    return LedgerState(status="tampered", detail=f"bad MAC at record {i + 1}")
                records.append(LedgerRecord(mac=mac, **payload))
                prev_mac = mac

        if not records:
            return LedgerState(status="tampered", detail="empty ledger with head present")
        last = records[-1]
        if last.seq != head[0] or not hmac.compare_digest(last.mac, head[1]):
            return LedgerState(status="tampered", detail="ledger truncated or rolled back")
        return LedgerState(status="ok", records=records)
