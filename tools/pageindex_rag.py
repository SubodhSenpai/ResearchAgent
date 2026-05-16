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

    # --- EORA SPRINT 1: Populate Evidence Graph ---
    try:
        from tools.evidence_graph import EvidenceGraph
        from agents.base_agent import BaseAgent
        import uuid
        import json

        # Get workspace path from settings
        workspace_path = Path(settings.pageindex_workspace) / user_id
        graph = EvidenceGraph(str(workspace_path))
        
        # Add Document Node
        graph.add_node(doc_id, "Document", file_path_obj.name, metadata={"path": str(file_path_obj)})
        
        # Extract Structure and Claims
        structure = client.get_document_structure(doc_id)
        temp_llm = BaseAgent("Extractor", "").llm
        
        # Sample text for claim extraction (first few pages)
        sample_text = client.get_page_content(doc_id, "1-3")
        
        extraction_prompt = f"""Extract 3-5 key entities and 3-5 atomic claims from this text.
        Text: {sample_text[:2000]}
        Output ONLY a JSON object with keys "entities" and "claims" (list of strings)."""
        
        response = temp_llm.invoke(extraction_prompt)
        match = re.search(r'\{.*\}', response.content, re.DOTALL)
        if match:
            data = json.loads(match.group())
            
            for ent in data.get('entities', []):
                ent_id = f"ent_{uuid.uuid4().hex[:8]}"
                graph.add_node(ent_id, "Entity", ent)
                graph.add_edge(doc_id, ent_id, "Mentions")
                
            for claim in data.get('claims', []):
                claim_id = f"claim_{uuid.uuid4().hex[:8]}"
                graph.add_node(claim_id, "Claim", claim, content=claim)
                graph.add_edge(doc_id, claim_id, "Supports")
                
        logger.info(f"Populated evidence graph for doc {doc_id}")
    except Exception as e:
        logger.warning(f"Failed to populate evidence graph: {e}")

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
        # Check if the OpenAI Agents SDK is actually installed and not just our local 'agents' folder
        import importlib.util
        spec = importlib.util.find_spec("agents")
        if spec is None or "site-packages" not in str(spec.origin):
            # If not in site-packages, it's likely our local folder or missing
            return retrieve_documents_simple(query, [selected_doc_id], user_id=user_id)

        from agents import Agent, Runner, function_tool
        import asyncio
        import concurrent.futures

        system_prompt = """You are PageIndex, a document context assembly expert.
        Your goal is to build a COHERENT EVIDENCE GRAPH, not just find isolated facts.

        STRATEGY:
        1. Call get_document() to understand the document's scope.
        2. Call get_document_structure() to find relevant sections.
        3. Call get_page_content() to fetch evidence.
        4. RECONSTRUCTION: If a snippet ends mid-sentence or mid-thought, fetch the next page immediately.
        5. CONTEXT ASSEMBLY: Always ensure you have the heading and surrounding context for any data point.

        Answer based only on tool output. Be concise. Cite page numbers explicitly."""

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


# ── Enhanced Nuanced Grader Prompt ───────────────────
RAG_GRADER_PROMPT = """You are an elite research analyst evaluating document evidence.
Evaluate the following document snippet in relation to the user's query.

Query: {query}
Snippet: {snippet}

Output a JSON object with these EXACT keys:
1. "relevance_score": (int 0-10) How directly this answers the query.
2. "is_fragment": (bool) True if it starts or ends mid-sentence/mid-thought.
3. "dependency": (string) "None", "Previous" (needs context before), "Next" (needs context after), or "Both".
4. "content_type": (string) "Fact", "Data/Table", "Analysis", or "Noise".
5. "reasoning": (string) 1-sentence explanation of the score.

Output ONLY the JSON object."""

