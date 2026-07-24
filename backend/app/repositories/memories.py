from __future__ import annotations

import base64
import json

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.enums import MemoryUpdateStatus, MemoryVersionType
from app.core.errors import AppError
from app.db.models_core import Branch, utc_now
from app.db.models_memory import MemoryUpdateRecord, MemoryVersion


class MemoryRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_current(self, branch_id: str) -> MemoryVersion | None:
        branch = self.session.get(Branch, branch_id)
        if branch is None or branch.active_memory_version_id is None:
            return None
        return self.session.get(MemoryVersion, branch.active_memory_version_id)

    def get_version(self, version_id: str) -> MemoryVersion | None:
        return self.session.get(MemoryVersion, version_id)

    def list_versions(
        self, branch_id: str, limit: int, cursor: str | None
    ) -> tuple[list[MemoryVersion], str | None, bool]:
        before = self._decode_cursor(cursor) if cursor else None
        statement = select(MemoryVersion).where(MemoryVersion.branch_id == branch_id)
        if before is not None:
            statement = statement.where(MemoryVersion.version_number < before)
        rows = list(
            self.session.scalars(
                statement.order_by(MemoryVersion.version_number.desc()).limit(limit + 1)
            )
        )
        has_more = len(rows) > limit
        items = rows[:limit]
        next_cursor = (
            self._encode_cursor(items[-1].version_number)
            if has_more and items
            else None
        )
        return items, next_cursor, has_more

    def next_version_number(self, branch_id: str) -> int:
        current = self.session.scalar(
            select(func.max(MemoryVersion.version_number)).where(
                MemoryVersion.branch_id == branch_id
            )
        )
        return int(current or 0) + 1

    def create_version(
        self,
        *,
        branch_id: str,
        version_type: MemoryVersionType,
        protected_user_text: str,
        system_summary: str,
        base_version_id: str | None = None,
        restored_from_version_id: str | None = None,
        inherited_from_version_id: str | None = None,
        covered_through_position: int | None = None,
        added_from_position: int | None = None,
        added_through_position: int | None = None,
        conflict_metadata: dict[str, object] | None = None,
    ) -> MemoryVersion:
        version = MemoryVersion(
            branch_id=branch_id,
            version_number=self.next_version_number(branch_id),
            type=version_type,
            base_version_id=base_version_id,
            restored_from_version_id=restored_from_version_id,
            inherited_from_version_id=inherited_from_version_id,
            protected_user_text=protected_user_text,
            system_summary=system_summary,
            covered_through_position=covered_through_position,
            added_from_position=added_from_position,
            added_through_position=added_through_position,
            conflict_metadata_json=conflict_metadata or {
                "status": "CLEAR",
                "checked_through_position": covered_through_position,
                "items": [],
            },
        )
        self.session.add(version)
        self.session.flush()
        return version

    def set_current(self, branch: Branch, version: MemoryVersion) -> None:
        branch.active_memory_version_id = version.id
        self.session.flush()

    def latest_update(self, branch_id: str) -> MemoryUpdateRecord | None:
        return self.session.scalar(
            select(MemoryUpdateRecord)
            .where(MemoryUpdateRecord.branch_id == branch_id)
            .order_by(
                MemoryUpdateRecord.created_at.desc(),
                MemoryUpdateRecord.id.desc(),
            )
            .limit(1)
        )

    def create_update_record(
        self,
        *,
        branch_id: str,
        base_version_id: str | None,
        from_position: int,
        through_position: int,
    ) -> MemoryUpdateRecord:
        record = MemoryUpdateRecord(
            branch_id=branch_id,
            base_memory_version_id=base_version_id,
            target_from_position=from_position,
            target_through_position=through_position,
            status=MemoryUpdateStatus.RUNNING,
            attempt_count=0,
        )
        self.session.add(record)
        self.session.flush()
        return record

    def finish_update(
        self,
        record: MemoryUpdateRecord,
        *,
        version: MemoryVersion | None = None,
        attempt_count: int,
        error_category: str | None = None,
        error_message: str | None = None,
    ) -> None:
        record.status = (
            MemoryUpdateStatus.SUCCEEDED
            if version is not None
            else MemoryUpdateStatus.FAILED
        )
        record.attempt_count = attempt_count
        record.error_category = error_category
        record.error_message = error_message[:500] if error_message else None
        record.created_memory_version_id = version.id if version else None
        record.completed_at = utc_now()

    def find_inheritable(
        self, source_branch_id: str, fork_position: int
    ) -> MemoryVersion | None:
        return self.session.scalar(
            select(MemoryVersion)
            .where(
                MemoryVersion.branch_id == source_branch_id,
                or_(
                    MemoryVersion.covered_through_position.is_(None),
                    MemoryVersion.covered_through_position < fork_position,
                ),
            )
            .order_by(MemoryVersion.version_number.desc())
            .limit(1)
        )

    @staticmethod
    def _encode_cursor(version_number: int) -> str:
        raw = json.dumps({"v": 1, "n": version_number}).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    @staticmethod
    def _decode_cursor(cursor: str) -> int:
        try:
            padding = "=" * (-len(cursor) % 4)
            payload = json.loads(base64.urlsafe_b64decode(cursor + padding))
            if payload.get("v") != 1 or int(payload["n"]) < 1:
                raise ValueError
            return int(payload["n"])
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            raise AppError("无效的分页游标", {"cursor": "invalid"}) from exc
