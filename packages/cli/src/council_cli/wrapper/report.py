"""Run report generation."""

from dataclasses import dataclass
from typing import List, Optional

from council_cli.utils.time import format_duration


@dataclass
class RunReportData:
    """Data for a run report."""
    session_id: str
    repo_path: str
    command: List[str]
    exit_code: int
    duration_seconds: float
    dirty: bool
    files_touched: List[str]
    test_passed: Optional[int] = None
    test_failed: Optional[int] = None
    questions: Optional[List[str]] = None
    

def format_run_report(data: RunReportData) -> str:
    """Format run report for event body.
    
    Args:
        data: Run report data
        
    Returns:
        Formatted report string
    """
    lines = []
    
    # Status
    status = "SUCCESS" if data.exit_code == 0 else f"FAILED (exit {data.exit_code})"
    lines.append(f"Status: {status}")
    
    # Duration
    lines.append(f"Duration: {format_duration(data.duration_seconds)}")
    
    # Command
    cmd_str = ' '.join(data.command)
    if len(cmd_str) > 60:
        cmd_str = cmd_str[:57] + "..."
    lines.append(f"Command: {cmd_str}")
    
    # Repo state
    if data.dirty:
        lines.append(f"Repo: dirty ({len(data.files_touched)} files changed)")
    else:
        lines.append("Repo: clean")
    
    # Test results if available
    if data.test_passed is not None or data.test_failed is not None:
        passed = data.test_passed or 0
        failed = data.test_failed or 0
        lines.append(f"Tests: {passed} passed, {failed} failed")
    
    # Questions
    if data.questions:
        lines.append("")
        lines.append("Open Questions:")
        for q in data.questions[:5]:
            lines.append(f"  - {q[:100]}")
    
    return '\n'.join(lines)


def create_run_report_meta(data: RunReportData) -> dict:
    """Create metadata dict for run report event.
    
    Args:
        data: Run report data
        
    Returns:
        Metadata dict
    """
    return {
        "status": "success" if data.exit_code == 0 else "failure",
        "exit_code": data.exit_code,
        "duration_seconds": data.duration_seconds,
        "dirty": data.dirty,
        "files_touched": data.files_touched[:20],  # Limit
        "test_passed": data.test_passed,
        "test_failed": data.test_failed,
        "questions": data.questions,
    }
