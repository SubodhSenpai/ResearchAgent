from typing import TypedDict, List, Optional, Annotated
import operator

class ResearchState(TypedDict):
    query: str                          # Original user question
    plan: List[str]                     # Supervisor's research plan
    search_results: List[dict]          # Raw search results
    documents: List[dict]               # Retrieved RAG documents
    analysis: Optional[str]             # Analyst's synthesis
    critique: Optional[str]             # Critic's feedback
    final_answer: Optional[str]         # Writer's output
    messages: Annotated[List, operator.add] # FUll agent message log
    iteration: int                      #prevent infinite loops
    quality_score: float                #critic's score (0-1)