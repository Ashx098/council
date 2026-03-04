"""Tail command - show recent events."""

from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from council_cli.client.hub_client import HubClient
from council_cli.utils.text import truncate


console = Console()


def tail(
    session_id: str = typer.Argument(..., help="Session ID"),
    n: int = typer.Option(50, "--n", "-n", help="Number of events to show"),
    hub_url: str = typer.Option("http://127.0.0.1:7337", envvar="COUNCIL_HUB_URL"),
):
    """Show last N events for a session.
    
    Prints compact rows: event_id, ts, source, type, first 120 chars of body.
    """
    client = HubClient(base_url=hub_url)
    
    try:
        events = client.get_last_n_events(session_id, n)
        
        if not events:
            console.print(f"[yellow]No events found for session {session_id}[/yellow]")
            return
        
        table = Table(title=f"Last {len(events)} events for {session_id}")
        table.add_column("ID", style="cyan", width=6)
        table.add_column("Time", style="dim", width=19)
        table.add_column("Source", style="green", width=10)
        table.add_column("Type", style="magenta", width=12)
        table.add_column("Body", width=80)
        
        for event in events:
            ts_short = event.ts[11:19] if len(event.ts) >= 19 else event.ts
            body_short = truncate(event.body.replace('\n', ' '), 80)
            table.add_row(
                str(event.event_id),
                ts_short,
                event.source,
                event.type,
                body_short
            )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)
    finally:
        client.close()
