"""RAG knowledge base: loads docs/*.txt and builds a retriever.

Two backends, selected automatically:
  - OPENAI_API_KEY set  → InMemoryVectorStore with text-embedding-3-small (semantic search)
  - Anthropic key only  → BM25Retriever (keyword search, no API needed)

The retriever interface is identical either way — the knowledge subagent is unaware of
which backend is active.
"""

import glob
import os

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()

_HERE = os.path.dirname(os.path.abspath(__file__))
DOCS_DIR = os.path.join(_HERE, "..", "docs")


def _load_docs() -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    docs: list[Document] = []
    for path in sorted(glob.glob(os.path.join(DOCS_DIR, "*.txt"))):
        text = open(path, encoding="utf-8").read()
        article_name = os.path.basename(path).replace(".txt", "")
        for chunk in splitter.split_text(text):
            docs.append(Document(page_content=chunk, metadata={"source": article_name}))
    return docs


def _build_vector_retriever(docs: list[Document]) -> BaseRetriever:
    """Semantic search via OpenAI text-embedding-3-small."""
    from langchain_core.vectorstores import InMemoryVectorStore
    from langchain_openai import OpenAIEmbeddings

    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    vs = InMemoryVectorStore(embedding=embeddings)
    if docs:
        vs.add_documents(docs)
    return vs.as_retriever(search_kwargs={"k": 3})


def _build_bm25_retriever(docs: list[Document]) -> BaseRetriever:
    """Keyword search via BM25 — no API key needed."""
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
