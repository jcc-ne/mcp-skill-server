"""CLI commands for mcp-skill-server"""

import argparse
import asyncio
import logging
import sys
from pathlib import Path

from .server import main as run_server_main


def init_skill(args: argparse.Namespace) -> int:
    """Initialize a new skill from a Claude skill or create a new one."""
    skill_path = Path(args.path)
    skill_name = args.name or skill_path.name

    # Check if directory already exists
    if skill_path.exists():
        if not args.force:
            print(f"Error: Directory already exists: {skill_path}")
            print("Use --force to overwrite")
            return 1
        print(f"Warning: Overwriting existing directory: {skill_path}")

    # Create the skill directory
    skill_path.mkdir(parents=True, exist_ok=True)

    # Check for existing Claude skill (SKILL.md without entry)
    existing_skill_md = skill_path / "SKILL.md"
    existing_content = ""
    existing_frontmatter = {}

    if existing_skill_md.exists() and not args.force:
        import yaml

        content = existing_skill_md.read_text()
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                try:
                    existing_frontmatter = yaml.safe_load(parts[1]) or {}
                    existing_content = parts[2].strip()

                    # Check if this is already an MCP skill (has entry)
                    if existing_frontmatter.get("entry"):
                        print(f"Skill already has entry point: {existing_frontmatter['entry']}")
                        print("Use --force to reinitialize")
                        return 1

                    # Use existing values as defaults
                    if not args.name and existing_frontmatter.get("name"):
                        skill_name = existing_frontmatter["name"]
                    if not args.description and existing_frontmatter.get("description"):
                        args.description = existing_frontmatter["description"]

                    print(f"Found existing Claude skill: {skill_name}")
                    print("Adding entry point to convert to MCP skill...")
                except yaml.YAMLError:
                    pass

    # Determine script name and entry
    script_name = f"{skill_name.replace('-', '_').replace(' ', '_')}.py"
    entry = f"uv run python {script_name}"

    # Generate SKILL.md
    description = args.description or f"Description for {skill_name}"

    skill_md_content = f"""---
name: {skill_name}
description: {description}
entry: {entry}
---

{
        existing_content
        or f'''# {skill_name.replace("_", " ").title()}

## Overview

Describe what this skill does.

## Usage Examples

- "Run {skill_name}"
- "Execute {skill_name} with --param value"

## Parameters

Document the available parameters here.
'''
    }"""

    # Generate Python script with argparse template
    script_content = f'''#!/usr/bin/env python3
"""
{skill_name} - {description}

This script is the entry point for the {skill_name} skill.
"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        description="{description}"
    )

    # Add your parameters here
    parser.add_argument(
        "--example",
        type=str,
        default="world",
        help="An example parameter",
    )

    # For skills with subcommands, uncomment:
    # subparsers = parser.add_subparsers(dest="command", help="Available commands")
    #
    # run_parser = subparsers.add_parser("run", help="Run the main operation")
    # run_parser.add_argument("--input", type=str, required=True, help="Input file")
    #
    # list_parser = subparsers.add_parser("list", help="List outputs")

    args = parser.parse_args()

    # Your skill logic here
    print(f"Hello, {{args.example}}!")

    # To indicate an output file, print:
    # print(f"OUTPUT_FILE:output/result.csv")


if __name__ == "__main__":
    main()
'''

    # Write files
    (skill_path / "SKILL.md").write_text(skill_md_content)

    script_path = skill_path / script_name
    if not script_path.exists() or args.force:
        script_path.write_text(script_content)
        script_path.chmod(0o755)
        print(f"Created: {script_path}")
    else:
        print(f"Skipped (exists): {script_path}")

    # Create output directory
    output_dir = skill_path / "output"
    output_dir.mkdir(exist_ok=True)
    (output_dir / ".gitkeep").touch()

    print(f"Created: {skill_path / 'SKILL.md'}")
    print(f"Created: {output_dir}")
    print()
    print(f"Skill initialized: {skill_name}")
    print()
    print("Next steps:")
    print(f"  1. Edit {script_path} to implement your skill logic")
    print(f"  2. Test with: uv run python {script_name} --help")
    print(f"  3. Run MCP server: uv run mcp-skill-server {skill_path.parent}")
    print()

    return 0


