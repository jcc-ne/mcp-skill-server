Most coding assistants now support skills natively, so an MCP server just for skill discovery isn't necessary. Where this package adds value is making skills' execution **deterministic and deployable** — with a fixed entry point and controlled execution, skills developed in your editor can run in non-sandboxed production environments. It also supports incremental loading, so agents discover skills on demand instead of loading everything upfront.

---
# MCP Skill Server

[![CI](https://github.com/jcc-ne/mcp-skill-server/actions/workflows/ci.yml/badge.svg)](https://github.com/jcc-ne/mcp-skill-server/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/mcp-skill-server)](https://pypi.org/project/mcp-skill-server/)
[![Python](https://img.shields.io/pypi/pyversions/mcp-skill-server)](https://pypi.org/project/mcp-skill-server/)
[![License](https://img.shields.io/github/license/jcc-ne/mcp-skill-server)](LICENSE)

Build agent skills where you work. Write a Python script, add a `SKILL.md`, and your agent can use it immediately. Iterate in real-time as part of your daily workflow. When it's ready, deploy the same skill to production — no rewrite needed.

## Why?

Most skill development looks like this: write code → deploy → test in a staging agent → realize it's wrong → redeploy → repeat. It's slow, and you never get to actually *use* the skill while building it.

MCP Skill Server flips this. It runs **on your machine, inside your editor** — Claude Code, Cursor, or Claude Desktop. You develop a skill and use it in your real work at the same time. That tight feedback loop (edit → save → use) means you discover what's missing naturally, not through artificial test scenarios.
The premise is if the skill doesn't work well with Claude Code, it's unlikely to work with a less sophisticated agent.


### How skills mature to survive in the outside world

Claude skills can already have companion scripts, but there's no formalized entry point — the agent decides how to invoke them. That works for local use, but it's not deployable: a production MCP server can't reliably call a skill if the execution path isn't fixed.

MCP Skill Server enforces a declared **`entry` field** in your SKILL.md frontmatter (e.g. `entry: uv run python my_script.py`). This gives you a single, fixed entry point that the server controls. Commands and parameters are discovered from the script's `--help` output — that's the source of truth, not the LLM's interpretation of your code.

```
1. Claude/coding agent skill                → SKILL.md + scripts, but no fixed entry — agent decides how to run them
2. Local MCP skill (+ entry)   → Fixed entry point, schema from --help, usable daily via this server
3. Production                  → Same skill, same entry — deployed to your enterprise MCP server
```

### Sharpen locally, then harden for production

Every agent that connects to the MCP server gets the same interface — `list_skills`, `get_skill`, `run_skill` — so the skill's description, parameter names, and help text are identical regardless of which agent calls them. That said, different agents have different strengths — a skill that works locally still needs testing with your production agent.

1. **Use it yourself** — build the skill, use it daily via Claude Code or Cursor. Fix descriptions and param names when the agent misuses the skill.
2. **Test with a weaker model** — try a smaller model to surface interface ambiguity.
3. **Add a deterministic entry point** — declare `entry` in SKILL.md for reliable, secure execution. Use `skill init` to scaffold it, `skill validate` to check readiness.
4. **Test with your production agent** — verify end-to-end in your target environment, then deploy.

## Install

### Claude Desktop (one-click)

[![Install with Claude Desktop](https://img.shields.io/badge/Claude_Desktop-Install_Server-orange?logo=claude)](claudedesktop://install?config=%7B%22mcpServers%22%3A%7B%22skills%22%3A%7B%22command%22%3A%22uvx%22%2C%22args%22%3A%5B%22mcp-skill-server%22%2C%22serve%22%2C%22.%2Fmy-skills%22%5D%7D%7D%7D)

After installing, edit the skills path in your Claude Desktop config to point to your skills directory.

### Claude Code

```bash
claude mcp add skills -- uvx mcp-skill-server serve /path/to/my/skills
```

### Cursor

Add to `.cursor/mcp.json` in your project (or Settings → MCP → Add Server):

```json
{
  "mcpServers": {
    "skills": {
      "command": "uvx",
      "args": ["mcp-skill-server", "serve", "/path/to/my/skills"]
    }
  }
}
```

### Manual install

```bash
# From PyPI (recommended)
uv pip install mcp-skill-server

# Or from source
git clone https://github.com/jcc-ne/mcp-skill-server
cd mcp-skill-server && uv sync

# Run the server
uvx mcp-skill-server serve /path/to/my/skills
```

Then add to your editor's MCP config:

```json
{
  "mcpServers": {
    "skills": {
      "command": "uvx",
      "args": ["mcp-skill-server", "serve", "/path/to/my/skills"]
    }
  }
}
```

## Creating a Skill

### Option A: Use `skill init` (recommended)

```bash
# Create a new skill
uv run mcp-skill-server init ./my_skills/hello -n "hello" -d "A friendly greeting"

# Or use the standalone command
uv run mcp-skill-init ./my_skills/hello -n "hello" -d "A friendly greeting"

# Promote an existing prompt-only Claude skill to a runnable MCP skill
uv run mcp-skill-init ./existing_claude_skill
```

### Option B: Manual setup

#### 1. Create a folder with your script

```
my_skills/
└── hello/
    ├── SKILL.md
    └── hello.py
```

#### 2. Add SKILL.md with frontmatter

```yaml
---
name: hello
description: A friendly greeting skill
entry: uv run python hello.py
---

# Hello Skill

Greets the user by name.
```

#### 3. Write your script with argparse

```python
# hello.py
import argparse

parser = argparse.ArgumentParser(description="Greeting skill")
parser.add_argument("--name", default="World", help="Name to greet")
args = parser.parse_args()

print(f"Hello, {args.name}!")
```

That's it. The server auto-discovers commands and parameters from your `--help` output — no config needed.

## Validating for Deployment

When a skill is ready to graduate to production:

```bash
uv run mcp-skill-server validate ./my_skills/hello
# or
uv run mcp-skill-validate ./my_skills/hello
```

Checks:
- Required frontmatter fields (name, description, entry)
- Entry command uses allowed runtime
- Script file exists
- Commands discoverable via `--help`

## How It Works

### MCP Tools

The server exposes four tools to your agent:

| Tool | Description |
|------|-------------|
| `list_skills` | List all available skills |
| `get_skill` | Get details about a skill (commands, parameters) |
| `run_skill` | Execute a skill with parameters |
| `refresh_skills` | Reload skills after you make changes |

### Schema Discovery

The server automatically discovers your skill's interface by parsing `--help` output:

```python
# Subcommands become separate commands
subparsers = parser.add_subparsers(dest='command')
analyze = subparsers.add_parser('analyze', help='Run analysis')

# Arguments become parameters with inferred types
analyze.add_argument('--year', type=int, required=True)  # int, required
analyze.add_argument('--file', type=str)                  # string, optional
```

### Output Files

Files saved to `output/` are automatically detected. Alternatively, print `OUTPUT_FILE:/path/to/file` to stdout.

## Plugins

### Output Handlers

Process files generated by skills (upload, copy, transform, etc.):

```python
from mcp_skill_server.plugins import OutputHandler, LocalOutputHandler

# Default: tracks local file paths
handler = LocalOutputHandler()

# Optional GCS handler (requires `uv sync --extra gcs`)
from mcp_skill_server.plugins import GCSOutputHandler
handler = GCSOutputHandler(
    bucket_name="my-bucket",
    folder_prefix="skills/outputs/",
)
```

### Response Formatters

Customize how execution results are formatted in MCP tool responses:

```python
from mcp_skill_server.plugins import ResponseFormatter

class CustomFormatter(ResponseFormatter):
    def format_execution_result(self, result, skill, command):
        return f"Result: {result.stdout}"

# Use with create_server()
from mcp_skill_server import create_server
server = create_server(
    "/path/to/skills",
    response_formatter=CustomFormatter()
)
```

## Development

```bash
git clone https://github.com/jcc-ne/mcp-skill-server
cd mcp-skill-server
uv sync --dev
uv run pytest
uv run mcp-skill-server serve examples/
```

## License

MIT
