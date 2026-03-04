"""Tests for event operations."""

import pytest
import tempfile
from pathlib import Path

from council_hub.db.repo import Database, SessionRepo, EventRepo
from council_hub.core.ingest import IngestService
from council_hub.storage.artifacts import ArtifactStore


@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = Database(db_path)
        yield db


@pytest.fixture
def session_repo(temp_db):
    """Create session repository."""
    return SessionRepo(temp_db)


@pytest.fixture
def event_repo(temp_db):
    """Create event repository."""
    return EventRepo(temp_db)


@pytest.fixture
def ingest_service(temp_db):
    """Create ingest service with temp storage."""
    with tempfile.TemporaryDirectory() as tmpdir:
        store = ArtifactStore(Path(tmpdir))
        service = IngestService(temp_db, store)
        yield service


class TestSessionRepo:
    """Test session repository operations."""
    
    def test_create_session(self, session_repo):
        """Test creating a session."""
        session = session_repo.create("test-session-1", repo_root="/tmp/repo", title="Test")
        
        assert session.session_id == "test-session-1"
        assert session.repo_root == "/tmp/repo"
        assert session.title == "Test"
        assert session.event_count == 0
    
    def test_get_session(self, session_repo):
        """Test retrieving a session."""
        session_repo.create("test-session-2")
        
        session = session_repo.get("test-session-2")
        assert session is not None
        assert session.session_id == "test-session-2"
    
    def test_get_nonexistent_session(self, session_repo):
        """Test retrieving nonexistent session returns None."""
        session = session_repo.get("nonexistent")
        assert session is None
    
    def test_get_or_create(self, session_repo):
        """Test get_or_create creates if not exists."""
        session = session_repo.get_or_create("test-session-3")
        assert session.session_id == "test-session-3"
        
        # Second call should return existing
        session2 = session_repo.get_or_create("test-session-3")
        assert session2.session_id == "test-session-3"
    
    def test_list_sessions(self, session_repo):
        """Test listing sessions."""
        session_repo.create("session-a")
        session_repo.create("session-b")
        
        sessions = session_repo.list(limit=10)
        assert len(sessions) == 2


class TestEventRepo:
    """Test event repository operations."""
    
    def test_append_event(self, event_repo, session_repo):
        """Test appending an event."""
        session_repo.create("test-session")
        
        event_id = event_repo.append(
            "test-session", "wrapper", "patch", "Modified file.py"
        )
        
        assert event_id > 0
        
        # Verify event exists
        event = event_repo.get(event_id)
        assert event is not None
        assert event.session_id == "test-session"
        assert event.source == "wrapper"
        assert event.type == "patch"
        assert event.body == "Modified file.py"
    
    def test_list_events_after_cursor(self, event_repo, session_repo):
        """Test listing events with cursor."""
        session_repo.create("test-session")
        
        # Add multiple events
        id1 = event_repo.append("test-session", "wrapper", "patch", "First")
        id2 = event_repo.append("test-session", "wrapper", "patch", "Second")
        id3 = event_repo.append("test-session", "wrapper", "patch", "Third")
        
        # List after first event
        events = event_repo.list_after("test-session", after=id1, limit=10)
        assert len(events) == 2
        assert events[0].event_id == id2
        assert events[1].event_id == id3
    
    def test_list_events_pagination(self, event_repo, session_repo):
        """Test event pagination."""
        session_repo.create("test-session")
        
        # Add 5 events
        for i in range(5):
            event_repo.append("test-session", "wrapper", "patch", f"Event {i}")
        
        # List with limit
        events = event_repo.list_after("test-session", after=0, limit=3)
        assert len(events) == 3
    
    def test_event_count_updates(self, session_repo, event_repo):
        """Test that event count updates when events are added."""
        session = session_repo.create("test-session")
        assert session.event_count == 0
        
        event_repo.append("test-session", "wrapper", "patch", "Test")
        
        # Reload session
        updated = session_repo.get("test-session")
        assert updated.event_count == 1


class TestIngestService:
    """Test ingest service."""
    
    def test_ingest_event_creates_session(self, ingest_service):
        """Test that ingesting event auto-creates session."""
        event_id = ingest_service.ingest_event(
            "new-session", "wrapper", "patch", "Test event"
        )
        
        assert event_id > 0
    
    def test_ingest_event_validation(self, ingest_service):
        """Test event validation."""
        # Invalid source
        with pytest.raises(Exception):
            ingest_service.ingest_event(
                "session", "invalid_source", "patch", "Test"
            )
        
        # Invalid type
        with pytest.raises(Exception):
            ingest_service.ingest_event(
                "session", "wrapper", "invalid_type", "Test"
            )
    
    def test_ingest_artifact(self, ingest_service):
        """Test artifact ingestion."""
        artifact_id = ingest_service.ingest_artifact(
            "test-session", "patch", b"diff content"
        )
        
        assert artifact_id is not None
        
        # Verify can retrieve
        content = ingest_service.store.retrieve("test-session", artifact_id)
        assert content == b"diff content"
    
    def test_ingest_with_artifact(self, ingest_service):
        """Test combined event + artifact ingestion."""
        result = ingest_service.ingest_with_artifact(
            session_id="test-session",
            source="wrapper",
            type="patch",
            body="Modified file.py",
            artifact_kind="patch",
            artifact_content=b"diff content",
            meta={"files_changed": ["file.py"]}
        )
        
        assert "event_id" in result
        assert "artifact_id" in result
