from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.core.enums import AttemptStatus, ErrorCategory, GenerationStatus, SearchStatus


class SearchSnapshotResponse(BaseModel):
    provider: str
    status: SearchStatus
    failure_code: str | None
    failure_message: str | None
    latency_ms: int


class RouteCandidateResponse(BaseModel):
    model_key: str
    display_name: str
    eligible: bool
    ineligible_reason: str | None
    predicted_accuracy: Decimal | None
    predicted_input_tokens: int | None
    predicted_output_tokens: int | None
    predicted_cost: Decimal | None
    cost_score: Decimal | None
    route_score: Decimal | None
    rank: int | None


class GenerationAttemptResponse(BaseModel):
    attempt_index: int
    model_key: str
    display_name: str
    response_model: str | None
    started_at: datetime
    ended_at: datetime
    status: AttemptStatus
    finish_reason: str | None
    error_category: ErrorCategory | None
    error_code: str | None
    error_message: str | None
    retry_of_attempt_id: str | None
    actual_input_tokens: int | None
    actual_output_tokens: int | None
    charged_cost: Decimal | None
    price_version: str


class GenerationTaskResponse(BaseModel):
    id: str
    status: GenerationStatus
    requested_model_key: str | None
    failure_category: ErrorCategory | None
    failure_message: str | None
    created_at: datetime
    completed_at: datetime | None
    search: SearchSnapshotResponse
    route_snapshot_id: str | None
    candidates: list[RouteCandidateResponse]
    attempts: list[GenerationAttemptResponse]
