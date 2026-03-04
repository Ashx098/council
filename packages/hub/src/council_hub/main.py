"""Council Hub - FastAPI application."""
import asyncio
import json
from typing import Optional, List, Dict, Any, AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from council_hub.config import settings, EVENT_SOURCES, EVENT_TYPES, ARTIFACT_KINDS
from council_hub.db.repo import Database, SessionRepo, EventRepo, ArtifactRepo
from council_hub.core.ingest import IngestService, IngestError
from council_hub.core.digest import DigestService
from council_hub.core.stream import SSEManager, SSEEvent, make_body_preview
from council_hub.core.pairing import PairingService, PairingCode
from council_hub.storage.artifacts import ArtifactStore


# Database and service instances
db: Optional[Database] = None
sessions: Optional[SessionRepo] = None
events: Optional[EventRepo] = None
artifacts: Optional[ArtifactRepo] = None
store: Optional[ArtifactStore] = None
ingest: Optional[IngestService] = None
digest: Optional[DigestService] = None
sse: Optional[SSEManager] = None
pairing: Optional[PairingService] = None


def get_sse() -> SSEManager:
    """Get SSE manager, initializing lazily if needed."""
    global sse
    if sse is None:
        sse = SSEManager()
    return sse


def get_pairing_service() -> PairingService:
    """Get pairing service, initializing lazily if needed."""
    global pairing, db
    if pairing is None:
        if db is None:
            db = Database()
        pairing = PairingService(db)
    return pairing


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    global db, sessions, events, artifacts, store, ingest, digest, sse, pairing
    
    # Initialize on startup
    db = Database()
    sessions = SessionRepo(db)
    events = EventRepo(db)
    artifacts = ArtifactRepo(db)
    store = ArtifactStore()
    ingest = IngestService(db, store)
    digest = DigestService(db, store)
    sse = SSEManager()
    pairing = PairingService(db)
    
    yield
    
    # Cleanup on shutdown
    db = None


