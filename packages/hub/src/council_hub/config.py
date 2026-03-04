"""Configuration for Council Hub."""

import os
from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Hub configuration loaded from environment variables."""
    
    # Server settings
    host: str = "127.0.0.1"
    port: int = 8000
    reload: bool = False
    
    # Data paths
    data_dir: Path = Path.home() / ".council"
    db_path: Path = Path.home() / ".council" / "council.db"
    artifacts_dir: Path = Path.home() / ".council" / "artifacts"
    
    # Digest budgets
    digest_max_chars: int = 12000
    digest_max_events: int = 100
    
    # Patch budgets
    patch_max_hunks_per_file: int = 3
    patch_max_lines_per_hunk: int = 20
    patch_max_files_in_digest: int = 10
    
    # Log budgets
    log_max_lines: int = 200
    log_tail_lines: int = 50
    log_error_window: int = 10
    
    # Artifact limits
    max_artifact_size: int = 10 * 1024 * 1024  # 10 MB
    
    class Config:
        """Pydantic config."""
        env_prefix = "COUNCIL_"
        case_sensitive = False
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Ensure directories exist
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)


# Global settings instance
settings = Settings()


# Error keywords for log scanning
ERROR_KEYWORDS = [
    "Error:",
    "ERROR",
    "Traceback",
    "FAILED",
    "FAIL:",
    "panic:",
    "panic(",
    "Exception",
    "SyntaxError",
    "TypeError",
    "ValueError",
    "AssertionError",
    "error:",
    "error ",
]

# Valid event sources
EVENT_SOURCES = [
    "user",
    "chatgpt",
    "opencode",
    "claude_code",
    "wrapper",
]

# Valid event types
EVENT_TYPES = [
    "message",
    "task_brief",
    "question",
    "patch",
    "tool_run",
    "test_result",
    "run_report",
    "decision",
    "milestone",
]

# Valid artifact kinds
ARTIFACT_KINDS = [
    "patch",
    "test_log",
    "command_output",
    "repo_map",
    "run_log",
]

# Milestone subtypes
MILESTONE_SUBTYPES = [
    "executor_started",
    "executor_finished",
    "executor_failed",
    "tests_passing",
    "tests_failing",
    "patch_applied",
    "question_asked",
]
