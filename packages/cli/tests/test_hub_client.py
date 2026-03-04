"""Tests for hub client."""

import pytest
from unittest.mock import Mock, patch
import httpx

from council_cli.client.hub_client import HubClient, Event, Digest, ContextPack


class TestHubClient:
    """Tests for HubClient."""
    
    @patch('httpx.Client')
    def test_health(self, mock_client_class):
        """Test health check."""
        mock_response = Mock()
        mock_response.json.return_value = {"status": "healthy", "version": "1.0.0"}
        mock_response.raise_for_status = Mock()
        
        mock_client = Mock()
        mock_client.request.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        client = HubClient("http://test:7337")
        result = client.health()
        
        assert result["status"] == "healthy"
    
    @patch('httpx.Client')
    def test_create_session(self, mock_client_class):
        """Test session creation."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "session_id": "test:123",
            "title": "Test",
            "event_count": 0
        }
        mock_response.raise_for_status = Mock()
        
        mock_client = Mock()
        mock_client.request.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        client = HubClient()
        result = client.create_session("test:123", title="Test")
        
        assert result["session_id"] == "test:123"
    
    @patch('httpx.Client')
    def test_ingest_event(self, mock_client_class):
        """Test event ingestion."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "event_id": 1,
            "session_id": "test:123",
            "ts": "2026-01-01T00:00:00Z"
        }
        mock_response.raise_for_status = Mock()
        
        mock_client = Mock()
        mock_client.request.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        client = HubClient()
        result = client.ingest_event(
            session_id="test:123",
            source="wrapper",
            type_="message",
            body="Hello"
        )
        
        assert result["event_id"] == 1
    
    @patch('httpx.Client')
    def test_ingest_event_with_artifact(self, mock_client_class):
        """Test event ingestion with artifact."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "event_id": 2,
            "session_id": "test:123",
            "ts": "2026-01-01T00:00:00Z",
            "meta": {"artifact_id": "art-123"}
        }
        mock_response.raise_for_status = Mock()
        
        mock_client = Mock()
        mock_client.request.return_value = mock_response
        mock_client_class.return_value = mock_client
        
        client = HubClient()
        result = client.ingest_event(
            session_id="test:123",
            source="wrapper",
            type_="patch",
            body="Fixed bug",
            artifacts=[{"kind": "patch", "content": "diff content"}]
        )
        
        assert result["event_id"] == 2
        assert result["meta"]["artifact_id"] == "art-123"


class TestEvent:
    """Tests for Event dataclass."""
    
    def test_event_creation(self):
        """Test event creation."""
        event = Event(
            event_id=1,
            session_id="test:123",
            ts="2026-01-01T00:00:00Z",
            source="wrapper",
            type="message",
            body="Hello"
        )
        
        assert event.event_id == 1
        assert event.source == "wrapper"
        assert event.type == "message"


class TestDigest:
    """Tests for Digest dataclass."""
    
    def test_digest_creation(self):
        """Test digest creation."""
        digest = Digest(
            digest_text="Summary",
            milestones=[],
            next_cursor=5,
            has_more=False
        )
        
        assert digest.digest_text == "Summary"
        assert digest.next_cursor == 5


class TestContextPack:
    """Tests for ContextPack dataclass."""
    
    def test_context_pack_creation(self):
        """Test context pack creation."""
        context = ContextPack(
            session_id="test:123",
            repo_root="/tmp/test",
            title="Test",
            pinned_decisions=[],
            current_task=None,
            last_patch=None,
            last_test_status=None,
            recent_digest=""
        )
        
        assert context.session_id == "test:123"
        assert context.repo_root == "/tmp/test"
