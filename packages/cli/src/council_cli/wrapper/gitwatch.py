from typing import List, Optional

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
            parts = line.split(' ')
            if len(parts) >= 4:
                fname = parts[3]
                if fname.startswith('b/'):
                    fname = fname[2:]
                if fname not in files:
                    files.append(fname)
    return files


"""Git repository watching."""

import hashlib
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple


@dataclass
class GitState:
    """Snapshot of git state."""
    diff_hash: str
    diff_text: str
    dirty: bool
    staged_diff: str
    files_changed: List[str]
    

@dataclass
class GitDiffSummary:
    """Summary of a git diff."""
    files: List[str]
    additions: int
    removals: int
    is_staged: bool
    is_dirty: bool


def run_git(repo_path: Path, *args: str) -> Tuple[str, str, int]:
    """Run a git command.
    
    Args:
        repo_path: Path to repository
        *args: Git command arguments
        
    Returns:
        Tuple of (stdout, stderr, return_code)
    """
    result = subprocess.run(
        ["git"] + list(args),
        cwd=repo_path,
        capture_output=True,
        text=True
    )
    return result.stdout, result.stderr, result.returncode


def get_git_status(repo_path: Path) -> Tuple[bool, List[str]]:
    """Get git status.
    
    Args:
        repo_path: Path to repository
        
    Returns:
        Tuple of (is_dirty, list of changed files)
    """
    stdout, _, rc = run_git(repo_path, "status", "--porcelain")
    
    if rc != 0:
        return False, []
    
    files = []
    for line in stdout.strip().split('\n'):
        if line:
            # Format: XY filename
            parts = line.strip().split(None, 1)
            if len(parts) >= 2:
                files.append(parts[1])
            elif len(parts) == 1:
                files.append(parts[0])
    
    return bool(files), files


def get_git_diff(repo_path: Path, staged: bool = False) -> str:
    """Get git diff.
    
    Args:
        repo_path: Path to repository
        staged: If True, get staged diff (--cached)
        
    Returns:
        Diff output
    """
    args = ["diff"]
    if staged:
        args.append("--cached")
    
    stdout, _, _ = run_git(repo_path, *args)
    return stdout


def get_git_state(repo_path: Path) -> GitState:
    """Get current git state.
    
    Args:
        repo_path: Path to repository
        
    Returns:
        GitState snapshot
    """
    dirty, files = get_git_status(repo_path)
    diff_text = get_git_diff(repo_path, staged=False)
    staged_diff = get_git_diff(repo_path, staged=True)
    
    # Hash the combined diff for change detection
    combined = diff_text + staged_diff
    diff_hash = hashlib.sha256(combined.encode()).hexdigest()[:16]
    
    return GitState(
        diff_hash=diff_hash,
        diff_text=diff_text,
        dirty=dirty,
        staged_diff=staged_diff,
        files_changed=files
    )


def summarize_diff(diff_text: str) -> GitDiffSummary:
    """Summarize a diff.
    
    Args:
        diff_text: Git diff output
        
    Returns:
        GitDiffSummary
    """
    files = []
    additions = 0
    removals = 0
    
    for line in diff_text.split('\n'):
        if line.startswith('diff --git '):
            # Extract filename
            parts = line.split(' ')
            if len(parts) >= 4:
                fname = parts[3]
                if fname.startswith('b/'):
                    fname = fname[2:]
                if fname not in files:
                    files.append(fname)
        elif line.startswith('+') and not line.startswith('+++'):
            additions += 1
        elif line.startswith('-') and not line.startswith('---'):
            removals += 1
    
    return GitDiffSummary(
        files=files,
        additions=additions,
        removals=removals,
        is_staged=False,
        is_dirty=bool(files)
    )


def format_patch_summary(summary: GitDiffSummary, artifact_id: Optional[str] = None) -> str:
    """Format a patch summary for event body.
    
    Args:
        summary: Git diff summary
        artifact_id: Optional artifact ID reference
        
    Returns:
        Summary string
    """
    if not summary.files:
        return "No changes"
    
    parts = []
    
    # File list
    if len(summary.files) <= 5:
        parts.append(f"Files: {', '.join(summary.files)}")
    else:
        parts.append(f"Files: {', '.join(summary.files[:5])} ... and {len(summary.files) - 5} more")
    
    # Line counts
    parts.append(f"+{summary.additions}/-{summary.removals} lines")
    
    # Artifact reference
    if artifact_id:
        parts.append(f"artifact: {artifact_id[:8]}...")
    
    return " | ".join(parts)
