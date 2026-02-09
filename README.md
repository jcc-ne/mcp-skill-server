# MCP Skill Server

A local MCP server for developing and testing skills before deploying them to production agents.

## Why?

Building skills for enterprise agents is slow: write code → deploy → test → iterate. This tool lets you **dog food locally** - test skills on your machine before pushing to production.

## Quick Start

```bash
# Install with uv (recommended)
uv pip install mcp-skill-server

# Or install from source
git clone https://github.com/your-org/mcp-skill-server
cd mcp-skill-server
uv sync

# Run the server
uv run mcp-skill-server /path/to/my/skills
```

## Configuration

### Claude Code

Add to your `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "skills": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/mcp-skill-server", "mcp-skill-server", "/path/to/my/skills"]
    }
  }
}
```

Or configure per-project in `.claude/settings.json` in your project root.

### Cursor

Add to your Cursor MCP settings (Settings → MCP → Add Server):

```json
{
  "mcpServers": {
    "skills": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/mcp-skill-server", "mcp-skill-server", "/path/to/my/skills"]
    }
  }
}
```

Or add to `.cursor/mcp.json` in your project:

```json
{
  "mcpServers": {
    "skills": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/mcp-skill-server", "mcp-skill-server", "/path/to/my/skills"]
    }
  }
}
```

### Claude Desktop

Add to `~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) or `%APPDATA%\Claude\claude_desktop_config.json` (Windows):

```json
{
  "mcpServers": {
    "skills": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/mcp-skill-server", "mcp-skill-server", "/path/to/my/skills"]
    }
  }
}
```

### Mounting onto an existing FastAPI / Starlette app

If you already have a FastAPI app (potentially with another MCP server mounted), you can add the skill server as a sub-application using streamable HTTP transport:

```python
from fastapi import FastAPI
from mcp_skill_server import create_starlette_app

app = FastAPI()

# Your existing MCP server
app.mount("/other-mcp", other_mcp_app)

# Mount the skill server alongside it
app.mount("/skills", create_starlette_app("/path/to/my/skills"))
```

Each MCP server lives at its own path prefix, so clients connect to them independently (e.g. `http://localhost:8000/skills/` for the skill server).

`create_starlette_app` accepts optional keyword arguments:

| Argument | Default | Description |
|----------|---------|-------------|
| `stateless` | `False` | No session persistence across requests. Useful for horizontal scaling. |
| `json_response` | `False` | Return plain JSON instead of SSE streams. |
| `output_handler` | `LocalOutputHandler()` | Plugin for processing skill output files. |

## Creating a Skill

### 1. Create a folder with your script

```
my_skills/
└── hello/
    ├── SKILL.md
    └── hello.py
```

### 2. Add SKILL.md with frontmatter

```yaml
---
name: hello
description: A friendly greeting skill
entry: python hello.py
---

# Hello Skill

Greets the user by name.
```

### 3. Write your script with argparse

```python
# hello.py
import argparse

parser = argparse.ArgumentParser(description="Greeting skill")
parser.add_argument("--name", default="World", help="Name to greet")
args = parser.parse_args()

print(f"Hello, {args.name}!")
```

### 4. Test it

The MCP server automatically discovers:
- Subcommands from `--help`
- Parameters and their types
- Required vs optional arguments

## MCP Tools

The server exposes these tools:

| Tool | Description |
|------|-------------|
| `list_skills` | List all available skills |
| `get_skill` | Get details about a skill (commands, parameters) |
| `run_skill` | Execute a skill with parameters |
| `refresh_skills` | Reload skills after changes |

## Skill Format

Skills are defined by a `SKILL.md` file with YAML frontmatter:

```yaml
---
name: my-skill          # Unique identifier
description: What it does   # Shown in skill list
entry: python script.py     # How to run it
---

# Documentation

Markdown docs shown when inspecting the skill.
```

## Schema Discovery

The server automatically discovers your skill's interface by parsing `--help` output:

```python
# Subcommands become separate commands
subparsers = parser.add_subparsers(dest='command')
analyze = subparsers.add_parser('analyze', help='Run analysis')

# Arguments become parameters with inferred types
analyze.add_argument('--year', type=int, required=True)  # int, required
analyze.add_argument('--file', type=str)                  # string, optional
```

## Output Files

Files saved to `output/` are automatically detected. Alternatively, print `OUTPUT_FILE:/path/to/file` to stdout.

## Development

```bash
# Clone and install
git clone https://github.com/your-org/mcp-skill-server
cd mcp-skill-server
uv sync --dev

# Run tests
uv run pytest

# Run server with example skills
uv run mcp-skill-server examples/
```

## Optional: GCS Output Handler

To upload skill outputs to Google Cloud Storage:

```bash
uv sync --extra gcs
```

```python
from mcp_skill_server.plugins import GCSOutputHandler

handler = GCSOutputHandler(
    bucket_name="my-bucket",
    folder_prefix="skills/outputs/",
)
```

## License

MIT
