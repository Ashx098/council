"""Text processing utilities for Council Hub."""

import re
from typing import List, NamedTuple
from council_hub.config import ERROR_KEYWORDS, settings


class DiffSummary(NamedTuple):
    """Summary of a diff."""
    files: List[str]
    lines_added: int
    lines_removed: int
    hunks: List["DiffHunk"]


class DiffHunk(NamedTuple):
    """A single diff hunk."""
    file_path: str
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: List[str]


def truncate_lines(text: str, max_lines: int, tail_lines: int = None) -> str:
    """Truncate text to max_lines, keeping tail if specified.
    
    Args:
        text: Input text
        max_lines: Maximum lines to keep
        tail_lines: If set, keep this many lines from the end
        
    Returns:
        Truncated text
    """
    lines = text.split("\n")
    
    if len(lines) <= max_lines:
        return text
    
    if tail_lines is not None:
        # Keep head and tail
        head_lines = max_lines - tail_lines
        if head_lines <= 0:
            # Just return tail
            return "\n".join(lines[-tail_lines:])
        
        head = lines[:head_lines]
        tail = lines[-tail_lines:] if tail_lines > 0 else []
        return "\n".join(head + ["..."] + tail)
    
    return "\n".join(lines[:max_lines])


def extract_error_windows(text: str, keywords: List[str] = None, 
                         window_size: int = None) -> List[str]:
    """Extract context windows around error keywords.
    
    Args:
        text: Input text (log output)
        keywords: List of keywords to search for (default: ERROR_KEYWORDS)
        window_size: Lines of context around each match (default: from settings)
        
    Returns:
        List of context windows
    """
    if keywords is None:
        keywords = ERROR_KEYWORDS
    if window_size is None:
        window_size = settings.log_error_window
    
    lines = text.split("\n")
    windows = []
    seen_lines = set()
    
    for i, line in enumerate(lines):
        for keyword in keywords:
            if keyword in line:
                # Calculate window bounds
                start = max(0, i - window_size)
                end = min(len(lines), i + window_size + 1)
                
                # Avoid duplicates
                window_key = (start, end)
                if window_key in seen_lines:
                    continue
                seen_lines.add(window_key)
                
                window_text = "\n".join(lines[start:end])
                windows.append(window_text)
                break
    
    return windows


def truncate_to_budget(parts: List[str], max_chars: int) -> str:
    """Concatenate parts until budget exhausted.
    
    Args:
        parts: List of text parts to concatenate
        max_chars: Maximum characters allowed
        
    Returns:
        Concatenated string within budget
    """
    result = []
    current_len = 0
    
    for part in parts:
        part_len = len(part)
        if current_len + part_len > max_chars:
            # Try to add partial
            remaining = max_chars - current_len
            if remaining > 10:  # Only add if meaningful space left
                result.append(part[:remaining] + "\n...")
            break
        result.append(part)
        current_len += part_len + 1  # +1 for newline
    
    return "\n".join(result)


def parse_diff_summary(diff_text: str) -> DiffSummary:
    """Parse git diff into structured summary.
    
    Args:
        diff_text: Raw git diff output
        
    Returns:
        DiffSummary with files, line counts, and hunks
    """
    files = []
    hunks = []
    lines_added = 0
    lines_removed = 0
    
    current_file = None
    current_hunk_lines = []
    current_hunk_header = None
    
    for line in diff_text.split("\n"):
        # File header: diff --git a/path b/path
        if line.startswith("diff --git "):
            # Save previous hunk if exists
            if current_file and current_hunk_header and current_hunk_lines:
                hunks.append(_parse_hunk_header(
                    current_file, current_hunk_header, current_hunk_lines
                ))
            
            # Extract filename
            match = re.search(r"diff --git a/(.*?) b/", line)
            if match:
                current_file = match.group(1)
                files.append(current_file)
            current_hunk_lines = []
            current_hunk_header = None
        
        # Hunk header: @@ -old_start,old_count +new_start,new_count @@
        elif line.startswith("@@"):
            # Save previous hunk
            if current_file and current_hunk_header and current_hunk_lines:
                hunks.append(_parse_hunk_header(
                    current_file, current_hunk_header, current_hunk_lines
                ))
            current_hunk_header = line
            current_hunk_lines = []
        
        # Hunk content
        elif current_hunk_header is not None:
            current_hunk_lines.append(line)
            if line.startswith("+") and not line.startswith("+++"):
                lines_added += 1
            elif line.startswith("-") and not line.startswith("---"):
                lines_removed += 1
    
    # Save final hunk
    if current_file and current_hunk_header and current_hunk_lines:
        hunks.append(_parse_hunk_header(
            current_file, current_hunk_header, current_hunk_lines
        ))
    
    return DiffSummary(
        files=files,
        lines_added=lines_added,
        lines_removed=lines_removed,
        hunks=hunks
    )


def _parse_hunk_header(file_path: str, header: str, 
                       lines: List[str]) -> DiffHunk:
    """Parse a hunk header line.
    
    Args:
        file_path: File path
        header: Hunk header line (@@ -old,old +new,new @@)
        lines: Hunk content lines
        
    Returns:
        DiffHunk object
    """
    # Extract numbers from header
    match = re.search(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", header)
    
    if match:
        old_start = int(match.group(1))
        old_count = int(match.group(2)) if match.group(2) else 1
        new_start = int(match.group(3))
        new_count = int(match.group(4)) if match.group(4) else 1
    else:
        old_start = old_count = new_start = new_count = 0
    
    return DiffHunk(
        file_path=file_path,
        old_start=old_start,
        old_count=old_count,
        new_start=new_start,
        new_count=new_count,
        lines=lines
    )


def format_hunk_for_digest(hunk: DiffHunk, max_lines: int = None) -> str:
    """Format a hunk for digest display.
    
    Args:
        hunk: DiffHunk to format
        max_lines: Maximum lines to include
        
    Returns:
        Formatted hunk string
    """
    if max_lines is None:
        max_lines = settings.patch_max_lines_per_hunk
    
    lines = hunk.lines
    if len(lines) > max_lines:
        # Keep first N/2 and last N/2
        half = max_lines // 2
        lines = lines[:half] + ["..."] + lines[-half:]
    
    header = f"@@ -{hunk.old_start},{hunk.old_count} +{hunk.new_start},{hunk.new_count} @@"
    return header + "\n" + "\n".join(lines)
