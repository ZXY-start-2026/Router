from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.core.enums import SearchStatus


@dataclass(frozen=True, slots=True)
class SearchRequest:
    query: str
    max_results: int = 5


@dataclass(frozen=True, slots=True)
class SearchResultItem:
    title: str
    snippet: str
    url: str


@dataclass(frozen=True, slots=True)
class SearchResponse:
    provider: str
    status: SearchStatus
    query: str
    results: tuple[SearchResultItem, ...] = ()
    failure_code: str | None = None
    failure_message: str | None = None
    latency_ms: int = 0


class SearchProvider(ABC):
    @abstractmethod
    def search(self, request: SearchRequest) -> SearchResponse:
        raise NotImplementedError


class DisabledSearchProvider(SearchProvider):
    """Real 360 web-search integration is intentionally deferred by user decision."""

    def search(self, request: SearchRequest) -> SearchResponse:
        return SearchResponse(
            provider="360",
            status=SearchStatus.FAILED,
            query=request.query,
            failure_code="SEARCH_NOT_IMPLEMENTED",
            failure_message="360 搜索暂未接入，本轮继续使用模型自身知识回答",
        )


class MockSearchProvider(SearchProvider):
    def __init__(self, response: SearchResponse | None = None) -> None:
        self.response = response

    def search(self, request: SearchRequest) -> SearchResponse:
        return self.response or SearchResponse(
            provider="mock",
            status=SearchStatus.FAILED,
            query=request.query,
            failure_code="MOCK_SEARCH_UNAVAILABLE",
            failure_message="测试搜索不可用",
        )