def validate_skill(args: argparse.Namespace) -> int:
    """Validate a skill is ready for MCP deployment."""
    import yaml

    from .executor import ALLOWED_RUNTIMES

    skill_path = Path(args.path)
    skill_md = skill_path / "SKILL.md"

    errors = []
    warnings = []

    # Check SKILL.md exists
    if not skill_md.exists():
        errors.append(f"SKILL.md not found in {skill_path}")
        print_validation_result(args.path, errors, warnings)
        return 1

    # Parse SKILL.md
    content = skill_md.read_text()
    if not content.startswith("---"):
        errors.append("SKILL.md must start with YAML frontmatter (---)")
        print_validation_result(args.path, errors, warnings)
        return 1

    parts = content.split("---", 2)
    if len(parts) < 3:
        errors.append("Invalid YAML frontmatter format")
        print_validation_result(args.path, errors, warnings)
        return 1

    try:
        frontmatter = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError as e:
        errors.append(f"Invalid YAML: {e}")
        print_validation_result(args.path, errors, warnings)
        return 1

    # Check required fields
    if not frontmatter.get("name"):
        errors.append("Missing required field: name")

    if not frontmatter.get("description"):
        errors.append("Missing required field: description")

    entry = frontmatter.get("entry")
    if not entry:
        errors.append("Missing required field: entry (required for MCP deployment)")
    else:
        # Validate entry command
        if not any(entry.startswith(rt) for rt in ALLOWED_RUNTIMES):
            errors.append(f"Entry must start with allowed runtime: {ALLOWED_RUNTIMES}")

        # Check script exists
        import shlex

        parts_list = shlex.split(entry)
        script_path = None
        for part in parts_list:
            if part.endswith((".py", ".sh", ".js")) or part.startswith("./"):
                script_path = part
                break

        if script_path:
            full_path = skill_path / script_path
            if not full_path.exists():
                errors.append(f"Script not found: {script_path}")
        else:
            warnings.append("Could not identify script file in entry command")

    # Check output directory
    if not (skill_path / "output").exists():
        warnings.append("No output/ directory (will be created on first run)")

    # Try to discover commands
    if entry and not errors:
        print(f"Discovering commands from: {entry}")
        from .loader import discover_commands

        try:
            commands = asyncio.run(discover_commands(entry, skill_path))
            if commands:
                print(f"Found {len(commands)} command(s): {list(commands.keys())}")
                for cmd_name, cmd in commands.items():
                    param_count = len(cmd.parameters)
                    required = sum(1 for p in cmd.parameters if p.required)
                    print(f"  - {cmd_name}: {param_count} params ({required} required)")
            else:
                warnings.append("No commands discovered (--help may have failed)")
        except Exception as e:
            warnings.append(f"Command discovery failed: {e}")

    print_validation_result(args.path, errors, warnings)
    return 1 if errors else 0


def print_validation_result(path: str, errors: list, warnings: list):
    """Print validation results."""
    print()
    if errors:
        print(f"FAILED: {path}")
        for err in errors:
            print(f"  ERROR: {err}")
    else:
        print(f"PASSED: {path}")

    for warn in warnings:
        print(f"  WARNING: {warn}")

    print()
    if not errors:
        print("Skill is ready for MCP deployment.")


def run_server(args: argparse.Namespace) -> int:
    """Run the MCP skill server."""
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    asyncio.run(run_server_main(args.skills_path))
    return 0


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="mcp-skill-server",
        description="MCP server for local skill development and testing",
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # serve command (default behavior)
    serve_parser = subparsers.add_parser(
        "serve",
        help="Run the MCP skill server",
    )
    serve_parser.add_argument(
        "skills_path",
        type=str,
        help="Path to the skills directory",
    )
    serve_parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    # init command
    init_parser = subparsers.add_parser(
        "init",
        help="Initialize a new skill or convert a Claude skill to MCP skill",
    )
    init_parser.add_argument(
        "path",
        type=str,
        help="Path to the skill directory to create/convert",
    )
    init_parser.add_argument(
        "-n",
        "--name",
        type=str,
        help="Skill name (defaults to directory name)",
    )
    init_parser.add_argument(
        "-d",
        "--description",
        type=str,
        help="Skill description",
    )
    init_parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Overwrite existing files",
    )

    # validate command
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate a skill is ready for MCP deployment",
    )
    validate_parser.add_argument(
        "path",
        type=str,
        help="Path to the skill directory to validate",
    )

    args = parser.parse_args()

    # Handle legacy usage: mcp-skill-server /path/to/skills
    if args.command is None:
        # Check if there's a positional argument that looks like a path
        if len(sys.argv) > 1 and not sys.argv[1].startswith("-"):
            # Legacy mode: treat first arg as skills_path
            args.command = "serve"
            args.skills_path = sys.argv[1]
            args.verbose = "-v" in sys.argv or "--verbose" in sys.argv
        else:
            parser.print_help()
            return 1

    if args.command == "serve":
        return run_server(args)
    elif args.command == "init":
        return init_skill(args)
    elif args.command == "validate":
        return validate_skill(args)
    else:
        parser.print_help()
        return 1


def main_init():
    """Entry point for mcp-skill-init command."""
    parser = argparse.ArgumentParser(
        prog="mcp-skill-init",
        description="Initialize a new skill or convert a Claude skill to MCP skill",
    )
    parser.add_argument(
        "path",
        type=str,
        help="Path to the skill directory to create/convert",
    )
    parser.add_argument(
        "-n",
        "--name",
        type=str,
        help="Skill name (defaults to directory name)",
    )
    parser.add_argument(
        "-d",
        "--description",
        type=str,
        help="Skill description",
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Overwrite existing files",
    )

    args = parser.parse_args()
    return init_skill(args)


def main_validate():
    """Entry point for mcp-skill-validate command."""
    parser = argparse.ArgumentParser(
        prog="mcp-skill-validate",
        description="Validate a skill is ready for MCP deployment",
    )
    parser.add_argument(
        "path",
        type=str,
        help="Path to the skill directory to validate",
    )

    args = parser.parse_args()
    return validate_skill(args)


if __name__ == "__main__":
    sys.exit(main())
