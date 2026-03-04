"""Tests for digest generation."""

import pytest
import tempfile
from pathlib import Path

from council_hub.db.repo import Database
from council_hub.core.ingest import IngestService
from council_hub.core.digest import DigestService
from council_hub.storage.artifacts import ArtifactStore
from council_hub.utils.text import (
    truncate_lines, extract_error_windows, truncate_to_budget,
    parse_diff_summary, format_hunk_for_digest
)


@pytest.fixture
def temp_digest_setup():
    """Create full setup for digest testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = Database(db_path)
        store = ArtifactStore(Path(tmpdir) / "artifacts")
        ingest = IngestService(db, store)
        digest = DigestService(db, store)
        
        yield {
            "db": db,
            "store": store,
            "ingest": ingest,
            "digest": digest,
        }


class TestTextUtils:
    """Test text utility functions."""
    
    def test_truncate_lines_basic(self):
        """Test basic line truncation."""
        text = "line1\nline2\nline3\nline4\nline5"
        result = truncate_lines(text, 3)
        assert result == "line1\nline2\nline3"
    
    def test_truncate_lines_with_tail(self):
        """Test truncation keeping tail."""
        text = "line1\nline2\nline3\nline4\nline5"
        result = truncate_lines(text, 4, tail_lines=2)
        assert "line1\nline2" in result
        assert "line4\nline5" in result
        assert "..." in result
    
    def test_truncate_lines_no_truncation_needed(self):
        """Test when text is within limit."""
        text = "line1\nline2"
        result = truncate_lines(text, 5)
        assert result == text
    
    def test_extract_error_windows(self):
        """Test error window extraction."""
        text = """line1
line2
Error: something broke
line4
line5
Traceback (most recent call last)
line7
line8"""
        
        windows = extract_error_windows(text, window_size=1)
        assert len(windows) >= 2  # Should find both Error and Traceback
        
        # Check Error window
        error_window = [w for w in windows if "Error:" in w]
        assert len(error_window) == 1
        assert "line2" in error_window[0]  # context before
        assert "line4" in error_window[0]  # context after
    
    def test_truncate_to_budget(self):
        """Test budget-based truncation."""
        parts = ["short", "medium length text", "another part"]
        result = truncate_to_budget(parts, 50)
        # Should include all parts
        assert "short" in result
        assert "medium" in result
    
    def test_truncate_to_budget_exceeded(self):
        """Test when budget is exceeded."""
        parts = ["a" * 100, "b" * 100, "c" * 100]
        result = truncate_to_budget(parts, 150)
        assert len(result) <= 150


class TestDiffParsing:
    """Test diff parsing utilities."""
    
    def test_parse_diff_summary(self):
        """Test parsing git diff output."""
        diff_text = """diff --git a/file1.py b/file1.py
--- a/file1.py
+++ b/file1.py
@@ -1,5 +1,5 @@
 def foo():
-    return 1
+    return 2
 
 def bar():
     pass
diff --git a/file2.py b/file2.py
--- a/file2.py
+++ b/file2.py
@@ -10,3 +10,4 @@
     x = 1
     y = 2
+    z = 3
     return x + y
