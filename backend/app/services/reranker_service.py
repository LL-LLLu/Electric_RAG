"""
Cross-Encoder Reranker Service

Uses a cross-encoder model to re-score search results by evaluating
query-document pairs together, improving ranking accuracy over
initial bi-encoder/keyword scores.
"""

import logging
import math
import threading
from typing import List, Optional

logger = logging.getLogger(__name__)

# Scoring constants
RERANKER_WEIGHT = 0.70
ORIGINAL_WEIGHT = 0.30
SCORE_SCALE = 2.0  # Original scores range 0-2
EXP_CLAMP_LIMIT = 20.0


def _exp_clamp(x: float) -> float:
    """Clamped exponential to avoid overflow."""
    x = max(-EXP_CLAMP_LIMIT, min(EXP_CLAMP_LIMIT, x))
    return math.exp(x)


class RerankerService:
    """Reranks search results using a cross-encoder model."""

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-12-v2"):
        self._model_name = model_name
        self._model = None  # Lazy-loaded
        self._lock = threading.Lock()

    def _load_model(self):
        """Load the cross-encoder model on first use (thread-safe)."""
        if self._model is not None:
            return

        with self._lock:
            # Double-check after acquiring lock
            if self._model is not None:
                return

            try:
                from sentence_transformers import CrossEncoder
                logger.info(f"Loading reranker model: {self._model_name}...")
                self._model = CrossEncoder(self._model_name)
                logger.info("Reranker model loaded successfully")
            except Exception as e:
                logger.warning(f"Failed to load reranker model: {e}. Reranking disabled.")
                self._model = None

    @property
    def is_available(self) -> bool:
        """Check if reranker model is loaded and available."""
        self._load_model()
        return self._model is not None

    def rerank(
        self,
        query: str,
        results: List,
        top_k: Optional[int] = None
    ) -> List:
        """
        Rerank search results using the cross-encoder.

        Args:
            query: The user's original search query
            results: List of SearchResult objects to rerank
            top_k: Return only top K results (None = return all, reranked)

        Returns:
            Reranked list of SearchResult objects with updated relevance_scores
        """
        if not results:
            return results

        self._load_model()
        if self._model is None:
            logger.debug("Reranker unavailable, returning results with original scores")
            return results[:top_k] if top_k else results

        try:
            # Build query-document pairs for scoring
            pairs = []
            for result in results:
                doc_text = self._extract_text(result)
                pairs.append([query, doc_text])

            # Score all pairs in batch
            scores = self._model.predict(pairs)

            # Combine reranker score with original score
            for i, result in enumerate(results):
                reranker_score = float(scores[i])
                # Normalize cross-encoder score to 0-1 range (sigmoid)
                normalized = 1.0 / (1.0 + _exp_clamp(-reranker_score))
                original = min(result.relevance_score / SCORE_SCALE, 1.0)
                result.relevance_score = (
                    normalized * RERANKER_WEIGHT + original * ORIGINAL_WEIGHT
                ) * SCORE_SCALE

            # Sort by new combined score
            results.sort(key=lambda r: r.relevance_score, reverse=True)

            if top_k:
                results = results[:top_k]

            logger.debug(f"Reranked {len(pairs)} results, top score: {results[0].relevance_score:.3f}")
            return results

        except Exception as e:
            logger.warning(f"Reranking failed: {e}. Returning original order.")
            return results[:top_k] if top_k else results

    def _extract_text(self, result) -> str:
        """Extract text from a SearchResult for cross-encoder scoring."""
        parts = []

        if result.document:
            if result.document.title:
                parts.append(result.document.title)
            if result.document.drawing_number:
                parts.append(f"Drawing: {result.document.drawing_number}")

        if result.equipment and result.equipment.tag:
            parts.append(f"Equipment: {result.equipment.tag}")

        if result.snippet:
            parts.append(result.snippet)

        text = " | ".join(parts) if parts else ""
        # Truncate to ~512 tokens (~2000 chars) for cross-encoder efficiency
        return text[:2000]


# Singleton instance
reranker_service = RerankerService()
