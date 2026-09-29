"""Audit log for the GitOps sync job. Every create/update recorded here,
with a timestamp, before any write reaches the Control API. Written to
stdout as structured JSON by default, and optionally to a file (--audit-log
flag in the CLI), so it can be shipped to a log aggregator by whatever
wrapper runs the sync job (CronJob, GitHub Actions, etc.).
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

logger = logging.getLogger(__name__)


@dataclass
class AuditEntry:
    operation: str  # "create" | "update" | "skip"
    resource_kind: (
        str  # "organization" | "team" | "project" | "agent" | "provider" | "model" | "policy"
    )
    resource_name: str
    resource_id: str | None
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def as_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "operation": self.operation,
            "resource_kind": self.resource_kind,
            "resource_name": self.resource_name,
            "resource_id": self.resource_id,
        }


class AuditLog:
    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []

    def record(self, operation: str, kind: str, name: str, resource_id: str | None = None) -> None:
        entry = AuditEntry(
            operation=operation,
            resource_kind=kind,
            resource_name=name,
            resource_id=resource_id,
        )
        self._entries.append(entry)
        logger.info("audit: %s", json.dumps(entry.as_dict()))

    @property
    def entries(self) -> list[AuditEntry]:
        return list(self._entries)

    def summary(self) -> dict:
        ops: dict[str, int] = {}
        for e in self._entries:
            ops[e.operation] = ops.get(e.operation, 0) + 1
        return {"total": len(self._entries), "by_operation": ops}

    def write_to_file(self, path: str) -> None:
        with open(path, "w") as f:
            json.dump(
                {"entries": [e.as_dict() for e in self._entries], "summary": self.summary()},
                f,
                indent=2,
            )
        logger.info("audit log written to %s", path)
