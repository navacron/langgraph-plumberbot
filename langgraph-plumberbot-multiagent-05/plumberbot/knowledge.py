"""RAG knowledge base: loads docs/*.txt and builds a retriever.

Two backends, selected automatically:
  - OPENAI_API_KEY set  → InMemoryVectorStore with text-embedding-3-small (semantic search)
  - Anthropic key only  → BM25Retriever (keyword search, no API needed)

The retriever interface is identical either way — the knowledge subagent is unaware of
which backend is active.

Embedding cache (OpenAI backend only):
  On first build the embedding vectors are pickled to EMBEDDINGS_CACHE_PATH.
  On subsequent startups the cache is loaded instead of calling the OpenAI API.

  Cache path precedence:
    1. EMBEDDINGS_CACHE_PATH env var  (set to /data/... on HF Pro tier)
    2. <project_root>/embeddings_cache.pkl  (can be pre-computed and committed to git)
"""

import glob
import os
import pickle

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()

_HERE = os.path.dirname(os.path.abspath(__file__))
DOCS_DIR = os.path.join(_HERE, "..", "docs")

# Default cache path sits at the project root so it can be committed to git.
EMBEDDINGS_CACHE_PATH = os.getenv(
    "EMBEDDINGS_CACHE_PATH",
    os.path.join(_HERE, "..", "embeddings_cache.pkl"),
)


def _load_docs() -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    docs: list[Document] = []
    for path in sorted(glob.glob(os.path.join(DOCS_DIR, "*.txt"))):
        text = open(path, encoding="utf-8").read()
        article_name = os.path.basename(path).replace(".txt", "")
        for chunk in splitter.split_text(text):
            docs.append(Document(page_content=chunk, metadata={"source": article_name}))
    return docs


def _save_vector_cache(vs) -> None:
    """Pickle the InMemoryVectorStore internal store dict to avoid re-embedding."""
    cache_dir = os.path.dirname(EMBEDDINGS_CACHE_PATH)
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)
    with open(EMBEDDINGS_CACHE_PATH, "wb") as f:
        pickle.dump(vs.store, f)
    print(f"[knowledge] Embeddings cached → {EMBEDDINGS_CACHE_PATH}")


def _load_vector_cache(embeddings_model):
    """Restore an InMemoryVectorStore from the cache without calling the API."""
    if not os.path.exists(EMBEDDINGS_CACHE_PATH):
        return None
    try:
        from langchain_core.vectorstores import InMemoryVectorStore
        with open(EMBEDDINGS_CACHE_PATH, "rb") as f:
            store_data = pickle.load(f)
        vs = InMemoryVectorStore(embedding=embeddings_model)
        vs.store = store_data  # restore pre-computed vectors
        n = len(store_data)
        print(f"[knowledge] Loaded {n} chunks from cache ({EMBEDDINGS_CACHE_PATH})")
        return vs
    except Exception as exc:
        print(f"[knowledge] Cache load failed ({exc}), rebuilding...")
        return None


def _build_vector_retriever(docs: list[Document]) -> BaseRetriever:
    """Semantic search via OpenAI text-embedding-3-small, with disk cache."""
    from langchain_core.vectorstores import InMemoryVectorStore
    from langchain_openai import OpenAIEmbeddings

    embeddings_model = OpenAIEmbeddings(model="text-embedding-3-small")

    vs = _load_vector_cache(embeddings_model)
    if vs is None:
        print(f"[knowledge] Computing OpenAI embeddings for {len(docs)} chunks…")
        vs = InMemoryVectorStore(embedding=embeddings_model)
        if docs:
            vs.add_documents(docs)
        _save_vector_cache(vs)

    return vs.as_retriever(search_kwargs={"k": 3})


def _build_bm25_retriever(docs: list[Document]) -> BaseRetriever:
    """Keyword search via BM25 — no API key needed, no caching required."""
    from langchain_community.retrievers import BM25Retriever

    return BM25Retriever.from_documents(docs, k=3)


def build_retriever() -> BaseRetriever:
    docs = _load_docs()
    if os.getenv("OPENAI_API_KEY"):
        backend = "OpenAI vector (text-embedding-3-small)"
        retriever = _build_vector_retriever(docs)
    else:
        backend = "BM25 keyword (no API key required)"
        retriever = _build_bm25_retriever(docs)
    print(f"[knowledge] RAG backend: {backend} — {len(docs)} chunks loaded")
    return retriever


_retriever: BaseRetriever | None = None


def get_retriever() -> BaseRetriever:
    """Return the shared retriever, building it on first call."""
    global _retriever
    if _retriever is None:
        _retriever = build_retriever()
    return _retriever


def rebuild_embeddings_cache() -> str:
    """Force-recompute OpenAI embeddings and save a fresh cache.

    Called by the Gradio 'Rebuild Embeddings' button and the CLI build script.
    Returns a human-readable status string.
    """
    global _retriever
    if not os.getenv("OPENAI_API_KEY"):
        return "⚠️ OPENAI_API_KEY not set — using BM25, no embeddings to rebuild."
    try:
        # Delete stale cache so _build_vector_retriever starts fresh
        if os.path.exists(EMBEDDINGS_CACHE_PATH):
            os.remove(EMBEDDINGS_CACHE_PATH)
        _retriever = None  # force rebuild on next get_retriever() call
        _retriever = build_retriever()
        n = len(getattr(_retriever.vectorstore if hasattr(_retriever, "vectorstore") else _retriever, "store", {}))
        return f"✅ Knowledge base rebuilt — {n} chunks embedded and cached."
    except Exception as exc:
        return f"❌ Rebuild failed: {exc}"
