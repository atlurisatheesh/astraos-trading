"""AstraOS Knowledge — RAG Engine for Institutional Books.

Loads local PDF books, chunks them, embeds them using HuggingFace
sentence transformers, and stores them in a local FAISS index (zero cost).
AI agents use this to back test ideas against Natenberg, Damodaran, and Graham.
"""

import os
from pathlib import Path
import structlog
from typing import List

try:
    from langchain_core.documents import Document
except ImportError:
    Document = None  # type: ignore[assignment,misc]

try:
    from langchain_community.vectorstores import FAISS
except ImportError:  # pragma: no cover
    FAISS = None  # type: ignore[assignment]

logger = structlog.get_logger()

# Books found in workspace
PDFS = [
    r"d:\stocks-monitoring\D1FZ114_S3_INVESTMENT.pdf",
    r"d:\stocks-monitoring\Option Volatility and Pricing (Sheldon Natenberg).pdf",
    r"d:\stocks-monitoring\investment-valuation-3rd-edition.pdf",
    r"d:\stocks-monitoring\security-analysis-seventh-edition-principles-and-techniques-7nbsped-1264932405-9781264932405_compress.pdf",
]

INDEX_DIR = r"d:\stocks-monitoring\apps\api\data\faiss_index"


class RAGEngine:
    """Retrieval-Augmented Generation using local PDFs and FAISS."""

    def __init__(self, embed_model_name: str = "all-MiniLM-L6-v2"):
        self.embed_model_name = embed_model_name
        self.embeddings = None
        self.vector_store = None
        
        try:
            from langchain_huggingface import HuggingFaceEmbeddings
            self.embeddings = HuggingFaceEmbeddings(model_name=embed_model_name)
        except ImportError:
            logger.warning("langchain_huggingface not available — RAG disabled")
        
        # Ensure data dir exists
        try:
            os.makedirs(INDEX_DIR, exist_ok=True)
        except Exception:
            pass

    def load_and_index_books(self, force_rebuild: bool = False):
        """Parse PDFs, chunk, and create FAISS index."""
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        import fitz  # PyMuPDF

        index_path = os.path.join(INDEX_DIR, "index.faiss")
        
        if os.path.exists(index_path) and not force_rebuild:
            logger.info("Loading existing FAISS index")
            self.vector_store = FAISS.load_local(
                INDEX_DIR, self.embeddings, allow_dangerous_deserialization=True
            )
            return

        logger.info("Building new FAISS index from PDFs", books=len(PDFS))
        documents: List[Document] = []

        for pdf_path in PDFS:
            if not os.path.exists(pdf_path):
                logger.warning("PDF not found, skipping", path=pdf_path)
                continue
                
            book_name = Path(pdf_path).stem
            logger.info("Parsing PDF", book=book_name)
            
            try:
                doc = fitz.open(pdf_path)
                for page_num in range(len(doc)):
                    page = doc.load_page(page_num)
                    text = page.get_text("text")
                    if text.strip():
                        documents.append(
                            Document(
                                page_content=text,
                                metadata={
                                    "source": book_name,
                                    "page": page_num + 1
                                }
                            )
                        )
            except Exception as e:
                logger.error("Error parsing PDF", book=book_name, error=str(e))

        if not documents:
            logger.warning("No documents loaded. Vector store is empty.")
            return

        # Split text into chunks
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            separators=["\n\n", "\n", ".", " ", ""],
        )
        logger.info("Chunking documents")
        chunks = text_splitter.split_documents(documents)
        logger.info(f"Created {len(chunks)} chunks")

        # Build FAISS index
        logger.info("Generating embeddings and building vectors")
        self.vector_store = FAISS.from_documents(chunks, self.embeddings)
        
        # Save locally
        self.vector_store.save_local(INDEX_DIR)
        logger.info("FAISS index saved", path=INDEX_DIR)

    def search(self, query: str, k: int = 4) -> list[dict]:
        """Search the books for investment knowledge."""
        if not self.vector_store:
            logger.warning("Vector store not initialized")
            return []

        results = self.vector_store.similarity_search_with_score(query, k=k)
        
        docs = []
        for doc, score in results:
            docs.append({
                "content": doc.page_content,
                "book": doc.metadata.get("source", "Unknown"),
                "page": doc.metadata.get("page", 0),
                "relevance_score": round(float(score), 4),
            })
            
        return docs


# Singleton instance
_rag_engine = None

def get_rag_engine() -> RAGEngine:
    global _rag_engine
    if _rag_engine is None:
        _rag_engine = RAGEngine()
    return _rag_engine
