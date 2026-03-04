"""Tests for SSE streaming endpoint."""

import asyncio
import json
import pytest
from council_hub.core.stream import SSEManager, SSEEvent, make_body_preview


class TestSSEManager:
    """Tests for SSEManager class."""
    
    @pytest.mark.asyncio
    async def test_subscribe_unsubscribe(self):
        """Test subscribe and unsubscribe operations."""
        manager = SSEManager()
        
        queue = await manager.subscribe("test-session")
        assert await manager.get_subscriber_count("test-session") == 1
        
        await manager.unsubscribe("test-session", queue)
        assert await manager.get_subscriber_count("test-session") == 0
    
    @pytest.mark.asyncio
    async def test_broadcast_to_subscribers(self):
        """Test broadcasting events to subscribers."""
        manager = SSEManager()
        
        queue = await manager.subscribe("test-session")
        
        event = SSEEvent(
            event_id=1,
            session_id="test-session",
            ts="2024-01-01T00:00:00Z",
            source="user",
            type="message",
            body_preview="Test"
        )
        
        await manager.broadcast("test-session", event)
        
        # Should receive the event
        received = await asyncio.wait_for(queue.get(), timeout=1.0)
        assert received.event_id == 1
        assert received.source == "user"
    
    def test_sse_event_format(self):
        """Test SSEEvent.to_sse() format."""
        event = SSEEvent(
            event_id=123,
            session_id="test-session",
            ts="2024-01-01T00:00:00Z",
            source="wrapper",
            type="run_report",
            body_preview="Test preview",
            meta={"exit_code": 0}
        )
        
        sse_text = event.to_sse()
        
        assert "id: 123" in sse_text
        assert "event: council_event" in sse_text
        assert '"event_id": 123' in sse_text
        assert '"source": "wrapper"' in sse_text
        assert '"type": "run_report"' in sse_text
    
    @pytest.mark.asyncio
    async def test_multiple_subscribers(self):
        """Test broadcasting to multiple subscribers."""
        manager = SSEManager()
        
        queue1 = await manager.subscribe("test-session")
        queue2 = await manager.subscribe("test-session")
        
        assert await manager.get_subscriber_count("test-session") == 2
        
        event = SSEEvent(
            event_id=1,
            session_id="test-session",
            ts="2024-01-01T00:00:00Z",
            source="user",
            type="message",
            body_preview="Test"
        )
        
        await manager.broadcast("test-session", event)
        
        # Both should receive
        r1 = await asyncio.wait_for(queue1.get(), timeout=1.0)
        r2 = await asyncio.wait_for(queue2.get(), timeout=1.0)
        assert r1.event_id == 1
        assert r2.event_id == 1
    
    @pytest.mark.asyncio
    async def test_broadcast_no_subscribers(self):
        """Test broadcasting when no subscribers (should not error)."""
        manager = SSEManager()
        
        event = SSEEvent(
            event_id=1,
            session_id="no-subscribers",
            ts="2024-01-01T00:00:00Z",
            source="user",
            type="message",
            body_preview="Test"
        )
        
        # Should not raise
        await manager.broadcast("no-subscribers", event)


class TestBodyPreview:
    """Tests for body preview truncation."""
    
    def test_short_body_not_truncated(self):
        """Test that short bodies are not truncated."""
        body = "Short message"
        preview = make_body_preview(body)
        assert preview == body
    
    def test_long_body_truncated(self):
        """Test that long bodies are truncated to 200 chars."""
        body = "x" * 500
        preview = make_body_preview(body)
        assert len(preview) == 200
        assert preview.endswith("...")
    
    def test_exact_200_chars(self):
        """Test body exactly 200 chars."""
        body = "x" * 200
        preview = make_body_preview(body)
        assert preview == body
        assert len(preview) == 200
    
    def test_201_chars_truncated(self):
        """Test body of 201 chars is truncated."""
        body = "x" * 201
        preview = make_body_preview(body)
        assert len(preview) == 200
        assert preview.endswith("...")


class TestSSEEventStructure:
    """Tests for SSE event structure and serialization."""
    
    def test_event_with_meta(self):
        """Test event with meta data serializes correctly."""
        event = SSEEvent(
            event_id=42,
            session_id="cgpt:test-123",
            ts="2024-01-15T10:30:00Z",
            source="wrapper",
            type="test_result",
            body_preview="Tests passed",
            meta={"exit_code": 0, "test_count": 5}
        )
        
        sse_text = event.to_sse()
        data = json.loads(sse_text.split("data: ")[1].strip())
        
        assert data["event_id"] == 42
        assert data["meta"]["exit_code"] == 0
        assert data["meta"]["test_count"] == 5
    
    def test_event_without_meta(self):
        """Test event without meta data."""
        event = SSEEvent(
            event_id=1,
            session_id="test",
            ts="2024-01-01T00:00:00Z",
            source="user",
            type="message",
            body_preview="Hello"
        )
        
        sse_text = event.to_sse()
        data = json.loads(sse_text.split("data: ")[1].strip())
        
        assert data["meta"] == {}
    
    def test_sse_format_has_required_fields(self):
        """Test SSE format has all required fields."""
        event = SSEEvent(
            event_id=1,
            session_id="test",
            ts="2024-01-01T00:00:00Z",
            source="user",
            type="message",
            body_preview="Test",
            meta={}
        )
        
        sse_text = event.to_sse()
        
        # Check SSE format
        assert sse_text.startswith("id: 1\n")
        assert "event: council_event\n" in sse_text
        assert "data: {" in sse_text
        
        # Check JSON fields
        data = json.loads(sse_text.split("data: ")[1].strip())
        required_fields = ["event_id", "ts", "source", "type", "body_preview", "meta"]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"
