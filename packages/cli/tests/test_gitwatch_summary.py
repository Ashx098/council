"""Tests for gitwatch module."""

import pytest
from pathlib import Path

from council_cli.wrapper.gitwatch import (
    extract_files_from_diff,
    summarize_diff,
    GitDiffSummary,
    format_patch_summary,
)


class TestExtractFilesFromDiff:
    """Tests for extract_files_from_diff."""
    
    def test_single_file(self):
        """Test extracting single file from diff."""
        diff = """diff --git a/src/main.py b/src/main.py
index 1234567..abcdefg 100644
--- a/src/main.py
+++ b/src/main.py
@@ -1,3 +1,4 @@
 def main():
+    print("hello")
     pass
"""
        files = extract_files_from_diff(diff)
        assert files == ["src/main.py"]
    
    def test_multiple_files(self):
        """Test extracting multiple files from diff."""
        diff = """diff --git a/a.py b/a.py
--- a/a.py
+++ b/a.py
@@ -0,0 +1 @@
+pass
diff --git a/b.py b/b.py
--- a/b.py
+++ b/b.py
@@ -0,0 +1 @@
+pass
"""
        files = extract_files_from_diff(diff)
        assert "a.py" in files
        assert "b.py" in files
    
    def test_empty_diff(self):
        """Test empty diff."""
        files = extract_files_from_diff("")
        assert files == []


class TestSummarizeDiff:
    """Tests for summarize_diff."""
    
    def test_basic_summary(self):
        """Test basic diff summary."""
        diff = """diff --git a/test.py b/test.py
--- a/test.py
+++ b/test.py
@@ -0,0 +1,2 @@
+def hello():
+    pass
"""
        summary = summarize_diff(diff)
        
        assert "test.py" in summary.files
        assert summary.additions == 2
        assert summary.removals == 0
    
    def test_with_removals(self):
        """Test diff with removals."""
        diff = """diff --git a/test.py b/test.py
--- a/test.py
+++ b/test.py
@@ -1,2 +1,1 @@
-old line
+new line
"""
        summary = summarize_diff(diff)

        assert summary.additions == 1
        assert summary.removals == 1


class TestFormatPatchSummary:
    """Tests for format_patch_summary."""
    
    def test_basic_summary(self):
        """Test basic patch summary."""
        summary = GitDiffSummary(
            files=["a.py", "b.py"],
            additions=10,
            removals=5,
            is_staged=False,
            is_dirty=True
        )
        
        result = format_patch_summary(summary)
        
        assert "a.py" in result
        assert "b.py" in result
        assert "+10" in result
        assert "-5" in result
    
    def test_with_artifact(self):
        """Test summary with artifact reference."""
        summary = GitDiffSummary(
            files=["test.py"],
            additions=1,
            removals=0,
            is_staged=False,
            is_dirty=True
        )
        
        result = format_patch_summary(summary, artifact_id="abc123xyz")
        
        assert "abc123xy" in result  # Truncated
    
    def test_empty_summary(self):
        """Test empty summary."""
        summary = GitDiffSummary(
            files=[],
            additions=0,
            removals=0,
            is_staged=False,
            is_dirty=False
        )
        
        result = format_patch_summary(summary)
        
        assert "No changes" in result
