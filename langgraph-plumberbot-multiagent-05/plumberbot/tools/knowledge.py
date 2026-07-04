"""Knowledge base tools — RAG search over plumbing how-to articles."""

import glob
import os

from langchain_core.tools import tool

from ..knowledge import get_vectorstore


@tool
def search_knowledge_base(query: str) -> str:
    """Search the plumbing knowledge base for how-to tips and troubleshooting guides.
    Use for DIY advice, repair instructions, maintenance tips, and plumbing questions."""
    results = get_vectorstore().similarity_search(query, k=3)
    if not results:
        return "No relevant articles found in the knowledge base."
    sections = [
        f"[Article: {r.metadata['source']}]\n{r.page_content}" for r in results
    ]
    return "\n\n---\n\n".join(sections)


@tool
def list_articles() -> list[str]:
    """List all available plumbing how-to articles in the knowledge base."""
    here = os.path.dirname(os.path.abspath(__file__))
    docs_dir = os.path.join(here, "..", "..", "docs")
    paths = glob.glob(os.path.join(docs_dir, "*.txt"))
    return [os.path.basename(p).replace(".txt", "") for p in sorted(paths)]


knowledge_tools = [search_knowledge_base, list_articles]
