"""
PageIndex RAG Implementation with Local Self-Hosted Integration

Uses the local PageIndex repo for vectorless, reasoning-based document indexing
and retrieval. No external API key required - workspace-based persistence.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent / "PageIndex"))

from pageindex import PageIndexClient
from config.settings import settings

logger = logging.getLogger(__name__)

_pageindex_clients: dict[str, PageIndexClient] = {}


def get_pageindex_client(user_id: str) -> PageIndexClient:
    """
    Get or create a PageIndex client with workspace persistence.

    Args:
        user_id: The ID of the user

    Returns:
        PageIndexClient instance with workspace configured
    """
    global _pageindex_clients
    if user_id not in _pageindex_clients:
        try:
            workspace = Path(settings.pageindex_workspace) / user_id
            model = settings.pageindex_model or settings.model_name

            if not model:
                raise ValueError("PAGEINDEX_MODEL or MODEL_NAME must be configured")

            client = PageIndexClient(
                workspace=str(workspace),
                model=model
            )
            logger.info(f"Initialized PageIndex client for user {user_id} at {workspace}")
            _pageindex_clients[user_id] = client
        except Exception as e:
            logger.error(f"Failed to initialize PageIndex client: {e}")
            raise

    return _pageindex_clients[user_id]


def index_document(file_path: str, user_id: str) -> str:
    """
    Index a document (PDF or Markdown) with PageIndex.

    Args:
        file_path: Path to the document to index
        user_id: User ID

    Returns:
        Document ID (doc_id) for future retrieval
    """
    import asyncio
    import concurrent.futures
    import threading

    client = get_pageindex_client(user_id)
    file_path_obj = Path(file_path)

    if not file_path_obj.exists():
        raise FileNotFoundError(f"Document not found: {file_path}")

    try:
        loop = asyncio.get_running_loop()
        is_running_loop = True
    except RuntimeError:
        is_running_loop = False

    if is_running_loop:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            doc_id = pool.submit(client.index, str(file_path_obj)).result()
    else:
        doc_id = client.index(str(file_path_obj))

    logger.info(f"Indexed document: {file_path_obj.name} (doc_id: {doc_id})")
    return doc_id


def get_document_structure(doc_id: str, user_id: str) -> str:
    """
    Get the hierarchical tree structure of an indexed document as JSON string.

    Args:
        doc_id: The document ID
        user_id: User ID

    Returns:
        JSON string representing the document's tree structure
    """
    client = get_pageindex_client(user_id)
    return client.get_document_structure(doc_id)


def get_document_metadata(doc_id: str, user_id: str) -> str:
    """
    Get metadata about a document (status, page count, etc.).

    Args:
        doc_id: The document ID
        user_id: User ID

    Returns:
        Metadata string
    """
    client = get_pageindex_client(user_id)
    return client.get_document(doc_id)


def retrieve_page_content(doc_id: str, pages: str, user_id: str) -> str:
    """
    Retrieve text content from specific pages of an indexed document.

    Args:
        doc_id: The document ID
        pages: Page range or specific pages (e.g., '5-7', '3,8', '12')
        user_id: User ID

    Returns:
        Text content from the requested pages
    """
    client = get_pageindex_client(user_id)
    return client.get_page_content(doc_id, pages)


def retrieve_documents_agentic(query: str, doc_ids: Optional[list[str]] = None, user_id: str = None) -> str:
    """
    Retrieve documents using agentic LLM reasoning with PageIndex tree search.

    Uses PageIndex tools with agentic reasoning:
    1. Call get_document() to check page counts
    2. Call get_document_structure() to understand hierarchy
    3. Reason about which pages are relevant
    4. Call get_page_content() with specific page ranges
    5. Return structured answer with citations

    Args:
        query: The search query
        doc_ids: Specific document IDs to search in (searches all if None)
        user_id: User ID to scope retrieval

    Returns:
        Agent's response with retrieved content and citations
    """
    if not user_id:
        return "Error: User ID required for document retrieval."

    client = get_pageindex_client(user_id)

    if not client.documents:
        logger.warning("No documents indexed in PageIndex")
        return "No documents available in the knowledge base."

    search_docs = {did: client.documents[did] for did in (doc_ids or client.documents.keys())}

    if not search_docs:
        return "No documents available for retrieval."

    selected_doc_id = list(search_docs.keys())[0]

    try:
        from agents import Agent, Runner, function_tool
        import asyncio
        import concurrent.futures

        system_prompt = """You are PageIndex, a document QA assistant.
