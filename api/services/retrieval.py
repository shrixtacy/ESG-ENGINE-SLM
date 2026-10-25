"""
ESGPilot — RAG Retrieval Service.

Hybrid retrieval (dense + sparse → RRF fusion → rerank).
Manages Qdrant collections, embedding, chunking, and query rewriting.
"""

import uuid
import hashlib
from typing import Optional
from dataclasses import dataclass, field

from qdrant_client import QdrantClient, models
from qdrant_client.http.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    SearchRequest,
    ScoredPoint,
)

from api.core.config import get_settings

settings = get_settings()


@dataclass
class ChunkMetadata:
    """Metadata per chunk (per ARCHITECTURE.md §2.5)."""
    doc_id: str
    doc_title: str
    issuer: Optional[str] = None
    doc_type: str = "guidance"  # law | circular | standard | guidance | example
    version: Optional[str] = None
    effective_from: Optional[str] = None
    effective_to: Optional[str] = None
    superseded_by: Optional[str] = None
    section_path: Optional[str] = None
    framework: Optional[str] = None
    principle: Optional[str] = None
    indicator_id: Optional[str] = None
    page: Optional[int] = None
    url: Optional[str] = None
    lang: str = "en"
    tenant_scope: str = "global"  # "global" or tenant_id


@dataclass
class RetrievedChunk:
    """A retrieved chunk with score and metadata."""
    chunk_id: str
    text: str
    score: float
    metadata: ChunkMetadata
    rank: int = 0


