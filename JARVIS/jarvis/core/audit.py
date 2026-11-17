from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("jarvis")
_SENSITIVE_KEYS = {"password", "secret", "token", "api_key", "authorization", "encryption_key"}


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: ("[REDACTED]" if k.lower() in _SENSITIVE_KEYS else _redact(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, str) and len(value) > 2000:
        return value[:2000] + "…[truncated]"
    return value


class AuditLogger:
    """Append-only local JSONL audit trail; refuses callers if persistence fails."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._lock = threading.Lock()

    def record(self, event: str, *, request_id: str | None = None, **details: Any) -> dict[str, Any]:
        entry = {"timestamp": datetime.now(timezone.utc).isoformat(), "event": event,
                 "request_id": request_id, "details": _redact(details)}
        serialized = json.dumps(entry, ensure_ascii=False, separators=(",", ":"), default=str)
        try:
            with self._lock:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a", encoding="utf-8") as handle:
                    handle.write(serialized + "\n")
        except OSError:
            logger.exception("Unable to persist audit event %s", event)
            raise
        logger.info("audit event", extra={"audit_event": entry})
        return entry
