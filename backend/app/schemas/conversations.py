from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import GenerationStatus, TitleSource


class CreateConversationRequest(BaseModel):
    title: str | None = Field(default=None, max_length=200)

    @field_validator("title")
    @classmethod
    def normalize_optional_title(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("标题不能为空")
        return normalized


class UpdateConversationRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("标题不能为空")
        return normalized


class ConversationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    title_source: TitleSource
    active_branch_id: str
    created_at: datetime
    updated_at: datetime
    generation_status: GenerationStatus = GenerationStatus.IDLE


class ConversationListItem(BaseModel):
    id: str
    title: str
    latest_message_preview: str | None
    updated_at: datetime
    generation_status: GenerationStatus

