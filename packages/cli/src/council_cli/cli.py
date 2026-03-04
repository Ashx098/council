"""Council CLI main entry point."""

import os
from typing import Optional

import typer
from rich.console import Console

from council_cli import __version__
from council_cli.commands.tail import tail
from council_cli.commands.snapshot import snapshot
from council_cli.commands.run import run
from council_cli.commands.attach import attach


app = typer.Typer(
    name="council",
    help="Council CLI - Wrapper for AI coding agents",
    add_completion=False,
)

console = Console()


@app.callback()
def main(
    version: bool = typer.Option(False, "--version", "-v", help="Show version"),
):
    """Council CLI - Wrapper for AI coding agents."""
    if version:
        console.print(f"council-cli version {__version__}")
        raise typer.Exit()


# Register commands
app.command("tail")(tail)
app.command("snapshot")(snapshot)
app.command("run")(run)
app.command("attach")(attach)


if __name__ == "__main__":
    app()
