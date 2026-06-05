"""AstraOS Tests — RAG Engine & Knowledge API."""

import pytest
from unittest.mock import patch, MagicMock

from src.knowledge.rag_engine import RAGEngine
from src.routers.rag_router import router

class TestRAGEngine:
    """Mock test for FAISS RAG operations."""

    @patch("src.knowledge.rag_engine.FAISS")
    def test_search_returns_docs(self, mock_faiss):
        # Mock vector store
        mock_vstore = MagicMock()
        mock_doc = MagicMock()
        mock_doc.page_content = "Intrinsic value is calculated via DCF..."
        mock_doc.metadata = {"source": "investment-valuation", "page": 42}
        
        mock_vstore.similarity_search_with_score.return_value = [(mock_doc, 0.85)]
        
        # Setup engine
        engine = RAGEngine()
        engine.vector_store = mock_vstore
        
        # Search
        results = engine.search("intrinsic value")
        
        # Verify
        assert len(results) == 1
        assert results[0]["book"] == "investment-valuation"
        assert results[0]["page"] == 42
        assert "DCF" in results[0]["content"]

    def test_search_without_index_returns_empty(self):
        engine = RAGEngine()
        engine.vector_store = None
        results = engine.search("What is gamma?")
        assert results == []
