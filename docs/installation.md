# Council Installation Guide

Detailed instructions for installing and configuring Council on your system.

---

## System Requirements

### Operating Systems

- **Linux**: Ubuntu 20.04+, Debian 11+, Fedora 35+, Arch Linux
- **macOS**: 11.0 (Big Sur) or later
- **Windows**: Windows 10/11 with WSL2 (recommended) or native Python

### Software Requirements

| Software | Minimum Version | How to Check |
|----------|-----------------|--------------|
| Python | 3.10 | `python --version` |
| pip | 21.0 | `pip --version` |
| Git | 2.20 | `git --version` |
| Chrome | 90+ | Chrome menu → Help → About Chrome |

### Hardware Requirements

- **RAM**: 512 MB minimum, 1 GB recommended
- **Disk**: 100 MB for installation, more for data storage
- **Network**: localhost access (no external network needed)

---

## Quick Install

```bash
# Clone the repository
git clone https://github.com/your-org/council.git
cd council

# Install everything
pip install -e packages/hub
pip install -e packages/cli
```

For detailed steps, see the sections below.

---

## Installing the Hub

### Step 1: Clone the Repository

```bash
git clone https://github.com/your-org/council.git
cd council
```

### Step 2: Create Virtual Environment (Recommended)

```bash
# Create venv
python -m venv venv

# Activate it
# On Linux/macOS:
source venv/bin/activate

# On Windows:
venv\Scripts\activate
```

### Step 3: Install Hub Package

```bash
cd packages/hub
pip install -e ".[dev]"
```

The `[dev]` extra installs test dependencies. For production, omit it:

```bash
pip install -e .
```

### Step 4: Verify Installation

```bash
python -c "from council_hub.main import app; print('Hub installed successfully!')"
```

### Step 5: Initialize Database

The database is created automatically on first run. To manually initialize:

```bash
# The database will be created at ~/.council/council.db
python -c "
from council_hub.db.repo import Database
db = Database()
print('Database initialized at ~/.council/council.db')
"
```

---

## Installing the CLI

### Step 1: Install Package

```bash
cd packages/cli
pip install -e ".[dev]"
```

### Step 2: Verify Installation

```bash
council --help
```

You should see:

```
Usage: council [OPTIONS] COMMAND [ARGS]...

  Council CLI - Bridge ChatGPT with AI coding agents

Commands:
  attach   Attach to a session and run a command
  pair     Pair CLI with an extension session
  run      Run a command and report results
  snapshot Show session state
  tail     Show recent events
```

### Step 3: Configure Hub URL (Optional)

If your hub runs on a non-default URL:

```bash
# Set environment variable
export COUNCIL_HUB_URL=http://127.0.0.1:7337

# Add to your shell profile for persistence
echo 'export COUNCIL_HUB_URL=http://127.0.0.1:7337' >> ~/.bashrc
```

---

## Installing the Chrome Extension

### Step 1: Open Chrome Extensions

1. Open Chrome
2. Navigate to `chrome://extensions/`
3. Enable **Developer mode** (toggle in top right)

### Step 2: Load the Extension

1. Click **Load unpacked**
2. Navigate to the `packages/extension` folder
3. Click **Select Folder**

### Step 3: Verify Installation

You should see "Council" in your extensions list with:
- ID: A generated extension ID
- Version: 0.1.0
- Status: On

### Step 4: Pin the Extension (Recommended)

1. Click the puzzle piece icon in Chrome's toolbar
2. Find "Council"
3. Click the pin icon

Now the Council icon is always visible in your toolbar.

---

## Platform-Specific Notes

### Linux

#### System Python vs User Python

If you encounter permission errors, use `--user`:

```bash
pip install --user -e packages/hub
pip install --user -e packages/cli
```

#### Headless Chrome (CI/CD)

For testing without a display:

```bash
# Install Chromium
sudo apt install chromium-browser

# Run Chrome with headless flag
chromium-browser --headless --disable-gpu
```

### macOS

#### Apple Silicon (M1/M2/M3)

Python packages should work natively. If you encounter issues:

```bash
# Use Homebrew Python
brew install python@3.11

# Create venv with correct Python
python3.11 -m venv venv
source venv/bin/activate
```

#### Permission Issues

If you get "unidentified developer" warnings:

1. System Preferences → Privacy & Security
2. Click "Open Anyway" next to the security warning

### Windows

#### Using WSL2 (Recommended)

WSL2 provides the best experience on Windows:

```bash
# In WSL2 terminal
sudo apt update
sudo apt install python3 python3-pip python3-venv git

# Then follow the Linux instructions
```

