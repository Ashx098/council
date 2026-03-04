"""Artifact storage on filesystem."""

import hashlib
import shutil
from pathlib import Path
from typing import Optional
from uuid import uuid4

from council_hub.config import settings


class ArtifactStore:
    """Filesystem storage for artifacts."""
    
    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or settings.artifacts_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
    
    def _session_dir(self, session_id: str) -> Path:
        """Get directory for session artifacts."""
        # Sanitize session_id for filesystem
        safe_id = session_id.replace(":", "_").replace("/", "_")
        path = self.base_dir / safe_id
        path.mkdir(parents=True, exist_ok=True)
        return path
    
    def _artifact_path(self, session_id: str, artifact_id: str) -> Path:
        """Get filesystem path for artifact."""
        return self._session_dir(session_id) / f"{artifact_id}.bin"
    
    def store(self, session_id: str, content: bytes, 
              artifact_id: Optional[str] = None) -> tuple[str, str, int]:
        """Store artifact content.
        
        Args:
            session_id: Session ID
            content: Raw bytes to store
            artifact_id: Optional ID (generated if not provided)
            
        Returns:
            Tuple of (artifact_id, sha256_hash, byte_size)
        """
        if artifact_id is None:
            artifact_id = str(uuid4())
        
        # Compute hash
        sha256 = hashlib.sha256(content).hexdigest()
        byte_size = len(content)
        
        # Write to file
        path = self._artifact_path(session_id, artifact_id)
        with open(path, "wb") as f:
            f.write(content)
        
        return artifact_id, sha256, byte_size
    
    def retrieve(self, session_id: str, artifact_id: str) -> Optional[bytes]:
        """Retrieve artifact content.
        
        Args:
            session_id: Session ID
            artifact_id: Artifact ID
            
        Returns:
            Content bytes or None if not found
        """
        path = self._artifact_path(session_id, artifact_id)
        if not path.exists():
            return None
        
        with open(path, "rb") as f:
            return f.read()
    
    def delete(self, session_id: str, artifact_id: str) -> bool:
        """Delete artifact.
        
        Args:
            session_id: Session ID
            artifact_id: Artifact ID
            
        Returns:
            True if deleted, False if not found
        """
        path = self._artifact_path(session_id, artifact_id)
        if path.exists():
            path.unlink()
            return True
        return False
    
    def delete_session(self, session_id: str) -> bool:
        """Delete all artifacts for a session.
        
        Args:
            session_id: Session ID
            
        Returns:
            True if directory was removed
        """
        path = self._session_dir(session_id)
        if path.exists():
            shutil.rmtree(path)
            return True
        return False
    
    def get_path(self, session_id: str, artifact_id: str) -> Optional[Path]:
        """Get filesystem path for artifact.
        
        Args:
            session_id: Session ID
            artifact_id: Artifact ID
            
        Returns:
            Path if exists, None otherwise
        """
        path = self._artifact_path(session_id, artifact_id)
        return path if path.exists() else None
    
    def verify(self, session_id: str, artifact_id: str, 
               expected_sha256: str) -> bool:
        """Verify artifact integrity.
        
        Args:
            session_id: Session ID
            artifact_id: Artifact ID
            expected_sha256: Expected SHA256 hash
            
        Returns:
            True if hash matches
        """
        content = self.retrieve(session_id, artifact_id)
        if content is None:
            return False
        
        actual_sha256 = hashlib.sha256(content).hexdigest()
        return actual_sha256 == expected_sha256
