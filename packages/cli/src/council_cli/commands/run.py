"""Run command - execute a command and log results."""

from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console

from council_cli.client.hub_client import HubClient
from council_cli.wrapper.safety import check_command_allowed, is_test_command
from council_cli.wrapper.runner import run_command, summarize_result


console = Console()


def run(
    session_id: str = typer.Argument(..., help="Session ID"),
    repo: Path = typer.Option(..., "--repo", "-r", help="Repository path", exists=True),
    command: List[str] = typer.Argument(..., help="Command to run (after --)"),
    hub_url: str = typer.Option("http://127.0.0.1:7337", envvar="COUNCIL_HUB_URL"),
    allow_any_command: bool = typer.Option(False, "--allow-any-command", help="Bypass allowlist"),
    timeout: float = typer.Option(300.0, "--timeout", "-t", help="Command timeout in seconds"),
):
    """Run a command and upload results to hub.
    
    Safety: Commands must be in allowlist unless --allow-any-command is set.
    
    Uploads output as artifact (test_log for test commands, command_output otherwise).
    Emits tool_run event, and test_result for test commands.
    """
    client = HubClient(base_url=hub_url)
    
    try:
        # Safety check
        safety = check_command_allowed(command, allow_any=allow_any_command)
        if not safety.allowed:
            console.print(f"[red]Command blocked: {safety.reason}[/red]")
            raise typer.Exit(1)
        
        console.print(f"[dim]Running: {' '.join(command)}[/dim]")
        
        # Run the command
        result = run_command(command, repo, timeout=timeout)
        
        # Summarize
        summary = summarize_result(result)
        console.print(f"[{'green' if result.success else 'red'}]{summary}[/]")
        
        # Determine artifact kind
        is_test = is_test_command(command)
        artifact_kind = "test_log" if is_test else "command_output"
        
        # Prepare output for artifact
        output = result.combined_output
        if not output:
            output = "(no output)"
        
        # Build event body (short summary, not full output)
        body = f"{' '.join(command[:3])}... - exit {result.exit_code} ({result.duration_ms}ms)"
        if len(body) > 100:
            body = body[:97] + "..."
        
        # Upload with artifact
        artifacts = [{"kind": artifact_kind, "content": output}]
        meta = {
            "command": ' '.join(command),
            "exit_code": result.exit_code,
            "duration_ms": result.duration_ms,
        }
        
        event_type = "test_result" if is_test else "tool_run"
        
        response = client.ingest_event(
            session_id=session_id,
            source="wrapper",
            type_=event_type,
            body=body,
            meta=meta,
            artifacts=artifacts
        )
        
        # For test_result, add pass/fail counts to meta if we can parse them
        if is_test:
            console.print(f"[dim]Event ID: {response.get('event_id')} | Artifact: {response.get('meta', {}).get('artifact_id', 'N/A')[:8]}...[/]")
        else:
            console.print(f"[dim]Event ID: {response.get('event_id')}[/]")
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    finally:
        client.close()
