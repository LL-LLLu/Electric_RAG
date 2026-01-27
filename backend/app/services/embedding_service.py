import logging
from typing import List
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Generate embeddings for semantic search"""

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        logger.info(f"Loading embedding model: {model_name}...")
        self.model = SentenceTransformer(model_name)
        self.embedding_dim = 384
        logger.info(f"Embedding model loaded successfully")

    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for a single text"""
        if not text or not text.strip():
            return [0.0] * self.embedding_dim

        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        valid_texts = [t if t and t.strip() else " " for t in texts]
        embeddings = self.model.encode(valid_texts, convert_to_numpy=True)
        return embeddings.tolist()

    def prepare_page_text_for_embedding(self, ocr_text: str, equipment_tags: List[str]) -> str:
        """Prepare page text for embedding with equipment context"""
        equipment_str = " ".join(equipment_tags) if equipment_tags else ""
        combined = f"{equipment_str} {ocr_text}"
        if len(combined) > 5000:
            combined = combined[:5000]
        return combined


embedding_service = EmbeddingService()