app = FastAPI(
    title="Council Hub",
    description="Local session store and digest service for Council",
    version="1.0.0-phase4",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Local development only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Pydantic models
class CreateSessionRequest(BaseModel):
    session_id: str
    repo_root: Optional[str] = None
    title: Optional[str] = None


class SessionResponse(BaseModel):
    session_id: str
    repo_root: Optional[str] = None
    title: Optional[str] = None
    created_at: str
    updated_at: str
    event_count: int


class ArtifactUpload(BaseModel):
    kind: str = Field(..., description=f"One of: {ARTIFACT_KINDS}")
    content: str = Field(..., description="Artifact content as string")


class IngestEventRequest(BaseModel):
    source: str = Field(..., description=f"One of: {EVENT_SOURCES}")
    type: str = Field(..., description=f"One of: {EVENT_TYPES}")
    body: str = Field(..., description="Event body text")
    meta: Optional[Dict[str, Any]] = Field(None, description="Optional metadata")
    artifacts: Optional[List[ArtifactUpload]] = Field(None, description="Optional artifacts to upload")

class IngestEventResponse(BaseModel):
    event_id: int
    session_id: str
    ts: str
    meta: Optional[Dict[str, Any]] = None


class ListEventsResponse(BaseModel):
    events: List[Dict[str, Any]]
    next_cursor: int
    has_more: bool


class DigestResponse(BaseModel):
    digest_text: str
    milestones: List[Dict[str, Any]]
    next_cursor: int
    has_more: bool


class ContextResponse(BaseModel):
    session_id: str
    repo_root: Optional[str] = None
    title: Optional[str] = None
    pinned_decisions: List[Dict[str, Any]]
    current_task: Optional[Dict[str, Any]] = None
    last_patch: Optional[Dict[str, Any]] = None
    last_test_status: Optional[Dict[str, Any]] = None
    recent_digest: str


class ErrorResponse(BaseModel):
    error: str
    message: str


# Exception handlers
@app.exception_handler(IngestError)
async def ingest_error_handler(request, exc):
    raise HTTPException(status_code=400, detail={
        "error": "ingest_error",
        "message": str(exc)
    })


# Session endpoints
@app.post("/v1/sessions", response_model=SessionResponse, status_code=201)
async def create_session(request: CreateSessionRequest):
    """Create a new session."""
    existing = sessions.get(request.session_id)
    if existing:
        return SessionResponse(**existing.to_dict())
    
    session = sessions.create(
        request.session_id,
        repo_root=request.repo_root,
        title=request.title
    )
    return SessionResponse(**session.to_dict())


@app.get("/v1/sessions/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str):
    """Get session by ID."""
    session = sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail={
            "error": "session_not_found",
            "message": f"Session {session_id} does not exist"
        })
    return SessionResponse(**session.to_dict())


@app.get("/v1/sessions", response_model=List[SessionResponse])
async def list_sessions(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """List sessions ordered by most recently updated."""
    session_list = sessions.list(limit=limit, offset=offset)
    return [SessionResponse(**s.to_dict()) for s in session_list]


# Event endpoints
@app.post("/v1/sessions/{session_id}/events", response_model=IngestEventResponse, status_code=201)
async def ingest_event(session_id: str, request: IngestEventRequest):
    """Ingest a new event into the session."""
    
    # Process artifacts if present
    meta = request.meta or {}
    if request.artifacts:
        for art in request.artifacts:
            artifact_id = ingest.ingest_artifact(
                session_id=session_id,
                kind=art.kind,
                content=art.content.encode("utf-8")
            )
            # Add artifact_id to meta
            meta["artifact_id"] = artifact_id
    
    event_id = ingest.ingest_event(
        session_id=session_id,
        source=request.source,
        type=request.type,
        body=request.body,
        meta=meta
    )
    
    event = events.get(event_id)
    
    # Broadcast to SSE subscribers
    sse_event = SSEEvent(
        event_id=event.event_id,
        session_id=event.session_id,
        ts=event.ts,
        source=event.source,
        type=event.type,
        body_preview=make_body_preview(event.body),
        meta=event.meta
    )
    await get_sse().broadcast(session_id, sse_event)
    
    return IngestEventResponse(
        event_id=event.event_id,
        session_id=event.session_id,
        ts=event.ts,
        meta=event.meta
    )

@app.get("/v1/sessions/{session_id}/events", response_model=ListEventsResponse)
async def list_events(
    session_id: str,
    after: int = Query(0, ge=0, description="Only return events after this event_id"),
    limit: int = Query(50, ge=1, le=100)
):
    """List events for session with cursor-based pagination."""
    event_list = events.list_after(session_id, after=after, limit=limit)
    
    if not event_list:
        return ListEventsResponse(
            events=[],
            next_cursor=after,
            has_more=False
        )
    
    # Check if there are more events
    last_id = event_list[-1].event_id
    has_more = len(event_list) >= limit
    
    return ListEventsResponse(
        events=[e.to_dict() for e in event_list],
        next_cursor=last_id,
        has_more=has_more
    )


# SSE streaming endpoint
@app.get("/v1/sessions/{session_id}/stream")
async def stream_events(
    session_id: str,
    after: int = Query(0, ge=0, description="Start streaming after this event_id"),
    last_event_id: Optional[str] = Query(None, alias="Last-Event-ID", description="Reconnect after this event_id")
):
    """SSE endpoint for real-time event streaming.
    
    Returns text/event-stream with events as they arrive.
    Supports reconnect via Last-Event-ID header or query param.
    """
    # Prefer Last-Event-ID header over query param
    reconnect_cursor = after
    if last_event_id:
        try:
            reconnect_cursor = int(last_event_id)
        except ValueError:
            pass
    
    async def event_generator() -> AsyncGenerator[str, None]:
        """Generate SSE events."""
        # Send hello event on connect
        hello = {
            "type": "connected",
            "session_id": session_id,
            "after": reconnect_cursor
        }
        yield f"event: hello\ndata: {json.dumps(hello)}\n\n"
        
        # Subscribe to session events
        queue = await get_sse().subscribe(session_id)
        
        try:
            while True:
                try:
                    # Wait for events with timeout for keepalive
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield event.to_sse() + "\n"
                except asyncio.TimeoutError:
                    # Send keepalive comment
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            # Client disconnected
            pass
        finally:
            await get_sse().unsubscribe(session_id, queue)
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


# Digest endpoints
@app.get("/v1/sessions/{session_id}/digest", response_model=DigestResponse)
async def get_digest(
    session_id: str,
    after: int = Query(0, ge=0, description="Only include events after this event_id")
):
    """Get bounded digest for session."""
    result = digest.generate_digest(session_id, after=after)
    return DigestResponse(
        digest_text=result.digest_text,
        milestones=result.milestones,
        next_cursor=result.next_cursor,
        has_more=result.has_more
    )


# Context pack endpoint
@app.get("/v1/sessions/{session_id}/context", response_model=ContextResponse)
async def get_context(session_id: str):
    """Get context pack for executor briefing."""
    context = digest.generate_context_pack(session_id)
    return ContextResponse(**context)


# Artifact endpoints
@app.get("/v1/sessions/{session_id}/artifacts/{artifact_id}")
async def get_artifact(session_id: str, artifact_id: str):
    """Get artifact content."""
    artifact = artifacts.get(artifact_id)
    if not artifact or artifact.session_id != session_id:
        raise HTTPException(status_code=404, detail={
            "error": "artifact_not_found",
            "message": f"Artifact {artifact_id} not found in session {session_id}"
        })
    
    content = store.retrieve(session_id, artifact_id)
    if content is None:
        raise HTTPException(status_code=404, detail={
            "error": "artifact_not_found",
            "message": f"Artifact {artifact_id} content not found"
        })
    
    # Determine content type based on kind
    content_type_map = {
        "patch": "text/plain",
        "test_log": "text/plain",
        "command_output": "text/plain",
        "repo_map": "application/json",
        "run_log": "text/plain",
    }
    content_type = content_type_map.get(artifact.kind, "application/octet-stream")
    
    return Response(
        content=content,
        media_type=content_type,
        headers={
            "X-Artifact-Id": artifact_id,
            "X-Artifact-Kind": artifact.kind,
            "X-Artifact-Size": str(artifact.byte_size),
        }
    )

# ============ Pairing Endpoints ============

class CreatePairingRequest(BaseModel):
    session_id: str = Field(..., description="Session ID to pair")
    ttl_minutes: int = Field(10, description="Time-to-live in minutes")


class ClaimPairingRequest(BaseModel):
    code: str = Field(..., description="Pairing code to claim")
    claimed_by: Optional[str] = Field(None, description="Identifier for claimer")
    repo_root: Optional[str] = Field(None, description="Repository path")


class PairingResponse(BaseModel):
    code: str
    session_id: str
    repo_root: Optional[str]
    created_at: str
    expires_at: str
    claimed_at: Optional[str]
    claimed_by: Optional[str]


def pairing_to_response(p: PairingCode) -> PairingResponse:
    return PairingResponse(
        code=p.code,
        session_id=p.session_id,
        repo_root=p.repo_root,
        created_at=p.created_at,
        expires_at=p.expires_at,
        claimed_at=p.claimed_at,
        claimed_by=p.claimed_by
    )


@app.post("/v1/pair/create", response_model=PairingResponse)
async def create_pairing(request: CreatePairingRequest):
    """Create a new pairing code for a session.
    
    The extension calls this to get a code that the CLI can claim.
    """
    if sessions is None:
        raise HTTPException(status_code=503, detail="Service not initialized")
    
    # Ensure session exists
    session = sessions.get_or_create(request.session_id)
    
    try:
        code = get_pairing_service().create(request.session_id, request.ttl_minutes)
        return pairing_to_response(code)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/v1/pair/claim", response_model=PairingResponse)
async def claim_pairing(request: ClaimPairingRequest):
    """Claim a pairing code.
    
    The CLI calls this to bind to a session.
    """
    try:
        result = get_pairing_service().claim(
            request.code,
            claimed_by=request.claimed_by,
            repo_root=request.repo_root
        )
        return pairing_to_response(result)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/v1/pair/{code}", response_model=PairingResponse)
async def get_pairing(code: str):
    """Get pairing code status."""
    result = get_pairing_service().get(code)
    if result is None:
        raise HTTPException(status_code=404, detail={
            "error": "pairing_not_found",
            "message": "Pairing code not found or expired"
        })
    
    return pairing_to_response(result)


@app.get("/v1/pair/session/{session_id}", response_model=PairingResponse)
async def get_session_pairing(session_id: str):
    """Get the active pairing code for a session."""
    result = get_pairing_service().get_by_session(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail={
            "error": "no_active_pairing",
            "message": "No active pairing code for this session"
        })
    
    return pairing_to_response(result)


# Health check
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "1.0.0-phase5"}


# Main entry point
def main():
    """Run the Council Hub server."""
    import uvicorn
    
    print(f"Starting Council Hub on {settings.host}:{settings.port}")
    print(f"Data directory: {settings.data_dir}")
    
    uvicorn.run(
        "council_hub.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload
    )


if __name__ == "__main__":
    main()
