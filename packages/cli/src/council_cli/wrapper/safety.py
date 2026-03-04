"""Safety checks for command execution."""

from typing import List, Optional, Set
from dataclasses import dataclass


# Default allowed commands
DEFAULT_ALLOWLIST: Set[str] = {
    # Python
    "python", "python3", "python3.10", "python3.11", "python3.12",
    "pip", "pip3", "poetry", "uv",
    # Testing
    "pytest", "py.test", "nosetests",
    "go", "go test",
    "npm", "npm test", "yarn", "yarn test", "pnpm",
    "jest", "mocha", "vitest",
    "cargo", "cargo test",
    "mvn", "mvn test", "gradle", "gradle test",
    "ruby", "rspec", "bundle",
    # Linting/formatting
    "ruff", "black", "isort", "mypy", "pylint", "flake8",
    "eslint", "prettier", "tsc",
    "golint", "gofmt",
    "cargo clippy", "cargo fmt",
    # Build
    "make", "cmake", "gcc", "g++",
    "node", "tsc", "webpack", "vite", "rollup",
    # Git
    "git", "git status", "git diff", "git log", "git show",
    # Shell utilities (safe subset)
    "ls", "cat", "head", "tail", "grep", "find", "wc",
    "echo", "pwd", "which", "env",
    # Other
    "bash", "sh", "zsh",  # Shell itself is allowed, commands are checked
}


@dataclass
class SafetyCheckResult:
    """Result of safety check."""
    allowed: bool
    reason: str


def extract_base_command(command: List[str]) -> str:
    """Extract base command from command list.
    
    Args:
        command: Full command as list
        
    Returns:
        Base command string
    """
    if not command:
        return ""
    
    # Get the actual command (might be after -- separator)
    cmd = command[0]
    
    # Handle paths - get just the basename
    if '/' in cmd:
        cmd = cmd.split('/')[-1]
    
    return cmd


def check_command_allowed(command: List[str], 
                         allowlist: Optional[Set[str]] = None,
                         allow_any: bool = False) -> SafetyCheckResult:
    """Check if command is allowed.
    
    Args:
        command: Command to check as list
        allowlist: Custom allowlist (uses default if None)
        allow_any: If True, allow any command
        
    Returns:
        SafetyCheckResult with allowed status and reason
    """
    if allow_any:
        return SafetyCheckResult(allowed=True, reason="--allow-any-command flag set")
    
    if not command:
        return SafetyCheckResult(allowed=False, reason="Empty command")
    
    allowed_commands = allowlist if allowlist is not None else DEFAULT_ALLOWLIST
    
    base_cmd = extract_base_command(command)
    
    # Check exact match
    if base_cmd in allowed_commands:
        return SafetyCheckResult(allowed=True, reason=f"'{base_cmd}' in allowlist")
    
    # Check if it's a test command pattern
    if "test" in base_cmd.lower():
        return SafetyCheckResult(allowed=True, reason=f"'{base_cmd}' appears to be a test command")
    
    # Check for compound commands like "npm test"
    first_two = " ".join(command[:2]) if len(command) >= 2 else None
    if first_two and first_two in allowed_commands:
        return SafetyCheckResult(allowed=True, reason=f"'{first_two}' in allowlist")
    
    return SafetyCheckResult(
        allowed=False, 
        reason=f"'{base_cmd}' not in allowlist. Use --allow-any-command to override."
    )


def is_test_command(command: List[str]) -> bool:
    """Check if command looks like a test command.
    
    Args:
        command: Command to check
        
    Returns:
        True if it looks like a test command
    """
    if not command:
        return False
    
    cmd_str = " ".join(command).lower()
    
    test_patterns = [
        "pytest", "py.test", "test", "unittest",
        "go test", "cargo test",
        "npm test", "yarn test", "pnpm test",
        "jest", "mocha", "vitest",
        "mvn test", "gradle test",
        "rspec", "bundle exec rspec",
    ]
    
    for pattern in test_patterns:
        if pattern in cmd_str:
            return True
    
    return False