#### Native Windows

If using native Windows:

```powershell
# Create venv
python -m venv venv
.\venv\Scripts\activate

# Install packages
pip install -e packages\hub
pip install -e packages\cli
```

---

## Configuration

### Hub Configuration

Create a configuration file or use environment variables:

```bash
# ~/.bashrc or ~/.zshrc
export COUNCIL_DATA_DIR=~/.council
export COUNCIL_PORT=7337
export COUNCIL_HOST=127.0.0.1
```

### CLI Configuration

```bash
# ~/.bashrc or ~/.zshrc
export COUNCIL_HUB_URL=http://127.0.0.1:7337
```

### Extension Configuration

Click the extension icon to configure:

| Setting | Default | Description |
|---------|---------|-------------|
| Hub URL | `http://127.0.0.1:7337` | Hub server URL |
| Auto-draft Pull | Off | Automatically insert digest on milestones |
| Notify on Patch | Off | Show notification for patch events |

---

## Data Storage

### Default Locations

```
~/.council/
├── council.db          # SQLite database
├── artifacts/          # Large content storage
│   └── cgpt:abc123/   # Per-session directories
│       ├── art_001.bin
│       └── art_002.bin
└── pairings.json       # CLI pairing storage
```

### Custom Data Directory

```bash
export COUNCIL_DATA_DIR=/custom/path
council-hub
```

### Backup

```bash
# Backup everything
cp -r ~/.council ~/.council-backup

# Backup just the database
cp ~/.council/council.db ~/council-backup.db
```

---

## Running as a Service

### systemd (Linux)

Create a service file:

```bash
# ~/.config/systemd/user/council-hub.service
[Unit]
Description=Council Hub
After=network.target

[Service]
Type=simple
ExecStart=/path/to/venv/bin/uvicorn council_hub.main:app --host 127.0.0.1 --port 7337
Restart=on-failure

[Install]
WantedBy=default.target
```

Enable and start:

```bash
systemctl --user enable council-hub
systemctl --user start council-hub
```

### launchd (macOS)

Create a plist:

```xml
<!-- ~/Library/LaunchAgents/com.council.hub.plist -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.council.hub</string>
    <key>ProgramArguments</key>
    <array>
        <string>/path/to/venv/bin/uvicorn</string>
        <string>council_hub.main:app</string>
        <string>--host</string>
        <string>127.0.0.1</string>
        <string>--port</string>
        <string>7337</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
</dict>
</plist>
```

Load it:

```bash
launchctl load ~/Library/LaunchAgents/com.council.hub.plist
```

---

## Updating

### Update from Git

```bash
cd council
git pull origin main

# Reinstall packages
pip install -e packages/hub
pip install -e packages/cli

# Update extension in Chrome
# 1. Go to chrome://extensions/
# 2. Click the refresh icon on the Council extension
```

### Database Migrations

The database schema may change between versions. Check for migration scripts:

```bash
# If provided, run migration
python scripts/migrate.py
```

---

## Uninstalling

### Remove Packages

```bash
pip uninstall council-hub council-cli
```

### Remove Extension

1. Go to `chrome://extensions/`
2. Find Council
3. Click **Remove**

### Remove Data

```bash
rm -rf ~/.council
rm -rf ~/council  # If you cloned to home
```

---

## Verification Checklist

After installation, verify everything works:

- [ ] Hub starts: `council-hub`
- [ ] Health check: `curl http://127.0.0.1:7337/health`
- [ ] CLI works: `council --help`
- [ ] Extension visible in Chrome
- [ ] Extension connects: Open ChatGPT, see Council toolbar

---

## Troubleshooting Installation

### pip install fails

```bash
# Upgrade pip
pip install --upgrade pip

# Clear cache
pip cache purge

# Try again
pip install -e packages/hub
```

### Extension won't load

1. Make sure you selected the `packages/extension` folder
2. Check for errors in `chrome://extensions/` (click "Errors" on the extension card)
3. Try removing and re-adding the extension

### Port 7337 already in use

```bash
# Find what's using the port
lsof -i :7337

# Kill it
kill -9 <PID>

# Or use a different port
uvicorn council_hub.main:app --port 7338
```

### Database locked

```bash
# Stop all hub processes
pkill -f council_hub

# Remove lock (if exists)
rm ~/.council/council.db-journal

# Restart
council-hub
```

---

## Next Steps

- [User Guide](user-guide.md) - Learn how to use Council
- [Architecture](architecture.md) - Understand the system design
- [Protocol](protocol.md) - API reference
