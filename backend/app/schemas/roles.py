from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class RoleContentRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    persona: str = ""
    background: str = ""
    domain: str = ""
    traits: list[str] = Field(default_factory=list)
    style: str = ""
    constraints_text: str = ""
    source_template_id: str | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("角色名称不能为空")
        return value

    @field_validator("traits")
    @classmethod
    def normalize_traits(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        for item in values:
            normalized = item.strip()
            if normalized and normalized not in result:
                result.append(normalized)
        return result


class RoleTemplateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    persona: str = ""
    background: str = ""
    domain: str = ""
    traits: list[str] = Field(default_factory=list)
    style: str = ""
    constraints_text: str = ""

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("模板名称不能为空")
        return value

    @field_validator("traits")
    @classmethod
    def normalize_traits(cls, values: list[str]) -> list[str]:
        result: list[str] = []
        for item in values:
            normalized = item.strip()
            if normalized and normalized not in result:
                result.append(normalized)
        return result


class RoleVersionResponse(BaseModel):
    id: str
    conversation_id: str
    version_number: int
    source_template_id: str | None
    name: str
    persona: str
    background: str
    domain: str
    traits: list[str]
    style: str
    constraints_text: str
    created_at: datetime


class CurrentRoleResponse(BaseModel):
    conversation_id: str
    branch_id: str
    active_role: RoleVersionResponse | None


class RoleTemplateResponse(BaseModel):
    id: str
    name: str
    persona: str
    background: str
    domain: str
    traits: list[str]
    style: str
    constraints_text: str
    created_at: datetime


class RoleTemplateListResponse(BaseModel):
    items: list[RoleTemplateResponse]
