"""Council CLI pair command - Pair with extension session."""

import os
import json
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from council_cli.client.hub_client import HubClient

console = Console()

# Local storage for pair bindings
PAIRINGS_FILE = Path.home() / ".council" / "pairings.json"


def load_pairings() -> dict:
    """Load local pairings from file."""
    if not PAIRINGS_FILE.exists():
        return {}
    try:
        return json.loads(PAIRINGS_FILE.read_text())
    except (json.JSONDecodeError, IOError):
        return {}


def save_pairings(pairings: dict):
    """Save local pairings to file."""
    PAIRINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PAIRINGS_FILE.write_text(json.dumps(pairings, indent=2))


def pair(
    code: str = typer.Argument(..., help="Pairing code to claim"),
    repo: Optional[str] = typer.Option(None, "--repo", "-r", help="Repository path to bind"),
    hub_url: Optional[str] = typer.Option(None, "--hub", "-h", help="Hub URL"),
    list_pairs: bool = typer.Option(False, "--list", "-l", help="List existing pairings"),
    remove: Optional[str] = typer.Option(None, "--remove", help="Remove a pairing by code"),
):
    """Pair CLI with an extension session.
    
    Usage:
        council pair AB7K                    # Claim pairing code
        council pair AB7K --repo ~/myrepo    # Claim with repo binding
        council pair --list                  # List existing pairings
        council pair --remove AB7K           # Remove a pairing
    
    After claiming a pairing code, you can use the code in place of session ID:
        council attach --pair AB7K -- opencode
    """
    # Handle list command
    if list_pairs:
        pairings = load_pairings()
        if not pairings:
            console.print("[yellow]No pairings found[/yellow]")
            return
        
        table = Table(title="Council Pairings")
        table.add_column("Code", style="cyan")
        table.add_column("Session ID", style="green")
        table.add_column("Repo", style="blue")
        
        for pair_code, data in pairings.items():
            table.add_row(
                pair_code,
                data.get("session_id", "-"),
                data.get("repo_root") or "-"
            )
        
        console.print(table)
        return
    
    # Handle remove command
    if remove:
        pairings = load_pairings()
        if remove.upper() in pairings:
            del pairings[remove.upper()]
            save_pairings(pairings)
            console.print(f"[green]Removed pairing {remove.upper()}[/green]")
        else:
            console.print(f"[yellow]Pairing {remove.upper()} not found[/yellow]")
        return
    
    # Claim the pairing code
    hub = HubClient(hub_url)
    
    # Get repo path
    repo_root = repo
    if repo_root:
        repo_root = os.path.abspath(os.path.expanduser(repo_root))
    
    # Get hostname for claimed_by
    import socket
    claimed_by = socket.gethostname()
    
    console.print(f"[cyan]Claiming pairing code {code.upper()}...[/cyan]")
    
    try:
        result = hub.claim_pairing(code, claimed_by=claimed_by, repo_root=repo_root)
        
        session_id = result.get("session_id")
        pair_code = result.get("code")
        
        # Save to local pairings
        pairings = load_pairings()
        pairings[pair_code] = {
            "session_id": session_id,
            "repo_root": repo_root,
            "claimed_by": claimed_by,
            "claimed_at": result.get("claimed_at")
        }
        save_pairings(pairings)
        
        console.print(f"[green]✓ Paired successfully![/green]")
        console.print(f"  Code: [cyan]{pair_code}[/cyan]")
        console.print(f"  Session: [green]{session_id}[/green]")
        if repo_root:
            console.print(f"  Repo: [blue]{repo_root}[/blue]")
        console.print()
        console.print("[dim]You can now use:[/dim]")
        console.print(f"  [cyan]council attach --pair {pair_code} -- <command>[/cyan]")
        
    except Exception as e:
        console.print(f"[red]Failed to claim pairing code: {e}[/red]")
        raise typer.Exit(1)


def get_session_from_pair(pair_code: str) -> Optional[str]:
    """Get session ID from pair code.
    
    Looks up locally stored pairing.
    """
    pairings = load_pairings()
    data = pairings.get(pair_code.upper())
    return data.get("session_id") if data else None


def get_repo_from_pair(pair_code: str) -> Optional[str]:
    """Get repo path from pair code."""
    pairings = load_pairings()
    data = pairings.get(pair_code.upper())
    return data.get("repo_root") if data else None
