"""Script to build the FAISS vector index from PDFs."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from src.knowledge.rag_engine import get_rag_engine

if __name__ == "__main__":
    print("Starting FAISS RAG index build for Institutional Books...")
    engine = get_rag_engine()
    engine.load_and_index_books(force_rebuild=True)
    print("FAISS Index build complete.")
