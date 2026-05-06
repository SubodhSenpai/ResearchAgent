import json
import logging
from collections.abc import Iterator
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from graph.graph_builder import build_research_graph
from graph.state import ResearchState

logger = logging.getLogger(__name__)

app = FastAPI(title="AI Research Assistant", version="1.0.0")

# Enable CORS for Streamlit Cloud and local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
_graph = None

# Track active research sessions for interrupt support
_active_sessions: dict[str, dict] = {}

# User-facing labels for graph node ids (see graph_builder.py)
NODE_LABELS: dict[str, str] = {
    "memory_check": "Memory (cache check)",
    "supervisor": "Supervisor",
    "researcher": "Researcher",
    "analyst": "Analyst",
    "critic": "Critic",
    "writer": "Writer",
    "save_memory": "Saving session",
    "interrupt_check": "Processing interrupt",
}


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_research_graph()
    return _graph


def _build_initial_state(query: str, max_iterations: int, session_id: Optional[str] = None) -> ResearchState:
    return {
        "query": query,
        "plan": [],
        "search_results": [],
        "documents": [],
        "analysis": None,
        "critique": None,
        "final_answer": None,
        "messages": [],
        "iteration": 0,
        "max_iterations": max_iterations,
        "quality_score": 0.0,
        "interrupt_requested": False,
        "error": None,
    }


class ResearchRequest(BaseModel):
    query: str
    max_iterations: int = 5
    session_id: Optional[str] = None


class ResearchResponse(BaseModel):
    answer: str
    messages: list[str]
    quality_score: float
    interrupted: bool = False
    error: Optional[str] = None


class InterruptRequest(BaseModel):
    session_id: str


def _research_ndjson_lines(initial: ResearchState, session_id: Optional[str] = None) -> Iterator[str]:
    """
    Stream one JSON object per line: agent steps, then result or error.
    Supports interrupt requests during streaming.
    """
    graph = get_graph()
    final: dict = dict(initial)

    try:
        # Register session
        if session_id:
            _active_sessions[session_id] = {"state": initial, "active": True}

        for step in graph.stream(initial, stream_mode="updates"):
            # Check for interrupt request
            if session_id and session_id in _active_sessions:
                if _active_sessions[session_id].get("interrupt_requested"):
                    logger.info(f"Interrupt signal received for session {session_id}")
                    final["interrupt_requested"] = True

            for node_name, node_out in step.items():
                if not isinstance(node_out, dict):
                    continue

                # Update session state
                if session_id:
                    _active_sessions[session_id]["state"] = node_out

                label = NODE_LABELS.get(node_name, node_name.replace("_", " ").title())
                yield json.dumps(
                    {
                        "type": "agent",
                        "node": node_name,
                        "label": label,
                        "iteration": node_out.get("iteration", 0),
                    },
                    ensure_ascii=False,
                ) + "\n"
                final = node_out

        answer = final.get("final_answer") or "No answer generated."
        messages = final.get("messages") or []
        if not isinstance(messages, list):
            messages = [str(messages)]
        quality_score = float(final.get("quality_score") or 0.0)
        interrupted = final.get("interrupt_requested", False)
        error = final.get("error")

        yield (
            json.dumps(
                {
                    "type": "result",
                    "answer": answer,
                    "messages": messages,
                    "quality_score": quality_score,
                    "interrupted": interrupted,
                    "error": error,
                },
                ensure_ascii=False,
            )
            + "\n"
        )
    except Exception as e:
        logger.error(f"Research error: {str(e)}")
        yield json.dumps(
            {"type": "error", "detail": str(e)},
            ensure_ascii=False,
        ) + "\n"
    finally:
        # Clean up session
        if session_id and session_id in _active_sessions:
            _active_sessions[session_id]["active"] = False


@app.post("/research", response_model=ResearchResponse)
async def research(request: ResearchRequest):
    """Run research synchronously."""
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    initial_state = _build_initial_state(request.query, request.max_iterations, request.session_id)
    result = get_graph().invoke(initial_state)

    return ResearchResponse(
        answer=result.get("final_answer") or "No answer generated.",
        messages=result.get("messages") or [],
        quality_score=float(result.get("quality_score") or 0.0),
        interrupted=result.get("interrupt_requested", False),
        error=result.get("error"),
    )


@app.post("/research/stream")
async def research_stream(request: ResearchRequest):
    """Stream research with NDJSON format and interrupt support."""
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    initial_state = _build_initial_state(request.query, request.max_iterations, request.session_id)

    return StreamingResponse(
        _research_ndjson_lines(initial_state, request.session_id),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/interrupt")
async def interrupt(request: InterruptRequest):
    """Send interrupt signal to a running research session."""
    if request.session_id not in _active_sessions:
        raise HTTPException(status_code=404, detail=f"Session {request.session_id} not found")

    session = _active_sessions[request.session_id]
    if not session.get("active"):
        raise HTTPException(status_code=400, detail=f"Session {request.session_id} is not active")

    session["interrupt_requested"] = True
    logger.info(f"Interrupt requested for session {request.session_id}")

    return {
        "status": "interrupt_scheduled",
        "session_id": request.session_id,
        "message": "Interrupt signal will take effect at next decision point",
    }


@app.get("/sessions")
async def list_sessions():
    """List all active research sessions."""
    active = {sid: v for sid, v in _active_sessions.items() if v.get("active")}
    return {
        "active_count": len(active),
        "sessions": [
            {
                "session_id": sid,
                "query": v["state"].get("query", "")[:100],
                "iteration": v["state"].get("iteration", 0),
            }
            for sid, v in active.items()
        ],
    }


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}
