"""Hub API client."""

import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

import httpx


@dataclass
class Event:
    """Event from hub."""
    event_id: int
    session_id: str
    ts: str
    source: str
    type: str
    body: str
    meta: Optional[Dict[str, Any]] = None


@dataclass
class Digest:
    """Digest from hub."""
    digest_text: str
    milestones: List[Dict[str, Any]]
    next_cursor: int
    has_more: bool


@dataclass
class ContextPack:
    """Context pack from hub."""
    session_id: str
    repo_root: Optional[str]
    title: Optional[str]
    pinned_decisions: List[Dict[str, Any]]
    current_task: Optional[Dict[str, Any]]
    last_patch: Optional[Dict[str, Any]]
    last_test_status: Optional[Dict[str, Any]]
    recent_digest: str


class HubClient:
    """Client for Council Hub API."""
    
    def __init__(self, base_url: str = "http://127.0.0.1:7337", 
                 timeout: float = 30.0, max_retries: int = 3):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.max_retries = max_retries
        self._client = httpx.Client(timeout=timeout)
    
    def _request(self, method: str, path: str, **kwargs) -> httpx.Response:
        """Make request with retry logic."""
        url = f"{self.base_url}{path}"
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                response = self._client.request(method, url, **kwargs)
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as e:
                # Don't retry client errors (4xx)
                if 400 <= e.response.status_code < 500:
                    raise
                last_error = e
            except httpx.RequestError as e:
                last_error = e
            
            # Wait before retry
            if attempt < self.max_retries - 1:
                time.sleep(0.5 * (attempt + 1))
        
        raise last_error or httpx.RequestError("Max retries exceeded")
    
    def health(self) -> Dict[str, str]:
        """Check hub health."""
        response = self._request("GET", "/health")
        return response.json()
    
    def create_session(self, session_id: str, title: Optional[str] = None,
                       repo_root: Optional[str] = None) -> Dict[str, Any]:
        """Create a new session."""
        payload = {"session_id": session_id}
        if title:
            payload["title"] = title
        if repo_root:
            payload["repo_root"] = repo_root
        
        response = self._request("POST", "/v1/sessions", json=payload)
        return response.json()
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session by ID."""
        try:
            response = self._request("GET", f"/v1/sessions/{session_id}")
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise
    
    def list_events(self, session_id: str, after: int = 0, 
                    limit: int = 100) -> Dict[str, Any]:
        """List events for session."""
        params = {"after": after, "limit": limit}
        response = self._request("GET", f"/v1/sessions/{session_id}/events",
                                params=params)
        return response.json()
    
    def get_last_n_events(self, session_id: str, n: int = 50) -> List[Event]:
        """Get last N events using cursor logic."""
        # First get total count by listing all
        all_events = []
        cursor = 0
        
        while True:
            result = self.list_events(session_id, after=cursor, limit=100)
            events = result.get("events", [])
            if not events:
                break
            all_events.extend([Event(**e) for e in events])
            cursor = result.get("next_cursor", 0)
            if not result.get("has_more", False):
                break
        
        # Return last N
        return all_events[-n:] if len(all_events) > n else all_events
    
    def ingest_event(self, session_id: str, source: str, type_: str,
                     body: str, meta: Optional[Dict[str, Any]] = None,
                     artifacts: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
        """Ingest a new event.
        
        Args:
            session_id: Session ID
            source: Event source (wrapper, chatgpt, user, etc.)
            type_: Event type (message, patch, test_result, etc.)
            body: Event body text
            meta: Optional metadata dict
            artifacts: Optional list of artifacts [{"kind": "patch", "content": "..."}]
            
        Returns:
            Response from hub
        """
        payload = {
            "source": source,
            "type": type_,
            "body": body,
        }
        if meta:
            payload["meta"] = meta
        if artifacts:
            payload["artifacts"] = artifacts
        
        response = self._request("POST", f"/v1/sessions/{session_id}/events",
                                json=payload)
        return response.json()
    
    def get_digest(self, session_id: str, after: int = 0) -> Digest:
        """Get digest for session."""
        response = self._request("GET", f"/v1/sessions/{session_id}/digest",
                                params={"after": after})
        data = response.json()
        return Digest(
            digest_text=data["digest_text"],
            milestones=data.get("milestones", []),
            next_cursor=data["next_cursor"],
            has_more=data["has_more"]
        )
    
    def get_context(self, session_id: str) -> ContextPack:
        """Get context pack for session."""
        response = self._request("GET", f"/v1/sessions/{session_id}/context")
        data = response.json()
        return ContextPack(
            session_id=data["session_id"],
            repo_root=data.get("repo_root"),
            title=data.get("title"),
            pinned_decisions=data.get("pinned_decisions", []),
            current_task=data.get("current_task"),
            last_patch=data.get("last_patch"),
            last_test_status=data.get("last_test_status"),
            recent_digest=data.get("recent_digest", "")
        )
    
    def get_artifact(self, session_id: str, artifact_id: str) -> bytes:
        """Get artifact content."""
        response = self._request("GET", 
                                f"/v1/sessions/{session_id}/artifacts/{artifact_id}")
        return response.content
    
    def close(self):
        """Close the client."""
        self._client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, *args):
        self.close()
