"""Database repository for Council Hub."""

import json
import sqlite3
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path

from council_hub.config import settings


class Session:
    """Session model."""
    
    def __init__(self, session_id: str, repo_root: Optional[str] = None,
                 title: Optional[str] = None, created_at: Optional[str] = None,
                 updated_at: Optional[str] = None, event_count: int = 0):
        self.session_id = session_id
        self.repo_root = repo_root
        self.title = title
        self.created_at = created_at or datetime.utcnow().isoformat()
        self.updated_at = updated_at or self.created_at
        self.event_count = event_count
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "repo_root": self.repo_root,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "event_count": self.event_count,
        }


class Event:
    """Event model."""
    
    def __init__(self, event_id: int, session_id: str, ts: str,
                 source: str, type: str, body: str,
                 meta: Optional[Dict[str, Any]] = None):
        self.event_id = event_id
        self.session_id = session_id
        self.ts = ts
        self.source = source
        self.type = type
        self.body = body
        self.meta = meta or {}
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "session_id": self.session_id,
            "ts": self.ts,
            "source": self.source,
            "type": self.type,
            "body": self.body,
            "meta": self.meta,
        }


class Artifact:
    """Artifact model."""
    
    def __init__(self, artifact_id: str, session_id: str, kind: str,
                 path: str, byte_size: int, sha256: str,
                 created_at: Optional[str] = None):
        self.artifact_id = artifact_id
        self.session_id = session_id
        self.kind = kind
        self.path = path
        self.byte_size = byte_size
        self.sha256 = sha256
        self.created_at = created_at or datetime.utcnow().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "session_id": self.session_id,
            "kind": self.kind,
            "path": self.path,
            "byte_size": self.byte_size,
            "sha256": self.sha256,
            "created_at": self.created_at,
        }


class Database:
    """Database connection manager."""
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or settings.db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize database with schema."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Read schema
        schema_path = Path(__file__).parent / "schema.sql"
        if schema_path.exists():
            with open(schema_path, "r") as f:
                schema = f.read()
            
            with sqlite3.connect(self.db_path) as conn:
                conn.executescript(schema)
    
    def get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn


class SessionRepo:
    """Repository for session operations."""
    
    def __init__(self, db: Database):
        self.db = db
    
    def create(self, session_id: str, repo_root: Optional[str] = None,
               title: Optional[str] = None) -> Session:
        """Create a new session."""
        with self.db.get_connection() as conn:
            conn.execute(
                """INSERT INTO sessions (session_id, repo_root, title)
                   VALUES (?, ?, ?)""",
                (session_id, repo_root, title)
            )
            conn.commit()
        
        return self.get(session_id)
    
    def get(self, session_id: str) -> Optional[Session]:
        """Get session by ID."""
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?",
                (session_id,)
            ).fetchone()
            
            if row:
                return Session(
                    session_id=row["session_id"],
                    repo_root=row["repo_root"],
                    title=row["title"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    event_count=row["event_count"],
                )
            return None
    
    def get_or_create(self, session_id: str, 
                      repo_root: Optional[str] = None) -> Session:
        """Get existing session or create new one."""
        session = self.get(session_id)
        if session:
            return session
        return self.create(session_id, repo_root)
    
    def list(self, limit: int = 20, offset: int = 0) -> List[Session]:
        """List sessions ordered by most recently updated."""
        with self.db.get_connection() as conn:
            rows = conn.execute(
                """SELECT * FROM sessions 
                   ORDER BY updated_at DESC LIMIT ? OFFSET ?""",
                (limit, offset)
            ).fetchall()
            
            return [
                Session(
                    session_id=r["session_id"],
                    repo_root=r["repo_root"],
                    title=r["title"],
                    created_at=r["created_at"],
                    updated_at=r["updated_at"],
                    event_count=r["event_count"],
                )
                for r in rows
            ]
    
    def update(self, session_id: str, **kwargs) -> Optional[Session]:
        """Update session fields."""
        allowed = {"repo_root", "title"}
        updates = {k: v for k, v in kwargs.items() if k in allowed}
        
        if not updates:
            return self.get(session_id)
        
        set_clause = ", ".join(f"{k} = ?" for k in updates.keys())
        values = list(updates.values()) + [session_id]
        
        with self.db.get_connection() as conn:
            conn.execute(
                f"UPDATE sessions SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE session_id = ?",
                values
            )
            conn.commit()
            conn.commit()
        
        return self.get(session_id)


class EventRepo:
    """Repository for event operations."""
    
    def __init__(self, db: Database):
        self.db = db
    
    def append(self, session_id: str, source: str, type: str,
               body: str, meta: Optional[Dict[str, Any]] = None) -> int:
        """Append a new event. Returns event_id."""
        meta_json = json.dumps(meta) if meta else None
        
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO events (session_id, source, type, body, meta_json)
                   VALUES (?, ?, ?, ?, ?)""",
                (session_id, source, type, body, meta_json)
            )
            conn.commit()
            return cursor.lastrowid
    
    def get(self, event_id: int) -> Optional[Event]:
        """Get event by ID."""
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM events WHERE event_id = ?",
                (event_id,)
            ).fetchone()
            
            if row:
                return self._row_to_event(row)
            return None
    
    def list_after(self, session_id: str, after: int = 0,
                   limit: int = 50) -> List[Event]:
        """List events after cursor, ordered by event_id."""
        with self.db.get_connection() as conn:
            rows = conn.execute(
                """SELECT * FROM events 
                   WHERE session_id = ? AND event_id > ?
                   ORDER BY event_id ASC LIMIT ?""",
                (session_id, after, limit)
            ).fetchall()
            
            return [self._row_to_event(r) for r in rows]
    
    def list_range(self, session_id: str, start: int, end: int) -> List[Event]:
        """List events in ID range."""
        with self.db.get_connection() as conn:
            rows = conn.execute(
                """SELECT * FROM events 
                   WHERE session_id = ? AND event_id >= ? AND event_id <= ?
                   ORDER BY event_id ASC""",
                (session_id, start, end)
            ).fetchall()
            
            return [self._row_to_event(r) for r in rows]
    
    def get_latest(self, session_id: str, type_filter: Optional[str] = None,
                   limit: int = 1) -> List[Event]:
        """Get latest events, optionally filtered by type."""
        with self.db.get_connection() as conn:
            if type_filter:
                rows = conn.execute(
                    """SELECT * FROM events 
                       WHERE session_id = ? AND type = ?
                       ORDER BY event_id DESC LIMIT ?""",
                    (session_id, type_filter, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT * FROM events 
                       WHERE session_id = ?
                       ORDER BY event_id DESC LIMIT ?""",
                    (session_id, limit)
                ).fetchall()
            
            # Return in chronological order
            return list(reversed([self._row_to_event(r) for r in rows]))
    
    def count(self, session_id: str) -> int:
        """Count events in session."""
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as count FROM events WHERE session_id = ?",
                (session_id,)
            ).fetchone()
            return row["count"] if row else 0
    
    def _row_to_event(self, row: sqlite3.Row) -> Event:
        """Convert database row to Event."""
        meta = None
        if row["meta_json"]:
            try:
                meta = json.loads(row["meta_json"])
            except json.JSONDecodeError:
                meta = {}
        
        return Event(
            event_id=row["event_id"],
            session_id=row["session_id"],
            ts=row["ts"],
            source=row["source"],
            type=row["type"],
            body=row["body"],
            meta=meta,
        )


