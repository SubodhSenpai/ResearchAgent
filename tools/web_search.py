from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_google_genai import ChatGoogleGenerativeAI
from config.settings import settings
import os

os.environ['TAVILY_API_KEY'] = settings.tavily_api_key
os.environ['GOOGLE_API_KEY'] = settings.google_api_key

def search_web(query: str, max_results: int = 5) -> list[dict]:
    '''
        Search the web using Tavily. Returns list of result dicts.
        Each dict has: url, content, title.
    '''
    # tool = TavilySearchResults(max_results=max_results)
    tool = ChatGoogleGenerativeAI(model = settings.model_name)
    model_with_search = tool.bind_tools([{"google_search": {}}])
    results = model_with_search.invoke(query)
    return results.content_blocks if isinstance(results, list) else []