class RetrievalService:
    """
    Hybrid retrieval over Qdrant collections.
    Supports global KB and per-tenant private KB.
    """

    # Collection names per ARCHITECTURE.md §2.5
    GLOBAL_COLLECTION = "kb_global"
    EXAMPLES_COLLECTION = "kb_examples"

    def __init__(self):
        self.client = QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            api_key=settings.qdrant_api_key or None,
        )
        self._embedding_model = None
        self._reranker = None

    def _get_embedding_model(self):
        """Lazy-load the embedding model."""
        if self._embedding_model is None:
            from FlagEmbedding import BGEM3FlagModel
            self._embedding_model = BGEM3FlagModel(
                settings.embedding_model, use_fp16=True
            )
        return self._embedding_model

    def _get_reranker(self):
        """Lazy-load the reranker."""
        if self._reranker is None:
            from FlagEmbedding import FlagReranker
            self._reranker = FlagReranker(
                settings.reranker_model, use_fp16=True
            )
        return self._reranker

    def ensure_collections(self):
        """Create collections if they don't exist."""
        collections = [self.GLOBAL_COLLECTION, self.EXAMPLES_COLLECTION]
        existing = {c.name for c in self.client.get_collections().collections}

        for name in collections:
            if name not in existing:
                self.client.create_collection(
                    collection_name=name,
                    vectors_config=VectorParams(
                        size=settings.embedding_dim,
                        distance=Distance.COSINE,
                    ),
                )

    def get_tenant_collection(self, tenant_id: str) -> str:
        """Get or create per-tenant private collection."""
        name = f"kb_tenant_{tenant_id}"
        existing = {c.name for c in self.client.get_collections().collections}
        if name not in existing:
            self.client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(
                    size=settings.embedding_dim,
                    distance=Distance.COSINE,
                ),
            )
        return name

    def embed_text(self, text: str) -> list[float]:
        """Embed a single text using BGE-M3."""
        model = self._get_embedding_model()
        result = model.encode([text], return_dense=True)
        return result["dense_vecs"][0].tolist()

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Batch embed texts."""
        model = self._get_embedding_model()
        result = model.encode(texts, return_dense=True)
        return [v.tolist() for v in result["dense_vecs"]]

    def index_chunks(
        self,
        chunks: list[dict],
        collection: str = None,
    ):
        """
        Index chunks into Qdrant.
        Each chunk: {"id": str, "text": str, "metadata": ChunkMetadata}
        """
        if not collection:
            collection = self.GLOBAL_COLLECTION

        texts = [c["text"] for c in chunks]
        vectors = self.embed_texts(texts)

        points = []
        for chunk, vector in zip(chunks, vectors):
            meta = chunk["metadata"]
            if isinstance(meta, ChunkMetadata):
                payload = meta.__dict__
            else:
                payload = meta

            payload["text"] = chunk["text"]

            point_id = chunk.get("id", uuid.uuid4().hex)
            # Qdrant expects either UUID or unsigned int
            # Use UUID string hash
            numeric_id = int(hashlib.md5(point_id.encode()).hexdigest()[:16], 16)

            points.append(PointStruct(
                id=numeric_id,
                vector=vector,
                payload=payload,
            ))

        # Batch upsert
        batch_size = 100
        for i in range(0, len(points), batch_size):
            self.client.upsert(
                collection_name=collection,
                points=points[i:i + batch_size],
            )

    def search(
        self,
        query: str,
        collection: str = None,
        top_k: int = None,
        framework: Optional[str] = None,
        doc_type: Optional[str] = None,
        tenant_scope: str = "global",
        effective_fy: Optional[str] = None,
    ) -> list[RetrievedChunk]:
        """
        Hybrid search: dense embedding search + metadata filtering.
        """
        if not collection:
            collection = self.GLOBAL_COLLECTION
        if not top_k:
            top_k = settings.retrieval_top_k

        query_vector = self.embed_text(query)

        # Build Qdrant filters
        filter_conditions = []
        if framework:
            filter_conditions.append(
                FieldCondition(key="framework", match=MatchValue(value=framework))
            )
        if doc_type:
            filter_conditions.append(
                FieldCondition(key="doc_type", match=MatchValue(value=doc_type))
            )
        if tenant_scope:
            filter_conditions.append(
                FieldCondition(key="tenant_scope", match=MatchValue(value=tenant_scope))
            )

        search_filter = Filter(must=filter_conditions) if filter_conditions else None

        results = self.client.search(
            collection_name=collection,
            query_vector=query_vector,
            query_filter=search_filter,
            limit=top_k,
            with_payload=True,
        )

        return self._scored_to_chunks(results)

    def search_multi_collection(
        self,
        query: str,
        collections: list[str],
        top_k: int = None,
        framework: Optional[str] = None,
    ) -> list[RetrievedChunk]:
        """Search across multiple collections and merge via RRF."""
        all_chunks = []
        for coll in collections:
            try:
                chunks = self.search(
                    query=query,
                    collection=coll,
                    top_k=top_k or settings.retrieval_top_k,
                    framework=framework,
                )
                all_chunks.extend(chunks)
            except Exception:
                continue  # Collection may not exist

        # Reciprocal Rank Fusion
        return self._rrf_merge(all_chunks, top_k or settings.retrieval_top_k)

    def rerank(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        top_k: int = None,
    ) -> list[RetrievedChunk]:
        """Rerank retrieved chunks using bge-reranker-v2-m3."""
        if not chunks:
            return []

        if not top_k:
            top_k = settings.rerank_top_k

        reranker = self._get_reranker()
        pairs = [[query, c.text] for c in chunks]
        scores = reranker.compute_score(pairs, normalize=True)

        if isinstance(scores, float):
            scores = [scores]

        # Attach rerank scores
        for chunk, score in zip(chunks, scores):
            chunk.score = score

        # Sort by reranked score, take top_k
        chunks.sort(key=lambda c: c.score, reverse=True)
        top_chunks = chunks[:top_k]

        for i, chunk in enumerate(top_chunks):
            chunk.rank = i + 1

        return top_chunks

    def retrieve(
        self,
        query: str,
        tenant_id: Optional[str] = None,
        framework: Optional[str] = None,
        top_k_retrieve: int = None,
        top_k_rerank: int = None,
    ) -> list[RetrievedChunk]:
        """
        Full retrieval pipeline: search → RRF fusion → rerank.
        Searches global KB + tenant KB if tenant_id provided.
        """
        collections = [self.GLOBAL_COLLECTION, self.EXAMPLES_COLLECTION]
        if tenant_id:
            collections.append(self.get_tenant_collection(tenant_id))

        # Search all collections
        candidates = self.search_multi_collection(
            query=query,
            collections=collections,
            top_k=top_k_retrieve or settings.retrieval_top_k,
            framework=framework,
        )

        # Rerank
        reranked = self.rerank(
            query=query,
            chunks=candidates,
            top_k=top_k_rerank or settings.rerank_top_k,
        )

        return reranked

    def _scored_to_chunks(self, results: list[ScoredPoint]) -> list[RetrievedChunk]:
        """Convert Qdrant ScoredPoints to RetrievedChunks."""
        chunks = []
        for i, r in enumerate(results):
            payload = r.payload or {}
            text = payload.pop("text", "")

            meta = ChunkMetadata(
                doc_id=payload.get("doc_id", ""),
                doc_title=payload.get("doc_title", ""),
                issuer=payload.get("issuer"),
                doc_type=payload.get("doc_type", "guidance"),
                version=payload.get("version"),
                effective_from=payload.get("effective_from"),
                effective_to=payload.get("effective_to"),
                superseded_by=payload.get("superseded_by"),
                section_path=payload.get("section_path"),
                framework=payload.get("framework"),
                principle=payload.get("principle"),
                indicator_id=payload.get("indicator_id"),
                page=payload.get("page"),
                url=payload.get("url"),
                lang=payload.get("lang", "en"),
                tenant_scope=payload.get("tenant_scope", "global"),
            )

            chunks.append(RetrievedChunk(
                chunk_id=str(r.id),
                text=text,
                score=r.score,
                metadata=meta,
                rank=i + 1,
            ))

        return chunks

    @staticmethod
    def _rrf_merge(
        chunks: list[RetrievedChunk],
        top_k: int,
        k: int = 60,
    ) -> list[RetrievedChunk]:
        """Reciprocal Rank Fusion merge of results from multiple collections."""
        chunk_scores: dict[str, float] = {}
        chunk_map: dict[str, RetrievedChunk] = {}

        for chunk in chunks:
            cid = chunk.chunk_id
            rrf_score = 1.0 / (k + chunk.rank)
            chunk_scores[cid] = chunk_scores.get(cid, 0) + rrf_score
            chunk_map[cid] = chunk

        # Sort by fused score
        sorted_ids = sorted(chunk_scores, key=lambda x: chunk_scores[x], reverse=True)

        result = []
        for i, cid in enumerate(sorted_ids[:top_k]):
            chunk = chunk_map[cid]
            chunk.score = chunk_scores[cid]
            chunk.rank = i + 1
            result.append(chunk)

        return result
