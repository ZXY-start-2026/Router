from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.core.enums import (
    MemoryOperationStatus,
    MemoryUpdateStatus,
    MemoryVersionType,
)


class MemoryConfigResponse(BaseModel):
    n: int
    k: int
    m: int


class MemoryVersionResponse(BaseModel):
    id: str
    branch_id: str
    version_number: int
    type: MemoryVersionType
    base_version_id: str | None
    restored_from_version_id: str | None
    inherited_from_version_id: str | None
    protected_user_text: str
    system_summary: str
    covered_through_position: int | None
    added_from_position: int | None
    added_through_position: int | None
    conflict_metadata: dict[str, object]
    created_at: datetime
    is_current: bool


class MemoryUpdateStatusResponse(BaseModel):
    id: str
    status: MemoryUpdateStatus
    target_from_position: int
    target_through_position: int
    attempt_count: int
    error_category: str | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None
    created_memory_version_id: str | None


class CurrentMemoryResponse(BaseModel):
    branch_id: str
    current: MemoryVersionResponse | None
    latest_update: MemoryUpdateStatusResponse | None
    config: MemoryConfigResponse


class MemoryVersionsResponse(BaseModel):
    items: list[MemoryVersionResponse]
    next_cursor: str | None
    has_more: bool


class UpdateProtectedMemoryRequest(BaseModel):
    protected_user_text: str


class MemoryOperationResponse(BaseModel):
    branch_id: str
    operation_status: MemoryOperationStatus
    current: MemoryVersionResponse | None
    created_version: MemoryVersionResponse | None
    latest_update: MemoryUpdateStatusResponse | None
