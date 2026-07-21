from __future__ import annotations

from collections.abc import Iterator

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.providers.model import ModelProvider
from app.providers.registry import ProviderRegistry
from app.schemas.chat import (
    BranchMessagesResponse,
    ModelOptionResponse,
    SendMessageRequest,
    SendMessageResponse,
)
from app.schemas.common import CursorPage, HealthResponse
from app.schemas.generation import GenerationTaskResponse
from app.schemas.conversations import (
    ConversationListItem,
    ConversationResponse,
    CreateConversationRequest,
    UpdateConversationRequest,
)
from app.services.chat import ChatService
from app.services.conversations import ConversationService


router = APIRouter()


def get_session(request: Request) -> Iterator[Session]:
    session = request.app.state.session_factory()
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_model_provider(request: Request) -> ModelProvider:
    return request.app.state.model_provider


def get_providers(request: Request) -> ProviderRegistry:
    return request.app.state.providers


@router.get("/health", response_model=HealthResponse)
def health(session: Session = Depends(get_session)) -> HealthResponse:
    session.execute(select(1))
    return HealthResponse(status="ok")


@router.post(
    "/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation(
    body: CreateConversationRequest,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    provider: ModelProvider = Depends(get_model_provider),
) -> ConversationResponse:
    return ConversationService(session, settings, provider).create(body)


@router.get(
    "/conversations",
    response_model=CursorPage[ConversationListItem],
)
def list_conversations(
    limit: int = Query(default=20, ge=1, le=100),
    cursor: str | None = None,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    provider: ModelProvider = Depends(get_model_provider),
) -> CursorPage[ConversationListItem]:
    return ConversationService(session, settings, provider).list_page(limit, cursor)


@router.get("/conversations/{conversation_id}", response_model=ConversationResponse)
def get_conversation(
    conversation_id: str,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    provider: ModelProvider = Depends(get_model_provider),
) -> ConversationResponse:
    return ConversationService(session, settings, provider).get(conversation_id)


@router.patch("/conversations/{conversation_id}", response_model=ConversationResponse)
def update_conversation(
    conversation_id: str,
    body: UpdateConversationRequest,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    provider: ModelProvider = Depends(get_model_provider),
) -> ConversationResponse:
    return ConversationService(session, settings, provider).rename(conversation_id, body)


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=BranchMessagesResponse,
)
def list_messages(
    conversation_id: str,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    providers: ProviderRegistry = Depends(get_providers),
) -> BranchMessagesResponse:
    return ChatService(session, settings, providers).list_active_branch_messages(
        conversation_id
    )


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=SendMessageResponse,
    status_code=status.HTTP_201_CREATED,
)
def send_message(
    conversation_id: str,
    body: SendMessageRequest,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    providers: ProviderRegistry = Depends(get_providers),
) -> SendMessageResponse:
    return ChatService(session, settings, providers).send_message(conversation_id, body)


@router.get("/generation-tasks/{task_id}", response_model=GenerationTaskResponse)
def get_generation_task(
    task_id: str,
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    providers: ProviderRegistry = Depends(get_providers),
) -> GenerationTaskResponse:
    return ChatService(session, settings, providers).get_generation_task(task_id)


@router.get("/models", response_model=list[ModelOptionResponse])
def list_models(
    session: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    provider: ModelProvider = Depends(get_model_provider),
) -> list[ModelOptionResponse]:
    return ConversationService(session, settings, provider).list_model_options()
