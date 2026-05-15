import os
from typing import Any
import json
import logging
from langchain_tavily import TavilySearch
from config.settings import settings

logger = logging.getLogger(__name__)

if settings.tavily_api_key:
    os.environ["TAVILY_API_KEY"] = settings.tavily_api_key


def search_web(query: str, max_results: int = 5) -> list[dict[str, Any]]:
    """
    Web search using Tavily with advanced depth configuration.
    Returns a list of result dicts with content, url, and title keys.
    """
    tool = TavilySearch(
        max_results=max_results,
        search_depth="advanced",
    )

    try:
        raw_output = tool.invoke(query)

        if isinstance(raw_output, str):
            try:
                parsed_data = json.loads(raw_output)
            except json.JSONDecodeError:
                return [{"content": raw_output, "url": "", "title": ""}]
        else:
            parsed_data = raw_output

        if isinstance(parsed_data, dict):
            return parsed_data.get("results", [parsed_data])

        if isinstance(parsed_data, list):
            return parsed_data

        return [{"content": str(parsed_data), "url": "", "title": ""}]

    except Exception as e:
        logger.error(f"Web search error for query '{query[:60]}': {e}")
        return [
            {
                "content": f"Error performing web search: {str(e)}",
                "url": "",
                "title": "Error"
            }
        ]


def search_web_multi(queries: list[str], max_results_per_query: int = 5) -> tuple[list[dict], list[dict]]:
    """
    Run multiple web searches and return deduplicated results + source tracking.

    Args:
        queries: List of search queries to execute
        max_results_per_query: Max results per individual query

    Returns:
        Tuple of (all_results, source_urls) where source_urls tracks
        unique URLs with their titles and snippets for citation.
    """
    all_results = []
    source_urls = []
    seen_urls = set()

    for query in queries:
        logger.info(f"Multi-search: querying '{query[:80]}'")
        results = search_web(query, max_results=max_results_per_query)

        for r in results:
            all_results.append(r)

            # Track unique source URLs for citations
            url = r.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                source_urls.append({
                    "url": url,
                    "title": r.get("title", ""),
                    "snippet": str(r.get("content", ""))[:200],
                    "query": query,
                })

    logger.info(f"Multi-search complete: {len(all_results)} results, {len(source_urls)} unique sources from {len(queries)} queries")
    return all_results, source_urls
