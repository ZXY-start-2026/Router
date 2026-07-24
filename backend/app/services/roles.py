from __future__ import annotations

from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError
from app.db.models_core import Branch
from app.db.models_role import RoleTemplate, RoleVersion
from app.repositories.conversations import ConversationRepository
from app.repositories.roles import RoleRepository
from app.schemas.roles import (
    CurrentRoleResponse,
    RoleContentRequest,
    RoleTemplateListResponse,
    RoleTemplateRequest,
    RoleTemplateResponse,
    RoleVersionResponse,
)


class RoleService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.roles = RoleRepository(session)
        self.conversations = ConversationRepository(session)

    def get_current(self, conversation_id: str) -> CurrentRoleResponse:
        conversation, branch = self._require_active_branch(conversation_id)
        role = self.roles.get_current_for_branch(branch.id)
        return CurrentRoleResponse(
            conversation_id=conversation.id,
            branch_id=branch.id,
            active_role=self.version_response(role) if role else None,
        )

    def update(
        self, conversation_id: str, content: RoleContentRequest
    ) -> CurrentRoleResponse:
        conversation, branch = self._require_active_branch(conversation_id)
        if content.source_template_id and not self.roles.get_template(
            content.source_template_id
        ):
            raise NotFoundError("角色模板不存在")
        version = self.roles.create_version(conversation.id, content)
        self.roles.set_active_for_branch(branch, version)
        self.conversations.touch(conversation)
        self.session.commit()
        return CurrentRoleResponse(
            conversation_id=conversation.id,
            branch_id=branch.id,
            active_role=self.version_response(version),
        )

    def deactivate(self, conversation_id: str) -> CurrentRoleResponse:
        conversation, branch = self._require_active_branch(conversation_id)
        self.roles.clear_active_for_branch(branch)
        self.conversations.touch(conversation)
        self.session.commit()
        return CurrentRoleResponse(
            conversation_id=conversation.id,
            branch_id=branch.id,
            active_role=None,
        )

    def list_templates(self) -> RoleTemplateListResponse:
        return RoleTemplateListResponse(
            items=[self.template_response(item) for item in self.roles.list_templates()]
        )

    def create_template(
        self, content: RoleTemplateRequest
    ) -> RoleTemplateResponse:
        template = self.roles.create_template(content)
        self.session.commit()
        return self.template_response(template)

    def inherit_for_branch(
        self,
        source: Branch,
        target: Branch,
        fork_position: int,
        answer_id: str | None,
    ) -> RoleVersion | None:
        role_id = self.roles.role_id_at_fork(
            source.id, fork_position, answer_id
        )
        if role_id is None:
            return None
        role = self.roles.get_version(role_id)
        if role is None or role.conversation_id != target.conversation_id:
            raise ConflictError("分叉点角色版本不可用")
        self.roles.set_active_for_branch(target, role)
        return role

    @staticmethod
    def render(role: RoleVersion | None) -> str:
        if role is None:
            return ""
        parts: list[str] = [f"角色名称：{role.name}"]
        values = (
            ("人格定位", role.persona),
            ("背景", role.background),
            ("专业领域", role.domain),
            ("性格特征", "、".join(role.traits_json)),
            ("表达风格", role.style),
            ("回答约束", role.constraints_text),
        )
        parts.extend(f"{label}：{value}" for label, value in values if value)
        return "\n".join(parts)

    @staticmethod
    def version_response(role: RoleVersion) -> RoleVersionResponse:
        return RoleVersionResponse(
            id=role.id,
            conversation_id=role.conversation_id,
            version_number=role.version_number,
            source_template_id=role.source_template_id,
            name=role.name,
            persona=role.persona,
            background=role.background,
            domain=role.domain,
            traits=role.traits_json,
            style=role.style,
            constraints_text=role.constraints_text,
            created_at=role.created_at,
        )

    @staticmethod
    def template_response(template: RoleTemplate) -> RoleTemplateResponse:
        return RoleTemplateResponse(
            id=template.id,
            name=template.name,
            persona=template.persona,
            background=template.background,
            domain=template.domain,
            traits=template.traits_json,
            style=template.style,
            constraints_text=template.constraints_text,
            created_at=template.created_at,
        )

    def _require_active_branch(self, conversation_id: str):
        conversation = self.conversations.get(conversation_id)
        if conversation is None:
            raise NotFoundError("会话不存在")
        branch = self.conversations.get_active_branch(conversation)
        if branch is None:
            raise ConflictError("会话缺少活动分支")
        return conversation, branch