class ArtifactRepo:
    """Repository for artifact operations."""
    
    def __init__(self, db: Database):
        self.db = db
    
    def create(self, artifact_id: str, session_id: str, kind: str,
               path: str, byte_size: int, sha256: str) -> Artifact:
        """Create artifact record."""
        with self.db.get_connection() as conn:
            conn.execute(
                """INSERT INTO artifacts 
                   (artifact_id, session_id, kind, path, byte_size, sha256)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (artifact_id, session_id, kind, path, byte_size, sha256)
            )
            conn.commit()
        
        return self.get(artifact_id)
    
    def get(self, artifact_id: str) -> Optional[Artifact]:
        """Get artifact by ID."""
        with self.db.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM artifacts WHERE artifact_id = ?",
                (artifact_id,)
            ).fetchone()
            
            if row:
                return Artifact(
                    artifact_id=row["artifact_id"],
                    session_id=row["session_id"],
                    kind=row["kind"],
                    path=row["path"],
                    byte_size=row["byte_size"],
                    sha256=row["sha256"],
                    created_at=row["created_at"],
                )
            return None
    
    def list_by_session(self, session_id: str, 
                        kind_filter: Optional[str] = None) -> List[Artifact]:
        """List artifacts for session, optionally filtered by kind."""
        with self.db.get_connection() as conn:
            if kind_filter:
                rows = conn.execute(
                    """SELECT * FROM artifacts 
                       WHERE session_id = ? AND kind = ?
                       ORDER BY created_at DESC""",
                    (session_id, kind_filter)
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT * FROM artifacts 
                       WHERE session_id = ?
                       ORDER BY created_at DESC""",
                    (session_id,)
                ).fetchall()
            
            return [
                Artifact(
                    artifact_id=r["artifact_id"],
                    session_id=r["session_id"],
                    kind=r["kind"],
                    path=r["path"],
                    byte_size=r["byte_size"],
                    sha256=r["sha256"],
                    created_at=r["created_at"],
                )
                for r in rows
            ]
    
    def delete(self, artifact_id: str) -> bool:
        """Delete artifact record."""
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM artifacts WHERE artifact_id = ?",
                (artifact_id,)
            )
            conn.commit()
            return cursor.rowcount > 0
