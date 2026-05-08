"""Tests for language-agnostic --describe-schema discovery in loader."""

import json
import shutil
import tempfile
from pathlib import Path

import pytest

from mcp_skill_server.loader import discover_commands


def _make_describe_script(skill_dir: Path, payload: dict) -> str:
    """Write a tiny shell script that echoes the JSON payload only when
    invoked with --describe-schema, and exits non-zero otherwise (so the
    argparse fallback would have nothing to parse)."""
    script = skill_dir / "describe.sh"
    script.write_text(
        "#!/usr/bin/env bash\n"
        'if [ "$1" = "--describe-schema" ]; then\n'
        f"  cat <<'EOF'\n{json.dumps(payload)}\nEOF\n"
        "  exit 0\n"
        "fi\n"
        "echo 'unsupported' >&2\n"
        "exit 2\n"
    )
    script.chmod(0o755)
    return f"bash {script.name}"


@pytest.fixture
def skill_dir():
    tmp = tempfile.mkdtemp()
    yield Path(tmp)
    shutil.rmtree(tmp)


@pytest.mark.asyncio
async def test_describe_schema_single_command(skill_dir):
    payload = {
        "commands": {
            "default": {
                "description": "Greet a user",
                "parameters": [
                    {
                        "name": "name",
                        "required": True,
                        "type": "string",
                        "description": "Person to greet",
                    }
                ],
            }
        }
    }
    entry = _make_describe_script(skill_dir, payload)

    commands = await discover_commands(entry, skill_dir)

    assert set(commands) == {"default"}
    cmd = commands["default"]
    assert cmd.description == "Greet a user"
    assert cmd.bash_template == entry  # no subcommand suffix for "default"
    assert len(cmd.parameters) == 1
    p = cmd.parameters[0]
    assert p.name == "name"
    assert p.required is True
    assert p.type == "string"


@pytest.mark.asyncio
async def test_describe_schema_subcommands(skill_dir):
    payload = {
        "commands": {
            "infer": {
                "description": "Infer NAICS",
                "parameters": [
                    {"name": "plan_year", "required": True, "type": "int"},
                ],
            },
            "summarize": {
                "description": "Summarize results",
                "parameters": [],
            },
        }
    }
    entry = _make_describe_script(skill_dir, payload)

    commands = await discover_commands(entry, skill_dir)

    assert set(commands) == {"infer", "summarize"}
    assert commands["infer"].bash_template == f"{entry} infer"
    assert commands["infer"].parameters[0].type == "int"
    assert commands["summarize"].parameters == []


@pytest.mark.asyncio
async def test_falls_back_when_describe_schema_not_supported(skill_dir):
    """If --describe-schema isn't supported, argparse parsing of -h still runs."""
    # A python argparse script — no --describe-schema handler, so the loader
    # should fall through to argparse parsing.
    script = skill_dir / "argparse_skill.py"
    script.write_text(
        "import argparse\n"
        "p = argparse.ArgumentParser()\n"
        "p.add_argument('--name', required=True)\n"
        "args = p.parse_args()\n"
    )
    entry = f"python3 {script.name}"

    commands = await discover_commands(entry, skill_dir)

    # argparse path produces a "default" command since there are no subparsers
    assert "default" in commands
    names = {p.name for p in commands["default"].parameters}
    assert "name" in names
