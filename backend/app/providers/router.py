from __future__ import annotations

import csv
import pickle
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
from sklearn.neighbors import NearestNeighbors
from transformers import BertModel, BertTokenizer

from app.core.config import ModelConfig, RouterConfig
from app.core.errors import ConfigurationError, ProviderError
from app.core.enums import ErrorCategory
from app.providers.mirt import MIRT


@dataclass(frozen=True, slots=True)
class RouterCandidateInput:
    model_key: str
    router_model_name: str


@dataclass(frozen=True, slots=True)
class RouterRequest:
    question: str
    candidates: tuple[RouterCandidateInput, ...]


@dataclass(frozen=True, slots=True)
class RouterPredictionSet:
    predictions: dict[str, float]
    version: str


class RouterProvider(ABC):
    @abstractmethod
    def predict(self, request: RouterRequest) -> RouterPredictionSet:
        raise NotImplementedError


class MockRouterProvider(RouterProvider):
    def __init__(self, predictions: dict[str, float] | None = None) -> None:
        self.predictions = predictions or {
            "MODEL_A": 0.90,
            "MODEL_B": 0.80,
            "MODEL_C": 0.70,
        }

    def predict(self, request: RouterRequest) -> RouterPredictionSet:
        return RouterPredictionSet(
            predictions={
                candidate.model_key: self.predictions[candidate.model_key]
                for candidate in request.candidates
            },
            version="mock-router-v1",
        )


class LocalMirtRouterProvider(RouterProvider):
    embedding_dim = 768

    def __init__(
        self,
        config: RouterConfig,
        models: tuple[ModelConfig, ...],
    ) -> None:
        self.config = config
        self.asset_dir = config.asset_dir
        self._load_assets(models)

    def _load_assets(self, models: tuple[ModelConfig, ...]) -> None:
        required = {
            "snapshot": self.asset_dir / "mirt_bert.snapshot",
            "bert": self.asset_dir / "bert-base-uncased",
            "llm_embeddings": self.asset_dir / "bert_embeddings" / "llm_embeddings.pkl",
            "query_embeddings": self.asset_dir / "bert_embeddings" / "query_embeddings.pkl",
            "cold_embeddings": self.asset_dir / "cold" / "test_avg_embeddings_bert.pkl",
            "llm_map": self.asset_dir / "map" / "llm.csv",
            "query_map": self.asset_dir / "map" / "query.csv",
        }
        missing = [name for name, path in required.items() if not path.exists()]
        if missing:
            raise ConfigurationError(f"缺少路由资产：{', '.join(missing)}")

        self.llm_id_map = self._read_csv_map(required["llm_map"], "name")
        self.query_id_map = self._read_csv_map(required["query_map"], "question")
        for model in models:
            if model.router_model_name not in self.llm_id_map:
                raise ConfigurationError(
                    f"router_model_name 不存在：{model.router_model_name}"
                )

        self.llm_embeddings = self._read_embeddings(
            required["llm_embeddings"], "embedding"
        )
        query_data = self._read_pickle(required["query_embeddings"])
        self.query_embeddings = {
            int(entry["index"]): self._vector(entry["embedding"])
            for entry in query_data
        }
        cold_data = self._read_pickle(required["cold_embeddings"])
        self.cold_embeddings = {
            int(entry["index"]): self._vector(entry["avg_embedding"])
            for entry in cold_data
        }
        if not query_data:
            raise ConfigurationError("query_embeddings 为空")
        self.train_embeddings = np.asarray(
            [self._vector(entry["embedding"]) for entry in query_data]
        )
        neighbor_count = min(self.config.knn_neighbors, len(self.train_embeddings))
        self.knn = NearestNeighbors(n_neighbors=neighbor_count, algorithm="auto")
        self.knn.fit(self.train_embeddings)

        self.bert_tokenizer = BertTokenizer.from_pretrained(
            required["bert"], local_files_only=True
        )
        self.bert_model = BertModel.from_pretrained(
            required["bert"], local_files_only=True
        ).to(self.config.device)
        self.bert_model.eval()
        self.mirt = MIRT(self.embedding_dim, self.embedding_dim, self.config.knowledge_n)
        self.mirt.load(required["snapshot"])

    @staticmethod
    def _read_csv_map(path: Path, key_field: str) -> dict[str, int]:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            result = {
                str(row[key_field]): int(row["index"])
                for row in csv.DictReader(stream)
            }
        if not result:
            raise ConfigurationError(f"映射文件为空：{path.name}")
        return result

    @staticmethod
    def _read_pickle(path: Path):
        with path.open("rb") as stream:
            return pickle.load(stream)  # trusted deployment assets only

    def _read_embeddings(self, path: Path, field: str) -> dict[int, np.ndarray]:
        return {
            int(entry["index"]): self._vector(entry[field])
            for entry in self._read_pickle(path)
        }

    def _vector(self, value) -> np.ndarray:
        vector = np.asarray(value, dtype=np.float32)
        if vector.shape != (self.embedding_dim,) or not np.isfinite(vector).all():
            raise ConfigurationError("路由 Embedding 必须是有限的 768 维向量")
        return vector

    def encode_question(self, question: str) -> np.ndarray:
        query_id = self.query_id_map.get(question)
        if query_id is not None:
            query_vector = self.query_embeddings[query_id]
            cold_vector = self.cold_embeddings.get(
                query_id, np.zeros(self.embedding_dim, dtype=np.float32)
            )
            weight = float(self.config.lambda_value)
            return (1 - weight) * query_vector + weight * cold_vector

        inputs = self.bert_tokenizer(
            question,
            return_tensors="pt",
            padding=True,
            truncation=True,
        ).to(self.config.device)
        with torch.no_grad():
            outputs = self.bert_model(**inputs)
        new_embedding = (
            outputs.last_hidden_state.mean(dim=1).squeeze().detach().cpu().numpy()
        )
        _, indices = self.knn.kneighbors([new_embedding])
        return np.mean(self.train_embeddings[indices[0]], axis=0)

    def predict(self, request: RouterRequest) -> RouterPredictionSet:
        try:
            query_vector = self.encode_question(request.question)
            predictions: dict[str, float] = {}
            for candidate in request.candidates:
                llm_id = self.llm_id_map[candidate.router_model_name]
                llm_vector = self.llm_embeddings[llm_id]
                predictions[candidate.model_key] = self.mirt.generate(
                    llm_vector,
                    query_vector,
                    device=self.config.device,
                )
            return RouterPredictionSet(
                predictions=predictions,
                version="mirt-bert-v1",
            )
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(
                "本地 MIRT 路由预测失败",
                category=ErrorCategory.UNKNOWN,
                fallback_allowed=False,
                global_stop=True,
            ) from exc
