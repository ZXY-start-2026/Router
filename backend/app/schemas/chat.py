from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.core.enums import (
    AnswerVersionStatus,
    GenerationStatus,
    SelectionMode,
    UserMessageStatus,
)


MODEL_KEYS = {"MODEL_A", "MODEL_B", "MODEL_C"}


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1)
    selection_mode: SelectionMode = SelectionMode.AUTO_ROUTE
    model_key: str | None = None

    @model_validator(mode="after")
    def validate_selection(self) -> "SendMessageRequest":
        self.content = self.content.strip()
        if not self.content:
            raise ValueError("消息不能为空")
        if self.selection_mode == SelectionMode.USER_SELECTED:
            if self.model_key not in MODEL_KEYS:
                raise ValueError("手动选择时必须指定 MODEL_A、MODEL_B 或 MODEL_C")
        elif self.selection_mode == SelectionMode.AUTO_ROUTE:
            if self.model_key is not None:
                raise ValueError("自动路由时不能指定模型")
        else:
            raise ValueError("当前接口仅支持自动路由或用户指定")
        return self


class UserMessageResponse(BaseModel):
    id: str
    content: str
    status: UserMessageStatus
    logical_position: int
    created_at: datetime


class AnswerResponse(BaseModel):
    id: str
    content: str
    model_key: str
    model_id: str
    display_name: str
    selection_mode: SelectionMode
    status: AnswerVersionStatus
    created_at: datetime
    completed_at: datetime
    predicted_input_tokens: int | None = None
    predicted_output_tokens: int | None = None
    actual_input_tokens: int | None = None
    actual_output_tokens: int | None = None
    predicted_cost: Decimal | None = None
    actual_cost: Decimal | None = None
    price_version: str | None = None
    finish_reason: str | None = None


class BranchTurnResponse(BaseModel):
    user_message: UserMessageResponse
    active_answer: AnswerResponse | None


class BranchMessagesResponse(BaseModel):
    conversation_id: str
    branch_id: str
    items: list[BranchTurnResponse]


class GenerationResultSummary(BaseModel):
    status: GenerationStatus
    task_id: str | None = None
    search_status: str | None = None
    selected_model_key: str | None = None
    route_snapshot_id: str | None = None
    failure_code: str | None = None
    failure_message: str | None = None


class SendMessageResponse(BaseModel):
    user_message: UserMessageResponse
    active_answer: AnswerResponse | None
    generation: GenerationResultSummary


class ModelOptionResponse(BaseModel):
    model_key: str
    label: str
    available: bool
