"""Skill execution engine"""

import logging
import os
import re
import shlex
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional, TYPE_CHECKING

from dataclasses import dataclass, field

if TYPE_CHECKING:
    from .plugins.base import OutputHandler, OutputFile

logger = logging.getLogger(__name__)

# Allowed runtime prefixes for entry commands
ALLOWED_RUNTIMES = (
    "python",
    "python3",
    "uv run python",
    "uv run",
    "node",
    "bash",
    "sh",
    "./",
)


@dataclass
class ExecutionResult:
    """Result of skill execution"""

    success: bool
    stdout: str
    stderr: str
    return_code: int
    output_files: List[str]
    new_file_paths: List[Path]
    processed_outputs: List["OutputFile"] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        result = {
            "success": self.success,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "return_code": self.return_code,
            "output_files": self.output_files,
        }
        if self.processed_outputs:
            result["processed_outputs"] = [
                {
                    "filename": o.filename,
                    "url": o.url,
                    "metadata": o.metadata,
                }
                for o in self.processed_outputs
            ]
        return result


class SkillExecutor:
    """Executes skills and manages outputs"""

    def __init__(self, output_handler: Optional["OutputHandler"] = None):
        """
        Initialize the executor.

        Args:
            output_handler: Optional OutputHandler plugin for processing output files.
                           See plugins.LocalOutputHandler or plugins.GCSOutputHandler.
        """
        self.output_handler = output_handler

    def _validate_entry_command(self, entry_command: str, skill_directory: Path) -> None:
        """
        Validate that an entry command is safe to execute.

        Security checks:
        1. Entry must start with an allowed runtime
        2. Script file must exist within the skill directory
        3. No absolute paths or path traversal attempts

        Raises:
            ValueError: If the entry command is invalid or unsafe
        """
        # Check for allowed runtime prefix
        if not any(entry_command.startswith(rt) for rt in ALLOWED_RUNTIMES):
            raise ValueError(
                f"Entry command must start with allowed runtime: {ALLOWED_RUNTIMES}. "
                f"Got: {entry_command}"
            )

        # Extract the script path from the entry command
        # Handle patterns like "uv run python script.py" or "python script.py"
        parts = shlex.split(entry_command)
        script_path = None

        for part in parts:
            # First check: reject any absolute paths immediately
            if os.path.isabs(part):
                raise ValueError(
                    f"Absolute paths not allowed: {part}"
                )

            # Look for script file (with extension or relative path)
            if part.endswith(".py") or part.endswith(".sh") or part.endswith(".js"):
                script_path = part
                break
            # Check if it's a relative path starting with ./
            if part.startswith("./"):
                script_path = part
                break

        if script_path:
            # Resolve the script path relative to skill directory
            full_path = (skill_directory / script_path).resolve()

            # Ensure the script is within the skill directory (prevent path traversal)
            try:
                full_path.relative_to(skill_directory.resolve())
            except ValueError:
                raise ValueError(
                    f"Script path escapes skill directory: {script_path}"
                )

            # Check that the script exists
            if not full_path.exists():
                raise ValueError(
                    f"Script not found: {script_path} (looked in {skill_directory})"
                )

    async def execute(
        self,
        skill,
        command_name: str,
        parameters: Dict[str, Any],
    ) -> ExecutionResult:
        """Execute a skill command with parameters

        Args:
            skill: Skill object with commands and directory
            command_name: Name of command to execute
            parameters: Dict of parameter values

        Returns:
            ExecutionResult with output details
        """
        cmd = skill.commands.get(command_name)
        if not cmd:
            raise ValueError(
                f"Command '{command_name}' not found. "
                f"Available: {list(skill.commands.keys())}"
            )

        # Security: Validate the entry command before execution
        self._validate_entry_command(skill.entry_command, skill.directory)

        required_params = [p.name for p in cmd.parameters if p.required]
        missing = [p for p in required_params if p not in parameters]
        if missing:
            raise ValueError(f"Missing required parameters: {missing}")

        bash_command = self._build_command(
            cmd.bash_template, cmd.parameters, parameters
        )

        logger.info("=" * 60)
        logger.info(f"Executing skill: {skill.name}")
        logger.info(f"Working directory: {skill.directory}")
        logger.info(f"Command: {command_name}")
        logger.info(f"Bash command: {bash_command}")
        logger.info(f"Parameters: {parameters}")
        logger.info("=" * 60)

        result = await self._execute_subprocess(bash_command, skill.directory)

        # Process output files if handler is configured and files were created
        if self.output_handler and result.success and result.new_file_paths:
            result.processed_outputs = await self.output_handler.process(
                result.new_file_paths,
                skill.name,
                skill.directory,
            )

        logger.info("=" * 60)
        if result.success:
            logger.info(f"Skill completed successfully!")
            logger.info(
                f"Output files: {', '.join(result.output_files) if result.output_files else 'None'}"
            )
        else:
            logger.error(f"Skill failed with return code {result.return_code}")
            if result.stderr:
                logger.error(f"stderr output:\n{result.stderr}")
            if result.stdout:
                logger.error(f"stdout output:\n{result.stdout}")
        logger.info("=" * 60)

        return result

    def _build_command(self, template: str, parameters_schema, parameters: Dict) -> str:
        """Build bash command from template and parameters.

        Security: All parameter values are escaped using shlex.quote() to prevent
        shell injection attacks.
        """
        bash_command = template
        for param in parameters_schema:
            value = parameters.get(param.name)
            if value is not None:
                param_flag = param.name.replace("_", "-")
                # Security: Escape the value to prevent shell injection
                escaped_value = shlex.quote(str(value))
                bash_command += f" --{param_flag} {escaped_value}"
        return bash_command

    async def _execute_subprocess(self, command: str, cwd: Path) -> ExecutionResult:
        """Execute subprocess and capture output"""
        output_dir = cwd / "output"
        before_files = set(output_dir.glob("*")) if output_dir.exists() else set()
        logger.info(
            f"Before execution - files in output dir: {[f.name for f in before_files]}"
        )

        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd),
        )

        stdout_lines = []
        stderr_lines = []

        async def read_stream(stream, lines_list, prefix):
            while True:
                line = await stream.readline()
                if not line:
                    break
                line_str = line.decode("utf-8").rstrip()
                lines_list.append(line_str)
                logger.info(f"{prefix} {line_str}")

        await asyncio.gather(
            read_stream(process.stdout, stdout_lines, "[stdout]"),
            read_stream(process.stderr, stderr_lines, "[stderr]"),
        )

        await process.wait()

        stdout = "\n".join(stdout_lines)
        stderr = "\n".join(stderr_lines)

        after_files = set(output_dir.glob("*")) if output_dir.exists() else set()
        new_file_paths = sorted(after_files - before_files)
        new_files = [str(f.relative_to(cwd)) for f in new_file_paths]

        logger.info(
            f"After execution - files in output dir: {[f.name for f in after_files]}"
        )
        logger.info(f"New files detected: {[f.name for f in new_file_paths]}")

        success = process.returncode == 0

        if success and not new_file_paths:
            output_file_match = re.search(r"OUTPUT_FILE:(.+)", stdout)
            if output_file_match:
                returned_file = output_file_match.group(1).strip()
                returned_file_path = (
                    Path(returned_file)
                    if os.path.isabs(returned_file)
                    else cwd / returned_file
                )
                if returned_file_path.exists() and returned_file_path.is_file():
                    new_file_paths = [returned_file_path]
                    new_files = [str(returned_file_path.relative_to(cwd))]
                    logger.info(
                        f"Found returned output file in stdout: {returned_file_path}"
                    )

        return ExecutionResult(
            success=success,
            stdout=stdout,
            stderr=stderr,
            return_code=process.returncode,
            output_files=new_files,
            new_file_paths=new_file_paths,
        )
