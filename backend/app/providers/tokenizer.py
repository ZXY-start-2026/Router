from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from tokenizers import Tokenizer

from app.core.config import ModelConfig
from app.core.errors import ConfigurationError


class TokenizerProvider(ABC):
    @abstractmethod
    def count_prompt(self, model: ModelConfig, prompt: str) -> int:
        raise NotImplementedError


class MockTokenizerProvider(TokenizerProvider):
    def __init__(self, counts: dict[str, int] | None = None) -> None:
        self.counts = counts or {}

    def count_prompt(self, model: ModelConfig, prompt: str) -> int:
        return self.counts.get(model.model_key, max(1, len(prompt.encode("utf-8")) // 3))


class LocalTokenizerProvider(TokenizerProvider):
    def __init__(self) -> None:
        self._cache: dict[Path, Tokenizer] = {}

    def count_prompt(self, model: ModelConfig, prompt: str) -> int:
        if model.tokenizer_path is None:
            raise ConfigurationError(f"{model.model_key} 缺少 tokenizer_path")
        path = model.tokenizer_path
        tokenizer_file = path / "tokenizer.json" if path.is_dir() else path
        tokenizer_file = tokenizer_file.resolve()
        if not tokenizer_file.exists():
            raise ConfigurationError(f"Tokenizer 不存在：{tokenizer_file}")
        tokenizer = self._cache.get(tokenizer_file)
        if tokenizer is None:
            try:
                tokenizer = Tokenizer.from_file(str(tokenizer_file))
            except Exception as exc:
                raise ConfigurationError(f"Tokenizer 加载失败：{tokenizer_file}") from exc
            self._cache[tokenizer_file] = tokenizer
        return len(tokenizer.encode(prompt, add_special_tokens=True).ids)
