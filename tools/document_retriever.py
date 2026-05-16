"""
Document retriever using PageIndex RAG (vectorless, OCR-enabled).

Provides two retrieval modes:
1. Agentic: Uses OpenAI Agents SDK with PageIndex tools (recommended)
2. Simple: Keyword matching fallback when OpenAI Agents SDK not available
"""

import logging
from pathlib import Path
from tools.pageindex_rag import (
    retrieve_documents_agentic,
    retrieve_documents_simple,
    index_document,
    list_indexed_documents,
    format_retrieval_results,
    get_pageindex_client
)

logger = logging.getLogger(__name__)


def retrieve_documents(query: str, user_id: str, k: int = 4) -> list[str]:
    """
    Retrieve document sections using PageIndex RAG with agentic reasoning.

    Uses OpenAI Agents SDK with PageIndex tools. Falls back to simple
    keyword matching if OpenAI Agents SDK not available.

    Args:
        query: Search query
        user_id: User ID
        k: Number of documents to retrieve (used in simple fallback)

    Returns:
        List of document content strings (for backward compatibility with researcher agent)
    """
    if not user_id:
        return ["Error: user_id is required."]

    try:
        # Try agentic retrieval first (OpenAI Agents SDK pattern)
        logger.info("Attempting agentic retrieval with OpenAI Agents SDK")
        agentic_result = retrieve_documents_agentic(query, user_id=user_id)

        # Check if result is valid (not an error/empty state)
        if agentic_result and agentic_result not in [
            "No documents available in the knowledge base.",
            "No documents available for retrieval."
        ]:
            return [agentic_result]  # Return as list for researcher agent

    except ImportError:
        logger.info("OpenAI Agents SDK not available, falling back to simple retrieval")
    except Exception as e:
        logger.warning(f"Agentic retrieval error: {e}, falling back to simple retrieval")

    # Fall back to simple keyword-based retrieval
    logger.info("Using simple keyword-based retrieval")
    simple_result = retrieve_documents_simple(query, k=k, user_id=user_id)

    return [simple_result] if simple_result else []


def retrieve_documents_agentic_only(query: str, user_id: str) -> str:
    """
    Retrieve documents using ONLY agentic LLM reasoning (no fallback).

    The LLM will:
    - Call tools to examine document structure
    - Reason about which pages are relevant
    - Retrieve specific page ranges
    - Return structured answer with citations

    Args:
        query: Search query
        user_id: User ID

    Returns:
        Agent's response string (not a list)
    """
    try:
        return retrieve_documents_agentic(query, user_id=user_id)
    except Exception as e:
        logger.error(f"Agentic retrieval failed: {e}")
        return "Error during agentic document retrieval."


def retrieve_documents_simple_only(query: str, user_id: str, k: int = 3) -> str:
    """
    Retrieve documents using ONLY keyword matching (no LLM reasoning).

    Simple and fast fallback that doesn't require LLM.

    Args:
        query: Search query
        user_id: User ID
        k: Number of sections to retrieve

    Returns:
        Formatted content string (not a list)
    """
    try:
        return retrieve_documents_simple(query, k=k, user_id=user_id)
    except Exception as e:
        logger.error(f"Simple retrieval failed: {e}")
        return "Error during document retrieval."


def add_documents(file_paths: list[str], user_id: str, metadatas: list[dict] | None = None) -> None:
    """
    Index documents with PageIndex.

    Args:
        file_paths: List of document file paths to index (PDFs or Markdown)
        user_id: User ID
        metadatas: Optional metadata dicts (currently unused by PageIndex)
    """
    if not file_paths:
        logger.warning("No file paths provided for indexing")
        return

    indexed_count = 0
    for file_path in file_paths:
        try:
            doc_id = index_document(file_path, user_id)
            logger.info(f"Indexed document: {file_path} (doc_id: {doc_id})")
            indexed_count += 1
        except Exception as e:
            logger.error(f"Failed to index document {file_path}: {e}")

    logger.info(f"Successfully indexed {indexed_count}/{len(file_paths)} documents")


def list_documents(user_id: str) -> list[dict]:
    """
    List all indexed documents.

    Args:
        user_id: User ID

    Returns:
        List of document info dicts
    """
    try:
        return list_indexed_documents(user_id)
    except Exception as e:
        logger.error(f"Failed to list documents: {e}")
        return []


def get_vectorstore(user_id: str):
    """
    Compatibility stub for existing code that might reference vectorstore.

    Args:
        user_id: User ID

    Returns:
        PageIndex client
    """
    return get_pageindex_client(user_id)
