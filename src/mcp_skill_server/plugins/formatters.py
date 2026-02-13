"""Default response formatter for MCP skill server."""

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..executor import ExecutionResult
    from ..loader import Skill

from .base import ResponseFormatter


class DefaultResponseFormatter(ResponseFormatter):
    """Default formatter for MCP tool responses.

    Formats execution results as human-readable text with optional
    processed output details.
    """

    def format_execution_result(
        self,
        result: "ExecutionResult",
        skill: "Skill",
        command: str,
    ) -> str:
        """Format execution result as text."""

        output = f"""Skill: {skill.name}
Command: {command}
Status: {"SUCCESS" if result.success else "FAILED"}
Return code: {result.return_code}

--- stdout ---
{result.stdout}

--- stderr ---
{result.stderr}
"""
        if result.output_files:
            output += f"\nOutput files:\n" + "\n".join(
                f"  - {f}" for f in result.output_files
            )

        if result.processed_outputs:
            output += "\n\nProcessed outputs:\n"
            for po in result.processed_outputs:
                output += f"  - {po.filename}"
                if po.url:
                    output += f" -> {po.url}"
                output += "\n"

        return output
