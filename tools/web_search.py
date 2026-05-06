import os
from typing import Any

from langchain_community.tools.tavily_search import TavilySearchResults

from config.settings import settings

if settings.tavily_api_key:
    os.environ["TAVILY_API_KEY"] = settings.tavily_api_key
if settings.google_api_key:
    os.environ["GOOGLE_API_KEY"] = settings.google_api_key


def search_web(query: str, max_results: int = 5) -> list[dict[str, Any]]:
    """
    Web search: Gemini path uses Google Generative AI with search grounding.
    OpenAI path uses Tavily (requires TAVILY_API_KEY).
    """
    if settings.uses_google_llm():
        from langchain_google_genai import ChatGoogleGenerativeAI

        tool = ChatGoogleGenerativeAI(
            model=settings.model_name,
            google_api_key=settings.google_api_key or None,
        )
        model_with_search = tool.bind_tools([{"google_search": {}}])
        msg = model_with_search.invoke(query)
        blocks = getattr(msg, "content_blocks", None)
        if blocks:
            out: list[dict[str, Any]] = []
            for b in blocks:
                if isinstance(b, dict):
                    out.append(b)
                else:
                    out.append({"content": str(b), "url": "", "title": ""})
            return out
        return [{"content": str(getattr(msg, "content", msg)), "url": "", "title": ""}]

    tool = TavilySearchResults(max_results=max_results)
    raw = tool.invoke({"query": query})
    if isinstance(raw, list):
        return raw
    return [{"content": str(raw), "url": "", "title": ""}]
