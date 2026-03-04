"""SSE streaming manager for real-time event notifications."""

import asyncio
import json
from typing import Dict, Set, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class SSEEvent:
    """SSE event payload."""
    event_id: int
    session_id: str
    ts: str
    source: str
    type: str
    body_preview: str  # First 200 chars max
    meta: Dict[str, Any] = field(default_factory=dict)
    
    def to_sse(self) -> str:
        """Format as SSE text."""
        data = {
            "event_id": self.event_id,
            "ts": self.ts,
            "source": self.source,
            "type": self.type,
            "body_preview": self.body_preview,
            "meta": self.meta
        }
        lines = [
            f"id: {self.event_id}",
            f"event: council_event",
            f"data: {json.dumps(data)}",
            "",  # Empty line to end event
        ]
        return "\n".join(lines)


class SSEManager:
    """Manages SSE subscriptions and event broadcasting.
    
    Uses asyncio.Queue per session for subscriber management.
    Thread-safe for use with FastAPI async endpoints.
    """
    
    def __init__(self):
        # session_id -> set of queues (one per subscriber)
        self._subscribers: Dict[str, Set[asyncio.Queue]] = {}
        self._lock = asyncio.Lock()
    
    async def subscribe(self, session_id: str) -> asyncio.Queue:
        """Subscribe to events for a session.
        
        Returns a queue that will receive SSEEvent objects.
        """
        queue = asyncio.Queue()
        
        async with self._lock:
            if session_id not in self._subscribers:
                self._subscribers[session_id] = set()
            self._subscribers[session_id].add(queue)
        
        return queue
    
    async def unsubscribe(self, session_id: str, queue: asyncio.Queue):
        """Unsubscribe from a session."""
        async with self._lock:
            if session_id in self._subscribers:
                self._subscribers[session_id].discard(queue)
                if not self._subscribers[session_id]:
                    del self._subscribers[session_id]
    
    async def broadcast(self, session_id: str, event: SSEEvent):
        """Broadcast an event to all subscribers of a session."""
        async with self._lock:
            queues = self._subscribers.get(session_id, set()).copy()
        
        # Put event in all subscriber queues
        for queue in queues:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # Skip if queue is full (slow consumer)
                pass
    
    def broadcast_sync(self, session_id: str, event: SSEEvent):
        """Synchronous broadcast for use from sync code.
        
        Creates a new event loop if needed.
        """
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.broadcast(session_id, event))
        except RuntimeError:
            # No running loop, create one
            asyncio.run(self.broadcast(session_id, event))
    
    async def get_subscriber_count(self, session_id: str) -> int:
        """Get number of subscribers for a session."""
        async with self._lock:
            return len(self._subscribers.get(session_id, set()))


# Global SSE manager instance
sse_manager = SSEManager()


def make_body_preview(body: str, max_len: int = 200) -> str:
    """Create a truncated body preview for SSE events."""
    if len(body) <= max_len:
        return body
    return body[:max_len - 3] + "..."
