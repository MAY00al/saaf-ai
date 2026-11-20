"""Persistent cosine retrieval with source hydration."""

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Literal, Protocol

import chromadb

from .corpus import Record, Source, load_corpus

DEFAULT_MODEL = "text-embedding-3-small"
DEFAULT_TOP_K = 3
DEFAULT_MIN_SCORE = 0.35


class Embeddings(Protocol):
    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...


class EmbeddingUnavailable(RuntimeError):
    """The embedding provider failed to compute vectors."""


@dataclass(frozen=True)
class Hit:
    record: Record
    source: Source
    score: float


@dataclass(frozen=True)
class SearchResult:
    status: Literal["ok", "insufficient_evidence"]
    hits: tuple[Hit, ...] = ()
    reason: Literal["empty_query", "no_relevant_hits"] | None = None


class KnowledgeIndex:
    def __init__(
        self, corpus_path: Path, index_path: Path, embeddings: Embeddings,
        *, model: str = DEFAULT_MODEL,
    ) -> None:
        self.corpus, digest = load_corpus(corpus_path)
        self.records = {record.id: record for record in self.corpus.records}
        self.embeddings = embeddings
        fingerprint = sha256(f"v1\n{model}\n{digest}".encode()).hexdigest()
        self.name = f"saaf-{fingerprint[:40]}"
        client = chromadb.PersistentClient(path=str(index_path))
        self.collection = client.get_or_create_collection(
            self.name,
            configuration={"hnsw": {"space": "cosine"}},
            metadata={"corpus_sha256": digest, "embedding_model": model},
            embedding_function=None,
        )

    def ingest(self) -> int:
        indexed_ids = set(self.collection.get(include=[])["ids"])
        missing = [record for record in self.records.values() if record.id not in indexed_ids]
        if missing:
            documents = [record.text_ar for record in missing]
            try:
                vectors = self.embeddings.embed_documents(documents)
            except Exception as exc:
                raise EmbeddingUnavailable("document embeddings unavailable") from exc
            metadata = [
                record.model_dump(include={"source_id", "topic", "evidence_level", "caveat_ar"},
                                  exclude_none=True)
                for record in missing
            ]
            self.collection.upsert(
                ids=[record.id for record in missing], documents=documents,
                embeddings=vectors, metadatas=metadata,
            )
        return len(missing)

    def search(
        self, query: str, *, top_k: int = DEFAULT_TOP_K,
        min_score: float = DEFAULT_MIN_SCORE, topic: str | None = None,
    ) -> SearchResult:
        if top_k < 1:
            raise ValueError("top_k must be positive")
        if not -1 <= min_score <= 1:
            raise ValueError("min_score must be between -1 and 1")
        if not query.strip():
            return SearchResult("insufficient_evidence", reason="empty_query")
        count = self.collection.count()
        if not count:
            return SearchResult("insufficient_evidence", reason="no_relevant_hits")
        if count != len(self.records):
            raise RuntimeError("index is incomplete; run ingestion again")
        try:
            vector = self.embeddings.embed_query(query.strip())
        except Exception as exc:
            raise EmbeddingUnavailable("query embedding unavailable") from exc
        matches = self.collection.query(
            query_embeddings=[vector], n_results=min(top_k, count),
            where={"topic": topic} if topic is not None else None,
            include=["distances"],
        )
        hits = []
        for record_id, distance in zip(matches["ids"][0], matches["distances"][0], strict=True):
            score = max(-1.0, min(1.0, 1.0 - distance))
            if score >= min_score:
                record = self.records[record_id]
                hits.append(Hit(record, self.corpus.sources[record.source_id], score))
        if not hits:
            return SearchResult("insufficient_evidence", reason="no_relevant_hits")
        return SearchResult("ok", tuple(hits))
