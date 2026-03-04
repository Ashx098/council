"""Attach command - run agent with monitoring."""

import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.panel import Panel

from council_cli.client.hub_client import HubClient
from council_cli.wrapper.safety import check_command_allowed
from council_cli.wrapper.runner import run_command, summarize_result
from council_cli.wrapper.gitwatch import get_git_state, summarize_diff, format_patch_summary
from council_cli.wrapper.capture import OutputCapture, OutputBatch, split_text_for_events
from council_cli.wrapper.report import RunReportData, format_run_report, create_run_report_meta
from council_cli.utils.text import summarize_diff as text_summarize_diff


console = Console()


def attach(
    session_id: str = typer.Argument(..., help="Session ID"),
    repo: Path = typer.Option(..., "--repo", "-r", help="Repository path", exists=True),
    command: List[str] = typer.Argument(..., help="Agent command to run (after --)"),
    hub_url: str = typer.Option("http://127.0.0.1:7337", envvar="COUNCIL_HUB_URL"),
    git_interval: float = typer.Option(2.0, "--git-interval", help="Git check interval in seconds"),
    batch_interval: float = typer.Option(2.0, "--batch-interval", help="Output batch interval"),
    batch_lines: int = typer.Option(50, "--batch-lines", help="Max lines per output batch"),
    allow_any_command: bool = typer.Option(False, "--allow-any-command", help="Bypass allowlist"),
):
    """Attach to an agent process and monitor its activity.
    
    1. Pulls context from hub and prints "Supervisor Brief"
    2. Starts agent process
    3. Batches stdout/stderr → message events (throttled)
    4. Watches git diffs periodically → patch artifacts and events
    5. Emits run_report at end
    """
    client = HubClient(base_url=hub_url)
    
    # Batching state
    pending_batches: List[OutputBatch] = []
    last_git_state = None
    last_git_check = 0
    files_touched = []
    
    def on_output_batch(batch: OutputBatch):
        """Handle output batch."""
        pending_batches.append(batch)
    
    try:
        # Get context and print brief
        context = client.get_context(session_id)
        
        brief_lines = [f"Session: {session_id}"]
        if context.repo_root:
            brief_lines.append(f"Repo: {context.repo_root}")
        if context.current_task:
            brief_lines.append(f"Task: {context.current_task.get('body', '')[:100]}")
        if context.last_test_status:
            meta = context.last_test_status.get("meta", {})
            brief_lines.append(f"Last Test: exit={meta.get('exit_code', '?')}")
        if context.pinned_decisions:
            brief_lines.append(f"Decisions: {len(context.pinned_decisions)} pinned")
        
        console.print(Panel('\n'.join(brief_lines), title="📋 Supervisor Brief", 
                           title_align="left", border_style="green"))
        
        # Safety check
        safety = check_command_allowed(command, allow_any=allow_any_command)
        if not safety.allowed:
            console.print(f"[red]Command blocked: {safety.reason}[/red]")
            raise typer.Exit(1)
        
        console.print(f"[dim]Starting: {' '.join(command)}[/dim]")
        
        # Start process
        start_time = time.time()
        process = subprocess.Popen(
            command,
            cwd=repo,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,  # Line buffered
        )
        
        # Set up capture
        stdout_capture = OutputCapture(
            "stdout", on_output_batch, batch_interval, batch_lines)
        stderr_capture = OutputCapture(
            "stderr", on_output_batch, batch_interval, batch_lines)
        
        # Read threads
        import threading
        
        def read_stdout():
            for line in iter(process.stdout.readline, ''):
                if line:
                    stdout_capture.add_line(line.rstrip('\n'))
        
        def read_stderr():
            for line in iter(process.stderr.readline, ''):
                if line:
                    stderr_capture.add_line(line.rstrip('\n'))
        
        stdout_thread = threading.Thread(target=read_stdout, daemon=True)
        stderr_thread = threading.Thread(target=read_stderr, daemon=True)
        
        stdout_capture.start()
        stderr_capture.start()
        stdout_thread.start()
        stderr_thread.start()
        
        # Monitor loop
        while process.poll() is None:
            # Flush pending batches
            while pending_batches:
                batch = pending_batches.pop(0)
                chunks = split_text_for_events(batch.text, max_size=8000)
                for chunk in chunks:
                    client.ingest_event(
                        session_id=session_id,
                        source="wrapper",
                        type_="message",
                        body=chunk,
                        meta={"stream": batch.stream, "line_count": batch.line_count}
                    )
            
            # Check git state
            now = time.time()
            if now - last_git_check >= git_interval:
                last_git_check = now
                current_state = get_git_state(repo)
                
                if last_git_state is None or current_state.diff_hash != last_git_state.diff_hash:
                    if current_state.diff_text:
                        # Diff changed, upload artifact
                        summary = summarize_diff(current_state.diff_text)
                        artifact_id = None
                        
                        # Upload artifact
                        response = client.ingest_event(
                            session_id=session_id,
                            source="wrapper",
                            type_="patch",
                            body=text_summarize_diff(current_state.diff_text),
                            meta={
                                "files_changed": current_state.files_changed,
                                "dirty": current_state.dirty,
                            },
                            artifacts=[{"kind": "patch", "content": current_state.diff_text}]
                        )
                        artifact_id = response.get("meta", {}).get("artifact_id")
                        
                        console.print(f"[dim]Patch: {len(current_state.files_changed)} files changed[/]")
                        files_touched.extend(current_state.files_changed)
                    
                    last_git_state = current_state
            
            time.sleep(0.1)
        
        # Process ended
        exit_code = process.returncode
        duration = time.time() - start_time
        
        # Stop captures and flush
        stdout_capture.stop()
        stderr_capture.stop()
        
        # Flush remaining batches
        while pending_batches:
            batch = pending_batches.pop(0)
            chunks = split_text_for_events(batch.text, max_size=8000)
            for chunk in chunks:
                client.ingest_event(
                    session_id=session_id,
                    source="wrapper",
                    type_="message",
                    body=chunk,
                    meta={"stream": batch.stream, "line_count": batch.line_count}
                )
        
        # Final git state
        final_state = get_git_state(repo)
        files_touched = list(set(files_touched + final_state.files_changed))
        
        # Emit run_report
        report_data = RunReportData(
            session_id=session_id,
            repo_path=str(repo),
            command=command,
            exit_code=exit_code,
            duration_seconds=duration,
            dirty=final_state.dirty,
            files_touched=files_touched[:20],
        )
        
        client.ingest_event(
            session_id=session_id,
            source="wrapper",
            type_="run_report",
            body=format_run_report(report_data),
            meta=create_run_report_meta(report_data)
        )
        
        console.print(f"\n[{'green' if exit_code == 0 else 'red'}]Agent finished: exit {exit_code} ({duration:.1f}s)[/]")
        console.print(f"[dim]Files touched: {len(files_touched)}[/]")
        
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/yellow]")
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    finally:
        client.close()
