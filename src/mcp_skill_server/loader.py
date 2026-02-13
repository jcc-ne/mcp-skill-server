#! /usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Dynamic skill loader for MCP skill server.
Discovers skills from SKILL.md files and infers schema from argparse --help output.

Skills have minimal frontmatter:
- name: Skill name
- description: What the skill does
- entry: Entry command (e.g., "uv run python script.py")

Commands and parameters are discovered dynamically by running --help.
"""

import logging
import os
import re
import yaml
import asyncio
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


@dataclass
class SkillParameter:
    """Represents a parameter for a skill command"""

    name: str
    required: bool
    type: str  # int, string, float, bool
    description: str


@dataclass
class SkillCommand:
    """Represents a subcommand of a skill"""

    name: str
    description: str
    bash_template: str  # e.g., "python script.py infer"
    parameters: List[SkillParameter] = field(default_factory=list)


@dataclass
class Skill:
    """Represents a dynamically loaded skill with schema discovery"""

    name: str
    description: str
    entry_command: str  # e.g., "uv run python naics_skill.py"
    content: str  # Full markdown content for documentation
    directory: Path
    commands: Dict[str, SkillCommand] = field(default_factory=dict)
    _schema_cache_time: Optional[datetime] = None
    _schema_ttl: timedelta = field(default_factory=lambda: timedelta(hours=1))

    def to_tool_definition(self) -> Dict[str, Any]:
        """Convert skill to MCP tool definition format"""
        return {
            "name": self.name.lower().replace(" ", "_").replace("-", "_"),
            "description": self.description,
            "entry_command": self.entry_command,
            "commands": {
                cmd_name: {
                    "description": cmd.description,
                    "parameters": [
                        {
                            "name": p.name,
                            "required": p.required,
                            "type": p.type,
                            "description": p.description,
                        }
                        for p in cmd.parameters
                    ],
                }
                for cmd_name, cmd in self.commands.items()
            },
            "directory": str(self.directory),
        }

    async def refresh_commands(self, force: bool = False):
        """Refresh command schema from --help output if stale"""
        now = datetime.now()

        if (
            force
            or not self._schema_cache_time
            or now - self._schema_cache_time > self._schema_ttl
        ):
            logger.info(f"Discovering commands for skill: {self.name}")
            self.commands = await discover_commands(self.entry_command, self.directory)
            self._schema_cache_time = now
            logger.info(
                f"Found {len(self.commands)} commands: {list(self.commands.keys())}"
            )


async def run_command(
    command: str, cwd: Path, timeout: int = 30
) -> asyncio.subprocess.Process:
    """Run a shell command and return stdout/stderr"""
    try:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd),
        )

        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)

        return type(
            "Result",
            (),
            {
                "stdout": stdout.decode("utf-8"),
                "stderr": stderr.decode("utf-8"),
                "returncode": process.returncode,
            },
        )()
    except asyncio.TimeoutError:
        logger.warning(f"Command timed out: {command}")
        return type(
            "Result",
            (),
            {"stdout": "", "stderr": "Command timed out", "returncode": -1},
        )()
    except Exception as e:
        logger.error(f"Failed to run command '{command}': {e}")
        return type("Result", (), {"stdout": "", "stderr": str(e), "returncode": -1})()


def parse_subcommands(help_text: str) -> Dict[str, str]:
    """Parse subcommands from argparse help output"""
    subcommands = {}

    # Find the section with subcommand descriptions
    lines = help_text.split("\n")
    in_positional_section = False
    found_choices = False

    for line in lines:
        if "positional arguments:" in line.lower():
            in_positional_section = True
            continue

        if in_positional_section and line and not line.startswith(" "):
            break

        if in_positional_section and not found_choices:
            if re.search(r"\{([^}]+)\}", line):
                found_choices = True
                continue

        if in_positional_section and found_choices:
            match = re.match(r"\s{4,}(\S+)\s{2,}(.+)", line)
            if match:
                cmd_name, cmd_desc = match.groups()
                subcommands[cmd_name] = cmd_desc.strip()

    return subcommands


def infer_type(metavar: Optional[str], description: str) -> str:
    """Infer parameter type from metavar and description"""
    if not metavar:
        return "bool"

    metavar_lower = metavar.lower()
    desc_lower = description.lower()

    if any(
        word in metavar_lower for word in ["year", "count", "num", "id", "port", "size"]
    ):
        return "int"
    if any(
        word in metavar_lower
        for word in ["file", "path", "name", "dir", "url", "string"]
    ):
        return "string"
    if any(word in desc_lower for word in ["integer", "number"]):
        return "int"
    if any(word in desc_lower for word in ["float", "decimal"]):
        return "float"
    if any(word in desc_lower for word in ["true", "false", "enable", "disable"]):
        return "bool"

    return "string"


def parse_parameters(help_text: str) -> List[SkillParameter]:
    """Parse parameters from argparse help output"""
    parameters = []
    lines = help_text.split("\n")

    required_params = set()
    usage_line = lines[0] if lines else ""
    if usage_line.startswith("usage:"):
        usage_without_optional = re.sub(r"\[--[\w-]+(?:\s+[A-Z_]+)?\]", "", usage_line)
        required_matches = re.findall(r"--?([\w-]+)", usage_without_optional)
        required_params = set(
            param.replace("-", "_")
            for param in required_matches
            if param not in ["h", "help"]
        )

    # Track parameters we've already added to avoid duplicates
    param_names_seen = set()

    i = 0
    while i < len(lines):
        line = lines[i]

        # Match parameter lines - description can be on same line or next line
        # Pattern: "  --param-name METAVAR" or "  --param-name METAVAR   description..."
        opt_match = re.match(
            r"\s+(?:-\w,\s+)?--?([\w-]+)(?:\s+([A-Z_]+))?(?:\s|$)", line
        )
        if opt_match:
            param_name = opt_match.group(1).replace("-", "_")
            metavar = opt_match.group(2)

            if param_name == "help" or param_name == "h":
                i += 1
                continue

            # Skip if we've already seen this parameter
            if param_name in param_names_seen:
                i += 1
                continue
            param_names_seen.add(param_name)

            # Check if description is on the same line (after multiple spaces)
            # e.g., "  --item-ids ITEM_IDS Comma-separated..."
            description = ""
            same_line_desc = re.search(r"--[\w-]+(?:\s+[A-Z_]+)?\s{2,}(.+)", line)
            if same_line_desc:
                description = same_line_desc.group(1).strip()
            else:
                # Description on next line(s)
                j = i + 1
                while j < len(lines) and lines[j].startswith(" " * 10):
                    description += lines[j].strip() + " "
                    j += 1
                description = description.strip()

            required = param_name in required_params

            if "(required)" in description.lower():
                required = True
                description = re.sub(
                    r"\(required\)", "", description, flags=re.IGNORECASE
                ).strip()

            param_type = infer_type(metavar, description)

            parameters.append(
                SkillParameter(
                    name=param_name,
                    required=required,
                    type=param_type,
                    description=description,
                )
            )

            i = j
        else:
            i += 1

    return parameters


async def discover_commands(entry: str, cwd: Path) -> Dict[str, SkillCommand]:
    """Discover subcommands and parameters by parsing --help output"""
    # Use longer timeout for help commands (uv run can take time to set up environment)
    result = await run_command(f"{entry} -h", cwd, timeout=30)

    if result.returncode != 0:
        logger.warning(f"Failed to get help for {entry}: {result.stderr}")
        return {}

    main_help = result.stdout
    subcommands = parse_subcommands(main_help)

    if not subcommands:
        logger.info(f"No subcommands found, treating as single-command script")
        params = parse_parameters(main_help)
        return {
            "default": SkillCommand(
                name="default", description="", bash_template=entry, parameters=params
            )
        }

    commands = {}
    tasks = []
    for subcmd_name in subcommands.keys():
        tasks.append(run_command(f"{entry} {subcmd_name} -h", cwd, timeout=30))

    results = await asyncio.gather(*tasks, return_exceptions=True)

    for subcmd_name, result in zip(subcommands.keys(), results):
        if isinstance(result, Exception):
            logger.warning(f"Failed to get help for {subcmd_name}: {result}")
            continue

        if result.returncode != 0:
            logger.warning(f"Failed to get help for {subcmd_name}: {result.stderr}")
            continue

        params = parse_parameters(result.stdout)

        commands[subcmd_name] = SkillCommand(
            name=subcmd_name,
            description=subcommands[subcmd_name],
            bash_template=f"{entry} {subcmd_name}",
            parameters=params,
        )

    return commands


class SkillLoader:
    """Discovers and loads skills from SKILL.md files with dynamic schema discovery"""

    def __init__(self, skills_path: str | Path = None):
        """
        Initialize the skill loader.

        Args:
            skills_path: Path to the skills directory. If None, uses current directory.
        """
        if skills_path is None:
            skills_path = Path.cwd()
        self.base_path = Path(skills_path)
        self.skills: Dict[str, Skill] = {}

    async def discover_skills_async(self) -> Dict[str, Skill]:
        """Scan for */SKILL.md files and parse metadata"""
        if not self.base_path.exists():
            logger.warning(f"Skills path {self.base_path} does not exist")
            return {}

        skill_files = list(self.base_path.glob("*/SKILL.md"))
        logger.info(f"Found {len(skill_files)} SKILL.md files in {self.base_path}")

        tasks = [self._load_skill(skill_file) for skill_file in skill_files]
        skills = await asyncio.gather(*tasks, return_exceptions=True)

        for skill in skills:
            if isinstance(skill, Skill):
                skill_id = skill.name.lower().replace(" ", "_").replace("-", "_")
                self.skills[skill_id] = skill
                logger.info(
                    f"Loaded skill: {skill.name} with {len(skill.commands)} command(s)"
                )
            elif isinstance(skill, Exception):
                logger.error(f"Failed to load skill: {skill}")

        return self.skills

    def discover_skills(self) -> Dict[str, Skill]:
        """Synchronous wrapper for discover_skills_async"""
        try:
            asyncio.get_running_loop()
            import threading

            result = None
            exception = None

            def run_in_thread():
                nonlocal result, exception
                try:
                    result = asyncio.run(self.discover_skills_async())
                except Exception as e:
                    exception = e

            thread = threading.Thread(target=run_in_thread)
            thread.start()
            thread.join()

            if exception:
                raise exception
            return result
        except RuntimeError:
            return asyncio.run(self.discover_skills_async())

    async def _load_skill(self, skill_file: Path) -> Optional[Skill]:
        """Load skill metadata (commands discovered lazily on first use)"""
        try:
            skill = self._parse_skill_file(skill_file)
            if not skill:
                return None

            return skill

        except Exception as e:
            logger.error(f"Failed to load skill {skill_file}: {e}", exc_info=True)
            return None

    def _parse_skill_file(self, skill_file: Path) -> Optional[Skill]:
        """Parse SKILL.md with YAML frontmatter: name, description, entry"""
        content = skill_file.read_text()

        if not content.startswith("---"):
            logger.warning(
                f"Skill file {skill_file} must start with YAML frontmatter (---)"
            )
            return None

        parts = content.split("---", 2)
        if len(parts) < 3:
            logger.warning(f"Invalid frontmatter in {skill_file}")
            return None

        try:
            frontmatter = yaml.safe_load(parts[1])
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse YAML frontmatter in {skill_file}: {e}")
            return None

        if frontmatter is None:
            frontmatter = {}

        markdown_content = parts[2].strip()

        name = frontmatter.get("name")
        if not name:
            logger.warning(f"No 'name' field in {skill_file}")
            return None

        description = frontmatter.get("description")
        if not description:
            logger.warning(f"No 'description' field in {skill_file}")
            return None

        entry_command = frontmatter.get("entry")
        if not entry_command:
            logger.warning(f"No 'entry' field in {skill_file}")
            return None

        return Skill(
            name=name,
            description=description,
            entry_command=entry_command,
            content=markdown_content,
            directory=skill_file.parent,
        )

    def get_skill(self, skill_name: str) -> Optional[Skill]:
        """Get a skill by name"""
        return self.skills.get(skill_name)

    def list_skills(self) -> List[str]:
        """List all available skill names"""
        return list(self.skills.keys())
