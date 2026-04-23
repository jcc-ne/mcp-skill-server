"""MCP Server for skill execution"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .executor import SkillExecutor
from .loader import SkillLoader
from .plugins.base import OutputHandler, ResponseFormatter
from .plugins.formatters import DefaultResponseFormatter
from .plugins.local import LocalOutputHandler

logger = logging.getLogger(__name__)


def create_server(
    skills_path: str | Path,
    output_handler: Optional[OutputHandler] = None,
    response_formatter: Optional[ResponseFormatter] = None,
    tool_prefix: Optional[str] = None,
) -> Server:
    """Create an MCP server for the given skills directory.

    Args:
        skills_path: Path to the directory containing skills
        output_handler: Optional output handler plugin.
            Defaults to LocalOutputHandler.
        response_formatter: Optional response formatter plugin.
            Defaults to DefaultResponseFormatter.
        tool_prefix: Optional prefix for tool names (e.g. "coding" yields
            "coding_list_skills").  Use this to avoid conflicts when a client
            connects to multiple skill servers simultaneously.
    """
    if output_handler is None:
        output_handler = LocalOutputHandler()

    if response_formatter is None:
        response_formatter = DefaultResponseFormatter()

    server = Server("mcp-skill-server")
    loader = SkillLoader(skills_path)
    executor = SkillExecutor(output_handler=output_handler)

    def _tool_name(base: str) -> str:
        return f"{tool_prefix}_{base}" if tool_prefix else base

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List all available skills as MCP tools."""
        if not loader.skills:
            loader.discover_skills()

        tools = [
            Tool(
                name=_tool_name("list_skills"),
                description="List all available skills",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            Tool(
                name=_tool_name("get_skill"),
                description="Get skill details including commands and parameters",  # noqa
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
                name=_tool_name("run_skill"),
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
                            "description": (
                                "Command to execute (use 'default' for single-command skills)"
                            ),
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
                name=_tool_name("refresh_skills"),
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

        if name == _tool_name("list_skills"):
            if not loader.skills:
                loader.discover_skills()

            skills_info = [
                f"- {skill_id}: {skill.description}" for skill_id, skill in loader.skills.items()
            ]

            return [
                TextContent(
                    type="text",
                    text=f"Available skills ({len(loader.skills)}):\n" + "\n".join(skills_info),
                )
            ]

        elif name == _tool_name("get_skill"):
            skill_name = arguments.get("skill_name", "").lower().replace("-", "_")
            skill = loader.get_skill(skill_name)

            if not skill:
                return [
                    TextContent(
                        type="text",
                        text=f"Skill '{skill_name}' not found. Available: {loader.list_skills()}",
                    )
                ]

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

            return [
                TextContent(
                    type="text",
                    text=f"""Skill: {skill.name}
Description: {skill.description}
Directory: {skill.directory}

Commands:
{chr(10).join(commands_text)}

Documentation:
{skill.content}""",
                )
            ]

        elif name == _tool_name("run_skill"):
            skill_name = arguments.get("skill_name", "").lower().replace("-", "_")
            command = arguments.get("command", "")
            parameters = arguments.get("parameters", {})

            skill = loader.get_skill(skill_name)
            if not skill:
                return [
                    TextContent(
                        type="text",
                        text=f"Skill '{skill_name}' not found. Available: {loader.list_skills()}",
                    )
                ]

            # Ensure commands are discovered
            await skill.refresh_commands()

            try:
                result = await executor.execute(skill, command, parameters)

                # Use response formatter plugin
                output = response_formatter.format_execution_result(result, skill, command)

                return [TextContent(type="text", text=output)]

            except ValueError as e:
                return [TextContent(type="text", text=f"Error: {str(e)}")]

        elif name == _tool_name("refresh_skills"):
            loader.skills = {}
            loader.discover_skills()
            return [
                TextContent(
                    type="text",
                    text=f"Refreshed. Found {len(loader.skills)} skills: {loader.list_skills()}",
                )
            ]

        return [TextContent(type="text", text=f"Unknown tool: {name}")]

    return server


def create_starlette_app(
    skills_path: str | Path,
    output_handler: Optional[OutputHandler] = None,
    response_formatter: Optional[ResponseFormatter] = None,
    *,
    stateless: bool = False,
    json_response: bool = False,
):
    """Create a Starlette ASGI app serving this MCP server over streamable HTTP.

    The returned app is ready to be mounted onto an existing FastAPI or
    Starlette application::

        from fastapi import FastAPI
        from mcp_skill_server.server import create_starlette_app

        app = FastAPI()
        app.mount("/other-mcp", other_mcp_app)          # your existing MCP app
        app.mount("/skills", create_starlette_app("./my-skills"))  # this one

    Args:
        skills_path: Path to the directory containing skills.
        output_handler: Optional output handler plugin.
            Defaults to LocalOutputHandler.
        response_formatter: Optional response formatter plugin.
            Defaults to DefaultResponseFormatter.
        stateless: When True, each HTTP request gets a fresh session
            (no persistent state across calls).  Useful for horizontal
            scaling behind a load-balancer.
        json_response: When True, return plain JSON instead of SSE streams.
    """
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
    from starlette.applications import Starlette
    from starlette.routing import Route

    server = create_server(skills_path, output_handler, response_formatter)

    session_manager = StreamableHTTPSessionManager(
        app=server,
        json_response=json_response,
        stateless=stateless,
    )

    @asynccontextmanager
    async def lifespan(app):
        async with session_manager.run():
            yield

    # Thin ASGI wrapper so Starlette's Route treats it as a raw ASGI app
    # rather than a request/response endpoint.
    class _JsonRpcHandler:
        async def __call__(self, scope, receive, send):
            await session_manager.handle_request(scope, receive, send)

    return Starlette(
        routes=[
            Route("/", endpoint=_JsonRpcHandler(), methods=["GET", "POST", "DELETE"]),
        ],
        lifespan=lifespan,
    )


async def main(skills_path: str, tool_prefix: Optional[str] = None):
    """Run the MCP server."""
    logging.basicConfig(level=logging.INFO)

    server = create_server(skills_path, tool_prefix=tool_prefix)

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
        "-v",
        "--verbose",
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