TOOL USE:
- Call get_document() first to confirm status and page/line count.
- Call get_document_structure() to identify relevant page ranges.
- Call get_page_content(pages="5-7") with tight ranges; never fetch the whole document.
- Before each tool call, output one short sentence explaining the reason.
Answer based only on tool output. Be concise."""

        @function_tool
        def get_document() -> str:
            """Get document metadata: status, page count, name, and description."""
            return get_document_metadata(selected_doc_id, user_id)

        @function_tool
        def get_document_structure() -> str:
            """Get the document's full tree structure to find relevant sections."""
            return get_document_structure(selected_doc_id, user_id)

        @function_tool
        def get_page_content(pages: str) -> str:
            """
            Get the text content of specific pages or line numbers.
            Use tight ranges: e.g. '5-7' for pages 5 to 7, '3,8' for pages 3 and 8.
            """
            if not pages or not isinstance(pages, str):
                raise ValueError("pages parameter required as string (e.g., '5-7')")
            return retrieve_page_content(selected_doc_id, pages, user_id)

        agent = Agent(
            name="PageIndex",
            instructions=system_prompt,
            tools=[get_document, get_document_structure, get_page_content],
            model=client.model,
        )

        async def _run_agent():
            streamed_run = Runner.run_streamed(agent, query)
            output_text = ""

            async for event in streamed_run.stream_events():
                try:
                    if hasattr(event, 'item') and hasattr(event.item, 'type'):
                        if event.item.type == "tool_call_output_item":
                            output_text += str(event.item.output) + "\n"
                except Exception:
                    pass

            final_output = streamed_run.final_output
            return str(final_output) if final_output else output_text

        try:
            loop = asyncio.get_running_loop()
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                response = pool.submit(asyncio.run, _run_agent()).result()
        except RuntimeError:
            response = asyncio.run(_run_agent())

        logger.info(f"Agentic retrieval completed for query: {query[:60]}")
        return response

    except ImportError as e:
        logger.warning(f"OpenAI Agents SDK not available ({e}), falling back to simple retrieval")
        return retrieve_documents_simple(query, [selected_doc_id], user_id=user_id)
    except Exception as e:
        logger.error(f"Agentic retrieval failed: {e}")
        return retrieve_documents_simple(query, [selected_doc_id], user_id=user_id)


def retrieve_documents_simple(query: str, doc_ids: Optional[list[str]] = None, k: int = 3, user_id: str = None) -> str:
    """
    Simple fallback retrieval using keyword matching over document structure.

    Args:
        query: The search query
        doc_ids: Specific document IDs to search in
        k: Number of sections to retrieve
        user_id: User ID

    Returns:
        Formatted content string
    """
    if not user_id:
        return "Error: User ID required for document retrieval."

    client = get_pageindex_client(user_id)

    if not client.documents:
        return "No documents available."

    search_docs = {did: client.documents[did] for did in (doc_ids or client.documents.keys())}

    results = []

    for doc_id, doc_info in search_docs.items():
        try:
            structure_json = get_document_structure(doc_id, user_id)
            structure = json.loads(structure_json)
            doc_name = doc_info.get('doc_name', 'Unknown')

            sections = _extract_sections_from_structure(structure, query, k)

            for section in sections:
                try:
                    content = retrieve_page_content(doc_id, section['pages'], user_id)
                    results.append({
                        'doc_id': doc_id,
                        'doc_name': doc_name,
                        'pages': section['pages'],
                        'title': section.get('title', ''),
                        'content': content,
                        'score': section.get('score', 0.0)
                    })
                except Exception as e:
                    logger.warning(f"Failed to retrieve {doc_id} pages {section['pages']}: {e}")

        except Exception as e:
            logger.warning(f"Failed to process document {doc_id}: {e}")

    return format_retrieval_results(results) if results else "No relevant sections found."


