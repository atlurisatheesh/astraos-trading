"""AstraOS Routers — RAG Knowledge API."""

from fastapi import APIRouter, Depends, Query, BackgroundTasks

from ..core.dependencies import get_current_user
from ..knowledge.rag_engine import get_rag_engine

router = APIRouter(prefix="/api/v1/rag", tags=["RAG Books"])


@router.post("/build")
async def build_index(background_tasks: BackgroundTasks, force: bool = False, user=Depends(get_current_user)):
    """Trigger the building of the FAISS index from the 4 PDFs."""
    engine = get_rag_engine()
    
    # Run in background because parsing hundreds of pages takes time
    background_tasks.add_task(engine.load_and_index_books, force_rebuild=force)
    
    return {"status": "processing", "message": "Building FAISS index in background from Damodaran, Natenberg, Graham, etc."}


@router.get("/search")
async def search_books(query: str = Query(..., min_length=3), k: int = Query(4, le=10), user=Depends(get_current_user)):
    """Semantic search across the institutional books."""
    engine = get_rag_engine()
    
    # Try to load if not already loaded
    if not engine.vector_store:
        try:
            engine.load_and_index_books(force_rebuild=False)
        except Exception:
            pass
            
    if not engine.vector_store:
        return {"error": "Index not built yet. Call /api/v1/rag/build first."}
        
    results = engine.search(query, k)
    return {
        "query": query,
        "count": len(results),
        "results": results
    }
