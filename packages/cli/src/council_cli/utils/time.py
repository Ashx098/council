"""Utility functions for time handling."""

import time
from datetime import datetime, timezone


def now_iso() -> str:
    """Get current timestamp in ISO 8601 format.
    
    Returns:
        ISO formatted timestamp
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def format_duration(seconds: float) -> str:
    """Format duration in human-readable form.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Human-readable duration string
    """
    if seconds < 1:
        return f"{int(seconds * 1000)}ms"
    elif seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}m{secs}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h{minutes}m"


def elapsed_since(start_time: float) -> float:
    """Calculate elapsed time since start.
    
    Args:
        start_time: Start time from time.time()
        
    Returns:
        Elapsed seconds
    """
    return time.time() - start_time
