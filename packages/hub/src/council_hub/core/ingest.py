"""Event and artifact ingestion service."""

from typing import Optional, Dict, Any
from council_hub.config import EVENT_SOURCES, EVENT_TYPES, ARTIFACT_KINDS, settings
from council_hub.db.repo import Database, SessionRepo, EventRepo, ArtifactRepo
from council_hub.storage.artifacts import ArtifactStore


class IngestError(Exception):
    """Ingestion error."""
    pass


class IngestService:
    """Service for ingesting events and artifacts."""
    
    def __init__(self, db: Optional[Database] = None,
                 store: Optional[ArtifactStore] = None):
        self.db = db or Database()
        self.sessions = SessionRepo(self.db)
        self.events = EventRepo(self.db)
        self.artifacts = ArtifactRepo(self.db)
        self.store = store or ArtifactStore()
    
    def ingest_event(self, session_id: str, source: str, type: str,
                     body: str, meta: Optional[Dict[str, Any]] = None) -> int:
        """Ingest a new event.
        
        Args:
            session_id: Session identifier
            source: Event source (user, chatgpt, opencode, claude_code, wrapper)
            type: Event type (message, task_brief, patch, etc.)
            body: Event body text (summary)
            meta: Optional metadata dict
            
        Returns:
            event_id of created event
            
        Raises:
            IngestError: If validation fails
        """
        # Validate source
        if source not in EVENT_SOURCES:
            raise IngestError(f"Invalid source: {source}. "
                            f"Must be one of: {EVENT_SOURCES}")
        
        # Validate type
        if type not in EVENT_TYPES:
            raise IngestError(f"Invalid type: {type}. "
                            f"Must be one of: {EVENT_TYPES}")
        
        # Validate body length
        max_body = 4000
        if len(body) > max_body:
            body = body[:max_body-3] + "..."
        
        # Ensure session exists
        self.sessions.get_or_create(session_id)
        
        # Append event
        event_id = self.events.append(session_id, source, type, body, meta)
        
        return event_id
    
    def ingest_artifact(self, session_id: str, kind: str,
                        content: bytes, artifact_id: Optional[str] = None) -> str:
        """Ingest an artifact.
        
        Args:
            session_id: Session identifier
            kind: Artifact kind (patch, test_log, command_output, repo_map, run_log)
            content: Raw bytes to store
            artifact_id: Optional artifact ID (generated if not provided)
            
        Returns:
            artifact_id of stored artifact
            
        Raises:
            IngestError: If validation fails
        """
        # Validate kind
        if kind not in ARTIFACT_KINDS:
            raise IngestError(f"Invalid kind: {kind}. "
                            f"Must be one of: {ARTIFACT_KINDS}")
        
        # Validate size
        if len(content) > settings.max_artifact_size:
            raise IngestError(f"Artifact too large: {len(content)} bytes. "
                            f"Max: {settings.max_artifact_size} bytes")
        
        # Ensure session exists
        self.sessions.get_or_create(session_id)
        
        # Store to filesystem
        artifact_id, sha256, byte_size = self.store.store(
            session_id, content, artifact_id
        )
        
        # Get path
        path = str(self.store.get_path(session_id, artifact_id))
        
        # Create database record
        self.artifacts.create(artifact_id, session_id, kind, path, 
                             byte_size, sha256)
        
        return artifact_id
    
    def ingest_with_artifact(self, session_id: str, source: str, type: str,
                             body: str, artifact_kind: str, 
                             artifact_content: bytes,
                             meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Ingest an event with an associated artifact.
        
        This is a convenience method for common pattern of event + artifact.
        
        Args:
            session_id: Session identifier
            source: Event source
            type: Event type
            body: Event body
            artifact_kind: Kind of artifact
            artifact_content: Artifact bytes
            meta: Optional metadata (artifact_id will be added)
            
        Returns:
            Dict with event_id and artifact_id
        """
        # First store artifact
        artifact_id = self.ingest_artifact(session_id, artifact_kind, 
                                          artifact_content)
        
        # Build meta with artifact reference
        full_meta = meta or {}
        full_meta["artifact_id"] = artifact_id
        
        # Then store event
        event_id = self.ingest_event(session_id, source, type, body, full_meta)
        
        return {
            "event_id": event_id,
            "artifact_id": artifact_id,
        }