def retrieve_documents(query: str, doc_ids: Optional[list[str]] = None, k: int = 3, user_id: str = None) -> list[str]:
    """
    Main retrieval function - tries agentic first, falls back to simple.

    Returns list of content strings for backward compatibility with existing code.

    Args:
        query: Search query
        doc_ids: Specific document IDs
        k: Number of results
        user_id: User ID

    Returns:
        List of content strings
    """
    if not user_id:
        return ["Error: User ID required for document retrieval."]

    try:
        agentic_result = retrieve_documents_agentic(query, doc_ids, user_id=user_id)

        if agentic_result and agentic_result != "No documents available in the knowledge base.":
            return [agentic_result]

    except Exception as e:
        logger.warning(f"Agentic retrieval failed, using simple retrieval: {e}")

    simple_result = retrieve_documents_simple(query, doc_ids, k, user_id=user_id)
    return [simple_result] if simple_result else []


def _extract_sections_from_structure(structure: dict, query: str, k: int = 3) -> list[dict]:
    """
    Extract relevant sections from document structure (simple keyword matching).

    Args:
        structure: Document structure dictionary
        query: Search query
        k: Number of sections to return

    Returns:
        List of section info with page ranges
    """
    query_lower = query.lower()
    query_words = set(w for w in query_lower.split() if len(w) > 2)

    sections = []

    def traverse(node: dict):
        """Recursively traverse structure tree."""
        if not isinstance(node, dict):
            return

        page_num = node.get('page_num') or node.get('start_index')
        title = node.get('title', '')

        score = 0.0
        if title:
            title_lower = title.lower()
            if query_lower in title_lower:
                score += 10
            for word in query_words:
                if word in title_lower:
                    score += 2

        if score > 0:
            sections.append({
                'pages': str(page_num),
                'title': title,
                'score': score
            })

        for child in node.get('nodes', []) or node.get('children', []):
            traverse(child)

    if isinstance(structure, list):
        for item in structure:
            traverse(item)
    else:
        traverse(structure)

    sections.sort(key=lambda x: x['score'], reverse=True)
    return sections[:k]


def list_indexed_documents(user_id: str) -> list[dict]:
    """
    List all indexed documents.

    Args:
        user_id: User ID

    Returns:
        List of document info dicts with 'doc_id', 'doc_name', 'page_count'
    """
    client = get_pageindex_client(user_id)
    documents = []

    for doc_id, doc_info in client.documents.items():
        doc_entry = {
            'doc_id': doc_id,
            'doc_name': doc_info.get('doc_name', ''),
            'type': doc_info.get('type', 'unknown'),
        }
        if doc_info.get('type') == 'pdf':
            doc_entry['page_count'] = doc_info.get('page_count', 0)
        elif doc_info.get('type') == 'md':
            doc_entry['line_count'] = doc_info.get('line_count', 0)

        documents.append(doc_entry)

    return documents


def format_retrieval_results(results: list[dict]) -> str:
    """
    Format PageIndex retrieval results for LLM consumption.

    Args:
        results: List of retrieval results from retrieve_documents()

    Returns:
        Formatted string suitable for passing to LLM
    """
    if not results:
        return "No documents available."

    formatted = []
    for i, result in enumerate(results, 1):
        doc_name = result.get('doc_name', 'Unknown')
        pages = result.get('pages', '?')
        title = result.get('title', '')
        content = result.get('content', '')
        score = result.get('relevance_score', 0.0)

        section_title = f"{title}" if title else f"Pages {pages}"
        formatted.append(
            f"[Document {i}] {doc_name} — {section_title} (pages {pages}, score: {score:.2f})\n"
            f"Content: {content[:500]}..."
        )

    return "\n\n".join(formatted)
