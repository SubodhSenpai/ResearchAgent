from langchain_community.tools.tavily_search import TavilySearchResults
from config.settings import settings
import os

os.environ['TAVILY_API_KEY'] = settings.tavily_api_key

def search_web(query: str, max_results: int = 5) -> list[dict]:
    '''
        Search the web using Tavily. Returns list of result dicts.
        Each dict has: url, content, title.
    '''
    tool = TavilySearchResults(max_results=max_results)
    results = tool.invoke(query)
    return results if isinstance(results, list) else []