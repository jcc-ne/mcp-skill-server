"""Local file output handler - just returns local file paths."""

from pathlib import Path
from typing import List

from .base import OutputHandler, OutputFile


class LocalOutputHandler(OutputHandler):
    """
    Simple handler that returns local file paths.

    Use this for local development or when you don't need
    to upload files anywhere.
    """

    async def process(
        self,
        file_paths: List[Path],
        skill_name: str,
        skill_directory: Path,
    ) -> List[OutputFile]:
        """Return output files with local file:// URLs."""
        results = []

        for file_path in file_paths:
            results.append(
                OutputFile(
                    filename=file_path.name,
                    local_path=file_path,
                    url=f"file://{file_path.absolute()}",
                )
            )

        return results
