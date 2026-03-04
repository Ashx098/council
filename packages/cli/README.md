# Council CLI

Command-line interface for Council - wrapper for AI coding agents.

## Installation

```bash
pip install -e ".[dev]"
```

## Usage

```bash
# Set hub URL
export COUNCIL_HUB_URL=http://127.0.0.1:7337

# Show recent events
council tail --session cgpt:demo --n 50

# Show session snapshot
council snapshot --session cgpt:demo

# Run a command
council run --session cgpt:demo --repo /path/to/repo -- pytest -q

# Attach to agent
council attach --session cgpt:demo --repo /path/to/repo -- your-agent
```

See docs/phase2_cli.md for full documentation.
