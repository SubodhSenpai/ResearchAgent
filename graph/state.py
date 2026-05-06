from typing import TypedDict, List, Optional

class ResearchState(TypedDict):
    query: str                          # Original user question
    plan: List[str]                     # Supervisor's research plan
    search_results: List[dict]          # Raw search results
    documents: List[dict]               # Retrieved RAG documents
    analysis: Optional[str]             # Analyst's synthesis
    critique: Optional[str]             # Critic's feedback
    final_answer: Optional[str]         # Writer's output
    messages: List[str]                 # Agent message log
    iteration: int                      # supervisor visits (incremented in supervisor node)
    max_iterations: int                 # cap supervisor cycles before forcing writer
    quality_score: float                # critic's score (0-1)
    interrupt_requested: bool           # Flag to gracefully stop execution
    error: Optional[str]                # Error message if execution failed