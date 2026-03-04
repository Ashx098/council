"""Snapshot command - show session state."""

from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from council_cli.client.hub_client import HubClient


console = Console()


def snapshot(
    session_id: str = typer.Argument(..., help="Session ID"),
    after: int = typer.Option(0, "--after", "-a", help="Cursor to fetch events after"),
    hub_url: str = typer.Option("http://127.0.0.1:7337", envvar="COUNCIL_HUB_URL"),
):
    """Show a clipboard-friendly snapshot of session state.
    
    Displays:
    - Session ID
    - Current task (if present)
    - Latest test status (if present)
    - Latest patch summary (if present)
    - Open questions (if present)
    - Bounded digest text
    - Next cursor
    """
    client = HubClient(base_url=hub_url)
    
    try:
        # Get context and digest
        context = client.get_context(session_id)
        digest = client.get_digest(session_id, after=after)
        
        output_lines = []
        output_lines.append(f"━━━ Session: {session_id} ━━━")
        output_lines.append("")
        
        # Repo info
        if context.repo_root:
            output_lines.append(f"Repo: {context.repo_root}")
        if context.title:
            output_lines.append(f"Title: {context.title}")
        output_lines.append("")
        
        # Current task
        if context.current_task:
            output_lines.append("📋 CURRENT TASK:")
            task_body = context.current_task.get("body", "")
            output_lines.append(f"  {task_body[:200]}")
            output_lines.append("")
        
        # Test status
        if context.last_test_status:
            output_lines.append("🧪 LAST TEST STATUS:")
            meta = context.last_test_status.get("meta", {})
            exit_code = meta.get("exit_code", "?")
            passed = meta.get("passed", "?")
            failed = meta.get("failed", "?")
            status = "✅ PASS" if exit_code == 0 else "❌ FAIL"
            output_lines.append(f"  {status} | Passed: {passed}, Failed: {failed}")
            output_lines.append("")
        
        # Last patch
        if context.last_patch:
            output_lines.append("📝 LAST PATCH:")
            patch_body = context.last_patch.get("body", "")
            output_lines.append(f"  {patch_body[:200]}")
            artifact_id = context.last_patch.get("meta", {}).get("artifact_id")
            if artifact_id:
                output_lines.append(f"  Artifact: {artifact_id[:8]}...")
            output_lines.append("")
        
        # Pinned decisions
        if context.pinned_decisions:
            output_lines.append("📌 PINNED DECISIONS:")
            for decision in context.pinned_decisions[:5]:
                body = decision.get("body", "")
                output_lines.append(f"  • {body[:100]}")
            output_lines.append("")
        
        # Digest
        output_lines.append("📄 DIGEST:")
        output_lines.append(digest.digest_text)
        output_lines.append("")
        
        # Cursor info
        output_lines.append(f"━━━ next_cursor: {digest.next_cursor} | has_more: {digest.has_more} ━━━")
        
        # Print as panel
        console.print(Panel('\n'.join(output_lines), title="Council Snapshot", 
                           title_align="left", border_style="blue"))
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    finally:
        client.close()
