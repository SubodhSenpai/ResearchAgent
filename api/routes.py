import json
import logging
from collections.abc import Iterator
from contextlib import asynccontextmanager
from typing import Optional
from uuid import uuid4
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from sqlalchemy.orm import Session as DBSession
from pathlib import Path
import shutil
import os

from graph.graph_builder import build_research_graph
from graph.state import ResearchState
from auth.database import get_db, init_db, close_db
from auth.models import User, Session as DBSession_Model, UserDocument
from auth.schemas import MessageResponse
from api.middleware import get_current_user, verify_ownership, NormalizePathMiddleware
from api.auth_routes import router as auth_router
from memory.session_manager import SessionManager
from tools.pageindex_rag import index_document, list_indexed_documents

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app):
    """Initialize database on startup, close on shutdown."""
    if not init_db():
        logger.error("Failed to initialize database during startup")
    else:
        logger.info("Database initialized via lifespan startup")
    yield
    close_db()
    logger.info("Database closed via lifespan shutdown")


app = FastAPI(title="AI Research Assistant", version="1.0.0", lifespan=lifespan)

# CORS: browsers send Origin on cross-origin requests; preflight OPTIONS must echo it back.
_DEFAULT_CORS_ORIGINS = [
    "https://research-agent-eight-rho.vercel.app",
    "https://research-agent-six.vercel.app",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
_extra_cors = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
_cors_origins = list(dict.fromkeys(_DEFAULT_CORS_ORIGINS + _extra_cors))

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    # Production + Vercel preview URLs (e.g. research-agent-git-main-….vercel.app)
    allow_origin_regex=r"https://research-agent[-a-z0-9.]*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Runs before routing; fixes //auth/login when API URL has a trailing slash
app.add_middleware(NormalizePathMiddleware)

# Include auth routes
app.include_router(auth_router)
_graph = None

# Track active research sessions for interrupt support
# NOTE: Session state is now part of ResearchState flowing through the graph
# This dict only tracks interrupt signals and is synchronized with graph execution
_active_sessions: dict[str, dict] = {}

# User-facing labels for graph node ids (see graph_builder.py)
NODE_LABELS: dict[str, str] = {
    "memory_check": "Memory (cache check)",
    "supervisor": "Supervisor",
    "researcher": "Researcher",
    "analyst": "Analyst",
    "critic": "Critic",
    "validator": "Evidence Auditor",
    "writer": "Writer",
    "save_memory": "Saving session",
    "interrupt_check": "Processing interrupt",
}


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_research_graph()
    return _graph


def _build_initial_state(
    query: str,
    session_id: str,
    user_id: str,
    jwt_token: str,
    max_iterations: int = 5,
    web_search_enabled: bool = True,
    chat_history: list = None
) -> ResearchState:
    from datetime import datetime

    return {
        # ━━━ SESSION & USER CONTEXT (Unified Source of Truth) ━━━━
        "session_id": session_id,
        "user_id": user_id,
        "jwt_token": jwt_token,
        "timestamp": datetime.utcnow().isoformat(),
        "user_preferences": {},

        # ━━━ RESEARCH CONTENT ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        "query": query,
        "plan": [],
        "sub_queries": [],
        "chat_history": chat_history or [],
        "search_results": [],
        "source_urls": [],
        "documents": [],
        "analysis": None,
        "critique": None,
        "research_gaps": [],
        "final_answer": None,

        # ━━━ EXECUTION CONTROL ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
        "messages": [],
        "_next": None,
        "_critic_recommendation": None,
        "iteration": 0,
        "max_iterations": max_iterations,
        "quality_score": 0.0,
        "web_search_enabled": web_search_enabled,
        "interrupt_requested": False,
        "error": None,
    }


class ResearchRequest(BaseModel):
    query: str
    max_iterations: int = 5
    web_search_enabled: bool = True


class ResearchStartResponse(BaseModel):
    session_id: str
    status: str
    created_at: str


class ResearchSessionResponse(BaseModel):
    session_id: str
    query: str
    final_answer: Optional[str]
    quality_score: float
    status: str
    created_at: str
    updated_at: str


class ResearchResponse(BaseModel):
    answer: str
    messages: list[str]
    quality_score: float
    interrupted: bool = False
    error: Optional[str] = None


class SessionListResponse(BaseModel):
    total: int
    sessions: list[ResearchSessionResponse]


class ChatHistoryItem(BaseModel):
    type: str
    content: str
    timestamp: str


class SessionHistoryResponse(BaseModel):
    session_id: str
    query: str
    messages: list[ChatHistoryItem]


class InterruptRequest(BaseModel):
    session_id: str


class DocumentResponse(BaseModel):
    document_id: str
    filename: str
    pageindex_doc_id: str
    status: str
    created_at: str


class DocumentListResponse(BaseModel):
    total: int
    documents: list[DocumentResponse]


class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    pageindex_doc_id: str
    status: str
    message: str


def _research_ndjson_lines(initial: ResearchState, db_session: DBSession = None) -> Iterator[str]:
    """
    Stream one JSON object per line: agent steps, then result or error.
    Supports interrupt requests during streaming.
    Session tracking is now unified in ResearchState.
    """
    from auth.database import SessionLocal

    if db_session is None:
        db_session = SessionLocal()

    graph = get_graph()
    session_id = initial["session_id"]
    user_id = initial["user_id"]
    final: dict = dict(initial)

    try:
        # Register session for interrupt tracking
        _active_sessions[session_id] = {"state": initial, "active": True}
        logger.info(f"Session {session_id} started for user {user_id}")

        for step in graph.stream(initial, stream_mode="updates"):
            # Check for interrupt request
            if session_id in _active_sessions:
                if _active_sessions[session_id].get("interrupt_requested"):
                    logger.info(f"Interrupt signal received for session {session_id}")
                    final["interrupt_requested"] = True

            for node_name, node_out in step.items():
                if not isinstance(node_out, dict):
                    continue

                # Update session state (unified state object)
                _active_sessions[session_id]["state"] = node_out

                label = NODE_LABELS.get(node_name, node_name.replace("_", " ").title())
                yield json.dumps(
                    {
                        "type": "agent",
                        "node": node_name,
                        "label": label,
                        "iteration": node_out.get("iteration", 0),
                        "completeness_score": node_out.get("completeness_score"),
                        "evidence_gaps": node_out.get("evidence_gaps"),
                        "contradictions": node_out.get("contradictions"),
                        "session_id": session_id,
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

        logger.info(f"Session {session_id} completed. Quality score: {quality_score}")

        # Save results to PostgreSQL
        if not interrupted:
            session_manager = SessionManager(db_session)
            session_manager.update_session_result(
                session_id=session_id,
                final_answer=answer,
                quality_score=quality_score,
                tokens_used=0,  # TODO: Calculate from LLM calls
            )
            # Save assistant answer to chat history
            session_manager.save_to_history(session_id, user_id, "assistant", answer)
            logger.info(f"Session {session_id} saved to database")

        yield (
            json.dumps(
                {
                    "type": "result",
                    "answer": answer,
                    "messages": messages,
                    "quality_score": quality_score,
                    "interrupted": interrupted,
                    "error": error,
                    "session_id": session_id,
                },
                ensure_ascii=False,
            )
            + "\n"
        )
    except Exception as e:
        logger.error(f"Research error in session {session_id}: {str(e)}")
        yield json.dumps(
            {"type": "error", "detail": str(e), "session_id": session_id},
            ensure_ascii=False,
        ) + "\n"
    finally:
        # Clean up session
        if session_id in _active_sessions:
            _active_sessions[session_id]["active"] = False
            logger.info(f"Session {session_id} cleaned up")

        # Close database session if we created it
        try:
            db_session.close()
        except Exception as e:
            logger.error(f"Error closing database session: {e}")


@app.post("/research/start", response_model=ResearchStartResponse)
async def research_start(
    request: ResearchRequest,
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """Start a new research session.

    Args:
        request: Research request with query and optional max_iterations
        current_user: Authenticated user from JWT
        db: Database session

    Returns:
        Session ID and status
    """
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    # Create session in database
    session_manager = SessionManager(db)
    session_id = session_manager.create_session(str(current_user.user_id), request.query)

    if not session_id:
        raise HTTPException(status_code=500, detail="Failed to create session")

    # Save initial user query to chat history
    session_manager.save_to_history(session_id, str(current_user.user_id), "user", request.query)

    # Note: web_search_enabled is currently handled in the stream call,
    # but we could store it in the session preferences if needed.

    logger.info(f"Research started. Session: {session_id}, User: {current_user.user_id}")
    return ResearchStartResponse(
        session_id=session_id,
        status="started",
        created_at=datetime.utcnow().isoformat(),
    )


@app.get("/research/{session_id}", response_model=ResearchSessionResponse)
async def get_research(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """Get research session details.

    Args:
        session_id: Session ID
        current_user: Authenticated user from JWT
        db: Database session

    Returns:
        Session details with results
    """
    session_manager = SessionManager(db)
    session = session_manager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Verify ownership
    if not verify_ownership(current_user.user_id, session.user_id):
        raise HTTPException(status_code=403, detail="Access denied")

    return ResearchSessionResponse(
        session_id=str(session.session_id),
        query=session.query,
        final_answer=session.final_answer,
        quality_score=session.quality_score,
        status=session.status,
        created_at=session.created_at.isoformat(),
        updated_at=session.updated_at.isoformat(),
    )


class StreamRequest(BaseModel):
    query: Optional[str] = None
    max_iterations: int = 5
    web_search_enabled: bool = True


@app.post("/research/{session_id}/stream")
async def research_stream(
    session_id: str,
    request: Optional[StreamRequest] = None,
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """Stream research execution with NDJSON format and interrupt support.

    Args:
        session_id: Session ID
        request: Optional stream request containing a new query for chat follow-ups
        current_user: Authenticated user from JWT
        db: Database session

    Returns:
        Server-Sent Events stream with research progress
    """
    session_manager = SessionManager(db)
    session = session_manager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Verify ownership
    if not verify_ownership(current_user.user_id, session.user_id):
        raise HTTPException(status_code=403, detail="Access denied")

    # Get chat history
    history_records = session_manager.get_session_history(session_id)
    chat_history = [{"role": h.message_type, "content": h.content} for h in history_records]

    # Determine query to use
    query_to_use = session.query
    if request and request.query and request.query.strip():
        new_query = request.query.strip()
        # If this is a follow-up, the previous answer should be in history.
        # But wait, we save to history after run.
        # Save the user's new query to history now.
        session_manager.save_to_history(session_id, str(current_user.user_id), "user", new_query)
        chat_history.append({"role": "user", "content": new_query})
        query_to_use = new_query

    # Get JWT from current request (note: would need to pass it through)
    # For now, we'll use a placeholder - in production, extract from request
    jwt_token = "token_from_request"

    # Initialize research state with session context
    initial_state = _build_initial_state(
        query=query_to_use,
        session_id=session_id,
        user_id=str(current_user.user_id),
        jwt_token=jwt_token,
        max_iterations=request.max_iterations if request else 5,
        web_search_enabled=request.web_search_enabled if request else True,
        chat_history=chat_history,
    )

    return StreamingResponse(
        _research_ndjson_lines(initial_state, db_session=db),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/research/{session_id}/interrupt", response_model=MessageResponse)
async def interrupt_research(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """Send interrupt signal to a running research session.

    Args:
        session_id: Session ID
        current_user: Authenticated user from JWT
        db: Database session

    Returns:
        Success message
    """
    session_manager = SessionManager(db)
    session = session_manager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Verify ownership
    if not verify_ownership(current_user.user_id, session.user_id):
        raise HTTPException(status_code=403, detail="Access denied")

    # Check if session is running
    if session_id not in _active_sessions:
        raise HTTPException(status_code=400, detail="Session is not currently active")

    if not _active_sessions[session_id].get("active"):
        raise HTTPException(status_code=400, detail="Session is not currently active")

    # Set interrupt flag
    _active_sessions[session_id]["interrupt_requested"] = True

    logger.info(f"Interrupt requested for session {session_id}")
    return MessageResponse(message="Interrupt signal sent")


@app.get("/sessions/{user_id}", response_model=SessionListResponse)
async def get_user_sessions(
    user_id: str,
    skip: int = 0,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """Get all sessions for a user (paginated).

    Args:
        user_id: User ID to get sessions for
        skip: Number of sessions to skip
        limit: Maximum sessions to return
        current_user: Authenticated user from JWT
        db: Database session

    Returns:
        Paginated list of user's sessions
    """
    # Only allow users to see their own sessions
    if not verify_ownership(current_user.user_id, user_id):
        raise HTTPException(status_code=403, detail="Access denied")

    session_manager = SessionManager(db)
    sessions = session_manager.get_user_sessions(user_id, limit=limit, offset=skip)
    total = session_manager.get_user_sessions_count(user_id)

    return SessionListResponse(
        total=total,
        sessions=[
            ResearchSessionResponse(
                session_id=str(s.session_id),
                query=s.query,
                final_answer=s.final_answer,
                quality_score=s.quality_score,
                status=s.status,
                created_at=s.created_at.isoformat(),
                updated_at=s.updated_at.isoformat(),
            )
            for s in sessions
        ],
    )


@app.get("/sessions/{session_id}/history", response_model=SessionHistoryResponse)
async def get_session_history(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """Get chat history for a session.

    Args:
        session_id: Session ID
        current_user: Authenticated user from JWT
        db: Database session

    Returns:
        Chat history with all messages
    """
    session_manager = SessionManager(db)
    session = session_manager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Verify ownership
    if not verify_ownership(current_user.user_id, session.user_id):
        raise HTTPException(status_code=403, detail="Access denied")

    history = session_manager.get_session_history(session_id)

    return SessionHistoryResponse(
        session_id=session_id,
        query=session.query,
        messages=[
            ChatHistoryItem(
                type=h.message_type,
                content=h.content,
                timestamp=h.created_at.isoformat(),
            )
            for h in history
        ],
    )


@app.get("/research/{session_id}/logs")
async def get_session_logs(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """Retrieve research session logs for debugging."""
    session_manager = SessionManager(db)
    session = session_manager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Verify ownership
    if not verify_ownership(current_user.user_id, session.user_id):
        raise HTTPException(status_code=403, detail="Access denied")

    log_file = Path("logs") / "research" / f"{session_id}.jsonl"
    if not log_file.exists():
        return {"logs": []}

    try:
        logs = []
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    logs.append(json.loads(line))
        return {"logs": logs}
    except Exception as e:
        logger.error(f"Failed to read logs for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to read logs")


@app.delete("/sessions/{session_id}", response_model=MessageResponse)
async def delete_session(
    session_id: str,
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """Archive/delete a session.

    Args:
        session_id: Session ID
        current_user: Authenticated user from JWT
        db: Database session

    Returns:
        Success message
    """
    session_manager = SessionManager(db)
    session = session_manager.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Verify ownership
    if not verify_ownership(current_user.user_id, session.user_id):
        raise HTTPException(status_code=403, detail="Access denied")

    # Permanently delete session
    if not session_manager.delete_session(session_id, soft_delete=False):
        raise HTTPException(status_code=500, detail="Failed to delete session")

    logger.info(f"Session {session_id} permanently deleted by user {current_user.user_id}")
    return MessageResponse(message="Session deleted")


@app.post("/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """Upload and index a document (PDF or Markdown).

    Args:
        file: Document file to upload
        current_user: Authenticated user
        db: Database session

    Returns:
        Document metadata and indexing status
    """
    user_id = str(current_user.user_id)

    # Validate file type
    allowed_extensions = {".pdf", ".md", ".markdown", ".txt"}
    file_ext = Path(file.filename).suffix.lower()
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"File type not supported. Allowed: {', '.join(allowed_extensions)}"
        )

    # Create uploads directory
    uploads_dir = Path("data") / "uploads" / user_id
    uploads_dir.mkdir(parents=True, exist_ok=True)

    # Save file temporarily
    file_path = uploads_dir / file.filename
    try:
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)
        logger.info(f"File saved: {file_path}")
    except Exception as e:
        logger.error(f"Failed to save file: {e}")
        raise HTTPException(status_code=500, detail="Failed to save file")

    # Index the document with PageIndex
    try:
        pageindex_doc_id = index_document(str(file_path), user_id)
        logger.info(f"Document indexed: {file.filename} (doc_id: {pageindex_doc_id})")
    except Exception as e:
        logger.error(f"Failed to index document: {e}")
        # Clean up uploaded file on indexing failure
        try:
            os.remove(file_path)
        except:
            pass
        raise HTTPException(status_code=500, detail=f"Failed to index document: {str(e)}")

    # Save metadata to database
    try:
        doc_record = UserDocument(
            user_id=current_user.user_id,
            filename=file.filename,
            pageindex_doc_id=pageindex_doc_id,
            status="indexed",
        )
        db.add(doc_record)
        db.commit()
        db.refresh(doc_record)
        logger.info(f"Document record saved: {doc_record.document_id}")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to save document record: {e}")
        raise HTTPException(status_code=500, detail="Failed to save document metadata")

    return DocumentUploadResponse(
        document_id=str(doc_record.document_id),
        filename=file.filename,
        pageindex_doc_id=pageindex_doc_id,
        status="indexed",
        message=f"Document '{file.filename}' uploaded and indexed successfully",
    )


@app.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """List all documents for the current user.

    Args:
        current_user: Authenticated user
        db: Database session

    Returns:
        List of user's documents
    """
    user_id = str(current_user.user_id)

    try:
        documents = db.query(UserDocument).filter_by(user_id=current_user.user_id).all()

        return DocumentListResponse(
            total=len(documents),
            documents=[
                DocumentResponse(
                    document_id=str(doc.document_id),
                    filename=doc.filename,
                    pageindex_doc_id=doc.pageindex_doc_id,
                    status=doc.status,
                    created_at=doc.created_at.isoformat(),
                )
                for doc in documents
            ],
        )
    except Exception as e:
        logger.error(f"Failed to list documents: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve documents")


@app.delete("/documents/{document_id}", response_model=MessageResponse)
async def delete_document(
    document_id: str,
    current_user: User = Depends(get_current_user),
    db: DBSession = Depends(get_db),
):
    """Delete a document and remove it from PageIndex.

    Args:
        document_id: Document ID to delete
        current_user: Authenticated user
        db: Database session

    Returns:
        Success message
    """
    try:
        # Get document record
        doc = db.query(UserDocument).filter_by(
            document_id=document_id,
            user_id=current_user.user_id
        ).first()

        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        # Delete from database
        db.delete(doc)
        db.commit()
        logger.info(f"Document deleted: {document_id}")

        # TODO: Delete from PageIndex workspace (optional cleanup)
        # This would involve removing the document from the user's PageIndex workspace

        return MessageResponse(message=f"Document '{doc.filename}' deleted successfully")

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to delete document: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete document")


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0",
    }


@app.get("/api/info")
async def api_info():
    """Get API information and available endpoints."""
    return {
        "version": "1.0.0",
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "endpoints": {
            "authentication": [
                "POST /auth/register",
                "POST /auth/login",
                "POST /auth/refresh",
                "GET /auth/me",
                "POST /auth/logout",
            ],
            "research": [
                "POST /research/start",
                "GET /research/{session_id}",
                "POST /research/{session_id}/stream",
                "POST /research/{session_id}/interrupt",
            ],
            "sessions": [
                "GET /sessions/{user_id}",
                "GET /sessions/{session_id}/history",
                "DELETE /sessions/{session_id}",
            ],
            "documents": [
                "POST /documents/upload",
                "GET /documents",
                "DELETE /documents/{document_id}",
            ],
            "health": [
                "GET /health",
                "GET /api/info",
            ],
        },
        "models": ["gpt-4o-mini", "gemini-2.5-pro"],
    }
