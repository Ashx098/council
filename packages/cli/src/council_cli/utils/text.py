"""Utility functions for text processing."""

from typing import List


def truncate(text: str, max_len: int = 120, suffix: str = "...") -> str:
    """Truncate text to max_len characters.
    
    Args:
        text: Text to truncate
        max_len: Maximum length
        suffix: Suffix to append if truncated
        
    Returns:
        Truncated text
    """
    if len(text) <= max_len:
        return text
    return text[:max_len - len(suffix)] + suffix


def split_by_size(text: str, max_size: int) -> List[str]:
    """Split text into chunks of max_size.
    
    Args:
        text: Text to split
        max_size: Maximum size per chunk
        
    Returns:
        List of text chunks
    """
    if not text:
        return []
    
    chunks = []
    remaining = text
    
    while remaining:
        if len(remaining) <= max_size:
            chunks.append(remaining)
            break
        # Find a good break point
        break_point = max_size
        # Try to break at newline
        newline_pos = remaining.rfind('\n', 0, max_size)
        if newline_pos > max_size // 2:
            break_point = newline_pos + 1
        chunks.append(remaining[:break_point])
        remaining = remaining[break_point:]
    
    return chunks


def count_lines(text: str) -> int:
    """Count lines in text.
    
    Args:
        text: Text to count
        
    Returns:
        Number of lines
    """
    if not text:
        return 0
    return text.count('\n') + (1 if text[-1] != '\n' else 0)


def extract_files_from_diff(diff_text: str) -> List[str]:
    """Extract file paths from a git diff.
    
    Args:
        diff_text: Git diff output
        
    Returns:
        List of file paths
    """
    files = []
    for line in diff_text.split('\n'):
        if line.startswith('diff --git '):
            # Format: diff --git a/path/to/file b/path/to/file
            parts = line.split(' ')
            if len(parts) >= 4:
                # Take the b/ path (destination)
                b_path = parts[3]
                if b_path.startswith('b/'):
                    b_path = b_path[2:]
                if b_path not in files:
                    files.append(b_path)
    return files


def summarize_diff(diff_text: str, max_files: int = 10) -> str:
    """Create a brief summary of a git diff.
    
    Args:
        diff_text: Git diff output
        max_files: Maximum files to list
        
    Returns:
        Summary string
    """
    files = extract_files_from_diff(diff_text)
    
    if not files:
        return "No changes"
    
    # Count additions and removals
    additions = diff_text.count('\n+') - diff_text.count('\n+++')
    removals = diff_text.count('\n-') - diff_text.count('\n---')
    
    file_list = ', '.join(files[:max_files])
    if len(files) > max_files:
        file_list += f" ... and {len(files) - max_files} more"
    
    return f"Files: {file_list} (+{additions}/-{removals})"
