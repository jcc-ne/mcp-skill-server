"""Base classes for output handlers and response formatters."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Any, TYPE_CHECKING
from dataclasses import dataclass

if TYPE_CHECKING:
    from ..executor import ExecutionResult
    from ..loader import Skill


@dataclass
class OutputFile:
    """Represents a processed output file."""

    filename: str
    local_path: Path
    url: str | None = None
    metadata: Dict[str, Any] | None = None


class OutputHandler(ABC):
    """
    Base class for handling skill output files.

    Implement this to customize how output files are processed
    (e.g., upload to cloud storage, copy to shared drive, etc.)
    """

    @abstractmethod
    async def process(
        self,
        file_paths: List[Path],
        skill_name: str,
        skill_directory: Path,
    ) -> List[OutputFile]:
        """
        Process output files from a skill execution.

        Args:
            file_paths: List of output file paths
            skill_name: Name of the skill that produced the files
            skill_directory: Working directory of the skill

        Returns:
            List of OutputFile objects with processing results
        """
        pass


class ResponseFormatter(ABC):
    """
    Base class for formatting MCP tool responses.

    Implement this to customize how execution results are formatted
    in MCP tool responses (e.g., add structured JSON, custom formatting, etc.)
    """

    @abstractmethod
    def format_execution_result(
        self,
        result: "ExecutionResult",
        skill: "Skill",
        command: str,
    ) -> str:
        """
        Format an execution result for MCP tool response.

        Args:
            result: The execution result to format
            skill: The skill that was executed
            command: The command that was executed

        Returns:
            Formatted string for TextContent response
        """
        pass
