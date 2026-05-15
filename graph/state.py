from typing import TypedDict, List, Optional


class ResearchState(TypedDict):
    # ━━━ SESSION & USER CONTEXT (Unified Source of Truth) ━━━━━━━━━━━━━━━
    session_id: str                     # Unique session identifier (links to database)
    user_id: str                        # Which user is executing (for memory isolation)
    jwt_token: str                      # Authentication token for this session
    timestamp: str                      # Session start time (ISO format)
    user_preferences: dict              # User's settings (optional)

    # ━━━ RESEARCH CONTENT ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    query: str                          # Original user question
    plan: List[str]                     # Supervisor's research plan
    sub_queries: List[str]              # Decomposed sub-queries for multi-angle search
    chat_history: List[dict]            # Previous turns in this session
    search_results: List[dict]          # Raw search results
    source_urls: List[dict]             # Tracked URLs for citations (title, url, snippet)
    documents: List[str]                # Retrieved RAG documents
    analysis: Optional[str]             # Analyst's synthesis
    critique: Optional[str]             # Critic's feedback
    research_gaps: List[str]            # Gaps identified by critic for follow-up research
    final_answer: Optional[str]         # Writer's output

    # ━━━ EXECUTION CONTROL & METADATA ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    messages: List[str]                 # Agent message log
    _next: Optional[str]               # Next agent routing hint (set by supervisor)
    _critic_recommendation: Optional[str]  # Critic's recommendation (needs_more_research|needs_reanalysis|ready_to_write)
    iteration: int                      # supervisor visits (incremented in supervisor node)
    max_iterations: int                 # cap supervisor cycles before forcing writer
    quality_score: float                # critic's score (0-1)
    interrupt_requested: bool           # Flag to gracefully stop execution
    error: Optional[str]               # Error message if execution failed