"""RAG knowledge base: loads docs/*.txt, chunks, and embeds using OpenAI embeddings.

Loaded once at import time — all agents share the same in-memory vectorstore.
Requires OPENAI_API_KEY to be set (used only for embeddings, not generation).
"""

import glob
import os

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()

_HERE = os.path.dirname(os.path.abspath(__file__))
DOCS_DIR = os.path.join(_HERE, "..", "docs")


def build_vectorstore() -> InMemoryVectorStore:
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    docs: list[Document] = []
    for path in sorted(glob.glob(os.path.join(DOCS_DIR, "*.txt"))):
        text = open(path, encoding="utf-8").read()
        article_name = os.path.basename(path).replace(".txt", "")
        for chunk in splitter.split_text(text):
            docs.append(Document(page_content=chunk, metadata={"source": article_name}))
    vs = InMemoryVectorStore(embedding=embeddings)
    if docs:
        vs.add_documents(docs)
    return vs


_vectorstore: InMemoryVectorStore | None = None


def get_vectorstore() -> InMemoryVectorStore:
    global _vectorstore
    if _vectorstore is None:
        _vectorstore = build_vectorstore()
    return _vectorstore
