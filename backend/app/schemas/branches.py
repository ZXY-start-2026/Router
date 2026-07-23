from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.enums import BranchPointType, RegenerationMode, SelectionMode
from app.schemas.chat import (
    AnswerResponse,
    GenerationResultSummary,
    MODEL_KEYS,
    UserMessageResponse,
)


class RegenerateRequest(BaseModel):
    branch_id: str
    mode: RegenerationMode
    model_key: str | None = None

    @model_validator(mode="after")
    def validate_mode(self) -> "RegenerateRequest":
        if self.mode == RegenerationMode.REGENERATE_USER_SELECTED:
            if self.model_key not in MODEL_KEYS:
                raise ValueError("临时指定模型时必须选择 MODEL_A、MODEL_B 或 MODEL_C")
        elif self.model_key is not None:
            raise ValueError("当前重新生成模式不能指定模型")
        return self


class ActivateAnswerRequest(BaseModel):
    branch_id: str


class EditMessageRequest(BaseModel):
    branch_id: str
    content: str = Field(min_length=1)
    selection_mode: SelectionMode = SelectionMode.AUTO_ROUTE
    model_key: str | None = None

    @field_validator("content")
    @classmethod
    def normalize_content(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("消息不能为空")
        return normalized

    @model_validator(mode="after")
    def validate_selection(self) -> "EditMessageRequest":
        if self.selection_mode == SelectionMode.USER_SELECTED:
            if self.model_key not in MODEL_KEYS:
                raise ValueError("手动选择时必须指定 MODEL_A、MODEL_B 或 MODEL_C")
        elif self.selection_mode == SelectionMode.AUTO_ROUTE:
            if self.model_key is not None:
                raise ValueError("自动路由时不能指定模型")
        else:
            raise ValueError("当前接口仅支持自动路由或用户指定")
        return self


class AnswerVersionsResponse(BaseModel):
    user_message_id: str
    branch_id: str
    active_answer_version_id: str | None
    items: list[AnswerResponse]


class GenerationOperationResponse(BaseModel):
    conversation_id: str
    branch_id: str
    created_branch_id: str | None
    user_message: UserMessageResponse
    active_answer: AnswerResponse | None
    generation: GenerationResultSummary


class AnswerActivationResponse(BaseModel):
    conversation_id: str
    branch_id: str
    created_branch_id: str | None
    active_answer: AnswerResponse


class BranchResponse(BaseModel):
    id: str
    parent_branch_id: str | None
    branch_point_type: BranchPointType
    branch_point_message_id: str | None
    branch_point_answer_version_id: str | None
    complete_turn_count: int
    created_at: datetime
    is_active: bool


class BranchListResponse(BaseModel):
    conversation_id: str
    active_branch_id: str
    items: list[BranchResponse]


class BranchActivationResponse(BaseModel):
    conversation_id: str
    active_branch_id: str