"""
        
        summary = parse_diff_summary(diff_text)
        
        assert len(summary.files) == 2
        assert "file1.py" in summary.files
        assert "file2.py" in summary.files
        assert summary.lines_added == 3  # Two + lines in first, one in second
        assert summary.lines_removed == 1
        assert len(summary.hunks) == 2
    
    def test_format_hunk_for_digest(self):
        """Test hunk formatting with truncation."""
        from council_hub.utils.text import DiffHunk
        
        hunk = DiffHunk(
            file_path="test.py",
            old_start=1,
            old_count=10,
            new_start=1,
            new_count=12,
            lines=[f"line {i}" for i in range(50)]
        )
        
        formatted = format_hunk_for_digest(hunk, max_lines=10)
        lines = formatted.split("\n")
        
        # Should have header + truncated lines
        assert lines[0].startswith("@@")
        assert "..." in formatted


class TestDigestService:
    """Test digest generation service."""
    
    def test_empty_digest(self, temp_digest_setup):
        """Test digest for session with no events."""
        digest = temp_digest_setup["digest"]
        
        result = digest.generate_digest("empty-session", after=0)
        
        assert "No new events" in result.digest_text
        assert result.next_cursor == 0
        assert not result.has_more
    
    def test_basic_digest(self, temp_digest_setup):
        """Test basic digest generation."""
        ingest = temp_digest_setup["ingest"]
        digest = temp_digest_setup["digest"]
        
        # Add some events
        ingest.ingest_event("session-1", "wrapper", "patch", "Modified auth.py")
        ingest.ingest_event("session-1", "wrapper", "test_result", "Tests passed")
        
        result = digest.generate_digest("session-1", after=0)
        
        assert "session-1" in result.digest_text
        assert "patch" in result.digest_text.lower() or "Modified" in result.digest_text
        assert result.next_cursor > 0
    
    def test_digest_with_cursor(self, temp_digest_setup):
        """Test digest with cursor pagination."""
        ingest = temp_digest_setup["ingest"]
        digest = temp_digest_setup["digest"]
        
        # Add events
        event_id = ingest.ingest_event("session-2", "wrapper", "patch", "First")
        ingest.ingest_event("session-2", "wrapper", "patch", "Second")
        
        # Get digest after first event
        result = digest.generate_digest("session-2", after=event_id)
        
        assert "Second" in result.digest_text
        assert "First" not in result.digest_text
    
    def test_milestone_extraction(self, temp_digest_setup):
        """Test milestone event extraction."""
        ingest = temp_digest_setup["ingest"]
        digest = temp_digest_setup["digest"]
        
        # Add regular and milestone events
        ingest.ingest_event("session-3", "wrapper", "patch", "Change 1")
        ingest.ingest_event("session-3", "wrapper", "milestone", "Executor started",
                          meta={"subtype": "executor_started"})
        ingest.ingest_event("session-3", "chatgpt", "message", "Done")
        
        result = digest.generate_digest("session-3", after=0)
        
        assert len(result.milestones) >= 1
        assert any(m["subtype"] == "executor_started" for m in result.milestones)
    
    def test_digest_budget_enforcement(self, temp_digest_setup):
        """Test that digest respects character budget."""
        ingest = temp_digest_setup["ingest"]
        digest = temp_digest_setup["digest"]
        
        # Add many events with long bodies
        for i in range(50):
            ingest.ingest_event("session-4", "wrapper", "message", "X" * 500)
        
        result = digest.generate_digest("session-4", after=0)
        
        assert len(result.digest_text) <= 12000 + 100  # Allow small margin
    
    def test_context_pack(self, temp_digest_setup):
        """Test context pack generation."""
        ingest = temp_digest_setup["ingest"]
        digest = temp_digest_setup["digest"]
        
        # Create session with various event types
        ingest.ingest_event("session-5", "chatgpt", "decision", "Use SQLite")
        ingest.ingest_event("session-5", "chatgpt", "task_brief", "Build the hub")
        ingest.ingest_event("session-5", "wrapper", "patch", "Added main.py")
        ingest.ingest_event("session-5", "wrapper", "test_result", "All passed")
        
        context = digest.generate_context_pack("session-5")
        
        assert context["session_id"] == "session-5"
        assert len(context["pinned_decisions"]) > 0
        assert context["current_task"] is not None
        assert context["last_patch"] is not None
        assert context["last_test_status"] is not None
        assert len(context["recent_digest"]) > 0


class TestPatchDigest:
    """Test patch-specific digest formatting."""
    
    def test_patch_with_artifact(self, temp_digest_setup):
        """Test patch event with artifact content."""
        ingest = temp_digest_setup["ingest"]
        digest = temp_digest_setup["digest"]
        
        diff_content = b"""diff --git a/main.py b/main.py
--- a/main.py
+++ b/main.py
@@ -1,3 +1,4 @@
 def main():
+    print("Hello")
     pass
"""
        
        # Ingest with artifact
        result = ingest.ingest_with_artifact(
            "session-6", "wrapper", "patch", "Added print",
            "patch", diff_content,
            meta={"files_changed": ["main.py"], "lines_added": 1, "lines_removed": 0}
        )
        
        digest_result = digest.generate_digest("session-6", after=0)
        
        assert "main.py" in digest_result.digest_text
        assert "Files:" in digest_result.digest_text


class TestLogDigest:
    """Test log-specific digest formatting."""
    
    def test_test_result_with_errors(self, temp_digest_setup):
        """Test test result with error extraction."""
        ingest = temp_digest_setup["ingest"]
        digest = temp_digest_setup["digest"]
        
        log_content = b"""Running tests...
test1 passed
test2 failed
Error: Assertion failed
  File "test.py", line 10
    assert x == 1
AssertionError: 1 != 2
test3 passed
5 tests, 1 failed
"""
        
        result = ingest.ingest_with_artifact(
            "session-7", "wrapper", "test_result", "Tests failed",
            "test_log", log_content,
            meta={"command": "pytest", "exit_code": 1, "passed": 4, "failed": 1, "skipped": 0}
        )
        
        digest_result = digest.generate_digest("session-7", after=0)
        
        assert "FAIL" in digest_result.digest_text or "failed" in digest_result.digest_text
        assert "Passed: 4" in digest_result.digest_text
        assert "Failed: 1" in digest_result.digest_text
