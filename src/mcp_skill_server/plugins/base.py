"""Base class for output handlers."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import dataclass


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
