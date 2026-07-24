from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import ConflictError
from app.db.models_core import AssistantAnswerVersion, Branch, BranchMessage
from app.db.models_generation import ContextSnapshot, GenerationTask
from app.db.models_role import RoleTemplate, RoleVersion


class RoleRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_current_for_branch(self, branch_id: str) -> RoleVersion | None:
        branch = self.session.get(Branch, branch_id)
        if branch is None or branch.active_role_version_id is None:
            return None
        return self.session.get(RoleVersion, branch.active_role_version_id)

    def get_version(self, version_id: str) -> RoleVersion | None:
        return self.session.get(RoleVersion, version_id)

    def next_version_number(self, conversation_id: str) -> int:
        current = self.session.scalar(
            select(func.max(RoleVersion.version_number)).where(
                RoleVersion.conversation_id == conversation_id
            )
        )
        return int(current or 0) + 1

    def create_version(self, conversation_id: str, content) -> RoleVersion:
        version = RoleVersion(
            conversation_id=conversation_id,
            version_number=self.next_version_number(conversation_id),
            source_template_id=content.source_template_id,
            name=content.name,
            persona=content.persona,
            background=content.background,
            domain=content.domain,
            traits_json=content.traits,
            style=content.style,
            constraints_text=content.constraints_text,
        )
        self.session.add(version)
        self.session.flush()
        return version

    def set_active_for_branch(self, branch: Branch, version: RoleVersion) -> None:
        if version.conversation_id != branch.conversation_id:
            raise ConflictError("角色版本不属于目标会话")
        branch.active_role_version_id = version.id
        self.session.flush()

    def clear_active_for_branch(self, branch: Branch) -> None:
        branch.active_role_version_id = None
        self.session.flush()

    def create_template(self, content) -> RoleTemplate:
        template = RoleTemplate(
            name=content.name,
            persona=content.persona,
            background=content.background,
            domain=content.domain,
            traits_json=content.traits,
            style=content.style,
            constraints_text=content.constraints_text,
        )
        self.session.add(template)
        self.session.flush()
        return template

    def list_templates(self) -> list[RoleTemplate]:
        return list(
            self.session.scalars(
                select(RoleTemplate).order_by(
                    RoleTemplate.created_at.asc(), RoleTemplate.id.asc()
                )
            )
        )

    def get_template(self, template_id: str) -> RoleTemplate | None:
        return self.session.get(RoleTemplate, template_id)

    def role_id_at_fork(
        self,
        source_branch_id: str,
        fork_position: int,
        answer_id: str | None,
    ) -> str | None:
        if answer_id:
            role_id = self.session.scalar(
                select(ContextSnapshot.role_version_id)
                .join(
                    GenerationTask,
                    GenerationTask.context_snapshot_id == ContextSnapshot.id,
                )
                .join(
                    AssistantAnswerVersion,
                    AssistantAnswerVersion.generation_task_id == GenerationTask.id,
                )
                .where(AssistantAnswerVersion.id == answer_id)
                .limit(1)
            )
            if role_id is not None:
                return role_id

        statement = (
            select(ContextSnapshot.role_version_id)
            .join(
                GenerationTask,
                GenerationTask.context_snapshot_id == ContextSnapshot.id,
            )
            .join(
                AssistantAnswerVersion,
                AssistantAnswerVersion.generation_task_id == GenerationTask.id,
            )
            .join(
                BranchMessage,
                BranchMessage.active_answer_version_id == AssistantAnswerVersion.id,
            )
            .where(
                BranchMessage.branch_id == source_branch_id,
                BranchMessage.logical_position <= fork_position,
            )
            .order_by(BranchMessage.logical_position.desc())
        )
        for role_id in self.session.scalars(statement):
            if role_id is not None:
                return role_id
        return None
