"""Command runner."""

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from council_cli.utils.time import format_duration


@dataclass
class RunResult:
    """Result of a command run."""
    command: List[str]
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    cwd: Path
    
    @property
    def combined_output(self) -> str:
        """Get combined stdout and stderr."""
        parts = []
        if self.stdout:
            parts.append(self.stdout)
        if self.stderr:
            parts.append(self.stderr)
        return '\n'.join(parts)
    
    @property
    def duration_ms(self) -> int:
        """Get duration in milliseconds."""
        return int(self.duration_seconds * 1000)
    
    @property
    def success(self) -> bool:
        """Check if command succeeded."""
        return self.exit_code == 0


def run_command(command: List[str], cwd: Path, 
                timeout: Optional[float] = None) -> RunResult:
    """Run a command and capture output.
    
    Args:
        command: Command to run as list
        cwd: Working directory
        timeout: Optional timeout in seconds
        
    Returns:
        RunResult with output and metadata
    """
    start_time = time.time()
    
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        exit_code = result.returncode
        stdout = result.stdout
        stderr = result.stderr
    except subprocess.TimeoutExpired:
        exit_code = -1
        stdout = ""
        stderr = f"Command timed out after {timeout} seconds"
    except Exception as e:
        exit_code = -1
        stdout = ""
        stderr = str(e)
    
    duration = time.time() - start_time
    
    return RunResult(
        command=command,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        duration_seconds=duration,
        cwd=cwd
    )


def format_command(command: List[str]) -> str:
    """Format command for display.
    
    Args:
        command: Command list
        
    Returns:
        Formatted string
    """
    return ' '.join(command)


def summarize_result(result: RunResult, max_len: int = 200) -> str:
    """Create brief summary of run result.
    
    Args:
        result: Run result
        max_len: Maximum length
        
    Returns:
        Summary string
    """
    status = "OK" if result.success else f"EXIT {result.exit_code}"
    duration = format_duration(result.duration_seconds)
    cmd = format_command(result.command)
    
    # Truncate command if needed
    if len(cmd) > 60:
        cmd = cmd[:57] + "..."
    
    return f"[{status}] {cmd} ({duration})"
