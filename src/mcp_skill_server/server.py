"""MCP Server for skill execution"""

import asyncio
import logging
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from .loader import SkillLoader
from .executor import SkillExecutor

logger = logging.getLogger(__name__)


def create_server(skills_path: str | Path) -> Server:
    """Create an MCP server for the given skills directory."""

    server = Server("mcp-skill-server")
    loader = SkillLoader(skills_path)
    executor = SkillExecutor()

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List all available skills as MCP tools."""
        if not loader.skills:
            loader.discover_skills()

        tools = [
            Tool(
                name="list_skills",
                description="List all available skills",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            Tool(
                name="get_skill",
                description="Get details about a specific skill including its commands and parameters",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "skill_name": {
                            "type": "string",
                            "description": "Name of the skill to get details for",
                        },
                    },
                    "required": ["skill_name"],
                },
            ),
            Tool(
                name="run_skill",
                description="Execute a skill command with parameters",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "skill_name": {
                            "type": "string",
                            "description": "Name of the skill to run",
                        },
                        "command": {
                            "type": "string",
                            "description": "Command to execute (use 'default' for single-command skills)",
                            "default": "default",
                        },
                        "parameters": {
                            "type": "object",
                            "description": "Parameters to pass to the skill command",
                            "additionalProperties": True,
                        },
                    },
                    "required": ["skill_name"],
                },
            ),
            Tool(
                name="refresh_skills",
                description="Refresh the skill list (use after adding new skills)",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
        ]

        return tools

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Handle tool calls."""

        if name == "list_skills":
            if not loader.skills:
                loader.discover_skills()

            skills_info = [
                f"- {skill_id}: {skill.description}"
                for skill_id, skill in loader.skills.items()
            ]

            return [TextContent(
                type="text",
                text=f"Available skills ({len(loader.skills)}):\n" + "\n".join(skills_info)
            )]

        elif name == "get_skill":
            skill_name = arguments.get("skill_name", "").lower().replace("-", "_")
            skill = loader.get_skill(skill_name)

            if not skill:
                return [TextContent(
                    type="text",
                    text=f"Skill '{skill_name}' not found. Available: {loader.list_skills()}"
                )]

            # Ensure commands are discovered
            await skill.refresh_commands()

            tool_def = skill.to_tool_definition()

            # Format commands for display
            commands_text = []
            for cmd_name, cmd_info in tool_def["commands"].items():
                params_text = []
                for p in cmd_info["parameters"]:
                    req = "(required)" if p["required"] else "(optional)"
                    params_text.append(f"    --{p['name']} [{p['type']}] {req}: {p['description']}")

                commands_text.append(
                    f"  {cmd_name}: {cmd_info['description']}\n" + "\n".join(params_text)
                )

            return [TextContent(
                type="text",
                text=f"""Skill: {skill.name}
Description: {skill.description}
Directory: {skill.directory}

Commands:
{chr(10).join(commands_text)}

Documentation:
{skill.content}"""
            )]

        elif name == "run_skill":
            skill_name = arguments.get("skill_name", "").lower().replace("-", "_")
            command = arguments.get("command", "default")
            parameters = arguments.get("parameters", {})

            skill = loader.get_skill(skill_name)
            if not skill:
                return [TextContent(
                    type="text",
                    text=f"Skill '{skill_name}' not found. Available: {loader.list_skills()}"
                )]

            # Ensure commands are discovered
            await skill.refresh_commands()

            try:
                result = await executor.execute(skill, command, parameters)

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
                    output += f"\nOutput files:\n" + "\n".join(f"  - {f}" for f in result.output_files)

                return [TextContent(type="text", text=output)]

            except ValueError as e:
                return [TextContent(type="text", text=f"Error: {str(e)}")]

        elif name == "refresh_skills":
            loader.skills = {}
            loader.discover_skills()
            return [TextContent(
                type="text",
                text=f"Refreshed. Found {len(loader.skills)} skills: {loader.list_skills()}"
            )]

        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    return server


async def main(skills_path: str):
    """Run the MCP server."""
    logging.basicConfig(level=logging.INFO)

    server = create_server(skills_path)

    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


def run_server():
    """Entry point for the MCP server CLI."""
    import argparse

    parser = argparse.ArgumentParser(description="MCP Skill Server")
    parser.add_argument(
        "skills_path",
        type=str,
        help="Path to the skills directory",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    asyncio.run(main(args.skills_path))


if __name__ == "__main__":
    run_server()