def grade_snippet_nuanced(llm, query, snippet):
    """Performs nuanced multi-dimensional grading of a RAG snippet."""
    try:
        from langchain_core.output_parsers import JsonOutputParser
        parser = JsonOutputParser()
        prompt = RAG_GRADER_PROMPT.format(query=query, snippet=snippet)
        response = llm.invoke(prompt)
        # Attempt to parse JSON
        import json
        import re
        content = response.content
        # Find JSON block if it exists
        match = re.search(r'\{.*\}', content, re.DOTALL)
        if match:
            return json.loads(match.group())
        return None
    except Exception as e:
        logger.warning(f"Nuanced grading failed: {e}")
        return None


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
    # Use a set to avoid duplicate pages for the same doc
    processed_pages = set()

    for doc_id, doc_info in search_docs.items():
        try:
            structure_json = get_document_structure(doc_id, user_id)
            structure = json.loads(structure_json)
            doc_name = doc_info.get('doc_name', 'Unknown')
            doc_desc = doc_info.get('doc_description', '').lower()

            # 1. Search structure titles
            sections = _extract_sections_from_structure(structure, query, k)

            # 2. Fallback: If no good title matches, check doc description
            if not sections or max(s.get('score', 0) for s in sections) < 4:
                query_lower = query.lower()
                if any(word in doc_desc for word in set(query_lower.split()) if len(word) > 3):
                    logger.info(f"Fallback: Query matches doc_description for {doc_name}. Returning first few pages.")
                    # Add first page as a fallback result
                    sections.append({'pages': '1', 'title': 'Introduction / Document Start', 'score': 5})

            for section in sections:
                pages_str = section['pages']
                if f"{doc_id}_{pages_str}" in processed_pages:
                    continue
                
                try:
                    # 1. Fetch the raw snippet
                    content = retrieve_page_content(doc_id, pages_str, user_id)
                    
                    # 2. Nuanced Grading
                    # Use LLM directly instead of abstract BaseAgent
                    from langchain_google_genai import ChatGoogleGenerativeAI
                    from config.settings import settings
                    temp_llm = ChatGoogleGenerativeAI(
                        model=settings.model_name,
                        google_api_key=settings.gemini_api_key or None
                    )
                    grade = grade_snippet_nuanced(temp_llm, query, content)
                    
                    # Heuristic score if LLM grading fails
                    score = grade.get('relevance_score', 0) if grade else section.get('score', 0)
                    
                    # 3. Neighbor Expansion (Highest ROI Upgrade)
                    # If it's a fragment or has high relevance, fetch neighbors
                    if score >= 6 or (grade and (grade.get('is_fragment') or grade.get('dependency') != "None")):
                        try:
                            # Parse pages_str to handle ranges or lists
                            if '-' in pages_str:
                                start_page = int(pages_str.split('-')[0])
                                neighbor_pages = f"{max(1, start_page-1)}-{start_page+2}"
                            else:
                                curr_page = int(pages_str.split(',')[0])
                                neighbor_pages = f"{max(1, curr_page-1)}-{curr_page+1}"
                                
                            logger.info(f"Expanding context for {doc_id} to pages {neighbor_pages}")
                            content = retrieve_page_content(doc_id, neighbor_pages, user_id)
                            pages_str = neighbor_pages
                        except Exception:
                            pass # Fallback to original content
                    
                    results.append({
                        'doc_id': doc_id,
                        'doc_name': doc_name,
                        'pages': pages_str,
                        'title': section.get('title', ''),
                        'content': content,
                        'relevance_score': score,
                        'grade': grade
                    })
                    processed_pages.add(f"{doc_id}_{pages_str}")

                except Exception as e:
                    logger.warning(f"Failed to retrieve {doc_id} pages {pages_str}: {e}")

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
    # Filter stopwords to focus on core concepts
    stopwords = {'return', 'full', 'section', 'exactly', 'structured', 'document', 'what', 'where', 'how', 'the', 'and', 'for'}
    query_words = set(w for w in query_lower.split() if len(w) > 2 and w not in stopwords)

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
            # Exact phrase match (Highest)
            if query_lower in title_lower:
                score += 15
            
            # Key term matches
            matches = 0
            for word in query_words:
                if word in title_lower:
                    matches += 1
                    # Boost for core conceptual terms
                    if word in ['memory', 'layer', 'htn', 'architecture', 'strategy']:
                        score += 5
                    else:
                        score += 2
            
            # Bonus for multiple keyword matches
            if matches >= 2:
                score += 5

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
        grade = result.get('grade', {})
        reasoning = grade.get('reasoning', 'No reasoning available')
        content_type = grade.get('content_type', 'General')
        
        formatted.append(
            f"--- EVIDENCE SOURCE {i} ---\n"
            f"Document: {doc_name}\n"
            f"Section: {section_title} (pages {pages})\n"
            f"Relevance Score: {score:.2f}/10\n"
            f"Content Type: {content_type}\n"
            f"AI Reasoning: {reasoning}\n"
            f"Content:\n{content}\n"
        )

    return "\n\n".join(formatted)
