# MCP Skill Server

A local MCP server for developing and testing skills before deploying them to production agents.

## Why?

Building skills for enterprise agents is slow: write code → deploy → test → iterate. This tool lets you **dog food locally** - test skills on your machine before pushing to production.

## Quick Start

```bash
# Install
pip install mcp-skill-server

# Point to your skills folder
mcp-skill-server /path/to/my/skills
```

Add to your MCP client config (e.g., Claude Desktop):

```json
{
  "mcpServers": {
    "skills": {
      "command": "mcp-skill-server",
      "args": ["/path/to/my/skills"]
    }
  }
}
```

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
git clone https://github.com/guideline-data/mcp-skill-server
cd mcp-skill-server
pip install -e ".[dev]"

# Run tests
pytest

# Run server with example skills
mcp-skill-server examples/
```

## License

MIT
