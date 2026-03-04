"""Pairing service for session-cli binding."""

import secrets
import string
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class PairingCode:
    """Pairing code model."""
    code: str
    session_id: str
    repo_root: Optional[str]
    created_at: str
    expires_at: str
    claimed_at: Optional[str] = None
    claimed_by: Optional[str] = None


class PairingService:
    """Manages pairing codes for session-cli binding.
    
    Flow:
    1. Extension creates pairing code for a session
    2. CLI claims the code with repo path
    3. CLI can now reference session by pair code
    """
    
    CODE_LENGTH = 4
    CODE_CHARS = string.ascii_uppercase + string.digits
    # Exclude ambiguous characters
    CODE_CHARS = ''.join(c for c in CODE_CHARS if c not in '0O1IL')
    
    DEFAULT_TTL_MINUTES = 10
    
    def __init__(self, db):
        """Initialize with database connection."""
        self.db = db
    
    def _generate_code(self) -> str:
        """Generate a random pairing code."""
        return ''.join(secrets.choice(self.CODE_CHARS) for _ in range(self.CODE_LENGTH))
    
    def create(self, session_id: str, ttl_minutes: int = None) -> PairingCode:
        """Create a new pairing code for a session.
        
        Args:
            session_id: The session to pair
            ttl_minutes: Time-to-live in minutes (default 10)
            
        Returns:
            PairingCode with the generated code
        """
        if ttl_minutes is None:
            ttl_minutes = self.DEFAULT_TTL_MINUTES
        
        # Generate unique code
        max_attempts = 10
        code = None
        
        for _ in range(max_attempts):
            candidate = self._generate_code()
            
            # Check if code already exists and is unexpired
            existing = self.get(candidate)
            if existing is None:
                code = candidate
                break
        
        if code is None:
            raise ValueError("Failed to generate unique pairing code")
        
        now = datetime.utcnow()
        expires_at = now + timedelta(minutes=ttl_minutes)
        
        with self.db.get_connection() as conn:
            conn.execute(
                """
                INSERT INTO pairing_codes (code, session_id, created_at, expires_at)
                VALUES (?, ?, ?, ?)
                """,
                (code, session_id, now.isoformat(), expires_at.isoformat())
            )
            conn.commit()
        
        return PairingCode(
            code=code,
            session_id=session_id,
            repo_root=None,
            created_at=now.isoformat(),
            expires_at=expires_at.isoformat()
        )
    
    def get(self, code: str) -> Optional[PairingCode]:
        """Get a pairing code by code.
        
        Returns None if code doesn't exist or is expired.
        """
        with self.db.get_connection() as conn:
            row = conn.execute(
                """
                SELECT code, session_id, repo_root, created_at, expires_at, 
                       claimed_at, claimed_by
                FROM pairing_codes
                WHERE code = ? AND expires_at > ?
                """,
                (code.upper(), datetime.utcnow().isoformat())
            ).fetchone()
        
        if row is None:
            return None
        
        return PairingCode(
            code=row['code'],
            session_id=row['session_id'],
            repo_root=row['repo_root'],
            created_at=row['created_at'],
            expires_at=row['expires_at'],
            claimed_at=row['claimed_at'],
            claimed_by=row['claimed_by']
        )
    
    def claim(self, code: str, claimed_by: str = None, repo_root: str = None) -> PairingCode:
        """Claim a pairing code.
        
        Args:
            code: The pairing code to claim
            claimed_by: Identifier for the claimer (e.g., hostname)
            repo_root: Repository path to associate
            
        Returns:
            PairingCode with session_id
            
        Raises:
            ValueError: If code is invalid, expired, or already claimed
        """
        pairing = self.get(code)
        
        if pairing is None:
            raise ValueError("Invalid or expired pairing code")
        
        if pairing.claimed_at is not None:
            raise ValueError("Pairing code already claimed")
        
        now = datetime.utcnow()
        
        with self.db.get_connection() as conn:
            conn.execute(
                """
                UPDATE pairing_codes
                SET claimed_at = ?, claimed_by = ?, repo_root = ?
                WHERE code = ?
                """,
                (now.isoformat(), claimed_by, repo_root, code.upper())
            )
            conn.commit()
        
        return PairingCode(
            code=pairing.code,
            session_id=pairing.session_id,
            repo_root=repo_root,
            created_at=pairing.created_at,
            expires_at=pairing.expires_at,
            claimed_at=now.isoformat(),
            claimed_by=claimed_by
        )
    
    def get_by_session(self, session_id: str) -> Optional[PairingCode]:
        """Get the latest unclaimed pairing code for a session."""
        with self.db.get_connection() as conn:
            row = conn.execute(
                """
                SELECT code, session_id, repo_root, created_at, expires_at,
                       claimed_at, claimed_by
                FROM pairing_codes
                WHERE session_id = ? AND claimed_at IS NULL AND expires_at > ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (session_id, datetime.utcnow().isoformat())
            ).fetchone()
        
        if row is None:
            return None
        
        return PairingCode(
            code=row['code'],
            session_id=row['session_id'],
            repo_root=row['repo_root'],
            created_at=row['created_at'],
            expires_at=row['expires_at'],
            claimed_at=row['claimed_at'],
            claimed_by=row['claimed_by']
        )
    
    def cleanup_expired(self) -> int:
        """Remove expired pairing codes.
        
        Returns:
            Number of codes removed
        """
        with self.db.get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM pairing_codes WHERE expires_at < ?",
                (datetime.utcnow().isoformat(),)
            )
            conn.commit()
            return cursor.rowcount
