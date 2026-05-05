from fastapi import FastAPI, HTTPExecption
from pydantic import BaseModel
from graph.graph_builder import build_research_graph
from graph.state import ResearchState


app = FastAPI(title='AI Research Assistant', version='1.0.0')
_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_research_graph()
    return _graph

class ResearchRequest(BaseModel):
    query: str
    max_iterations: int = 5

class ResearchResponse(BaseModel):
    answer: str
    messages: list[str]
    quality_score: float

@app.post('/research', response_model=ResearchResponse)
async def research(request: ResearchRequest):
    if not request.query.strip():
        raise HTTPExecption(status_code=400, detail='Query cannot be empty')

    initial_state = ResearchState(
        query=request.query,
        plan=[],
        search_results=[],
        documents=[],
        analysis=None,
        critique=None,
        final_answer=None,
        messages=[],
        iteration=0,
        quality_score=0.0
    )

    result = get_graph().invoke(initial_state)
    return ResearchResponse(
        answer = result.get('final_anser', 'No answer generated'),
        messages = result.get('messages', []),
        quality_score=result.get('quality_score', 0.0)
    )

@app.get('/health')
async def health():
    return {'status': 'ok', 'version': '1.0.0'}