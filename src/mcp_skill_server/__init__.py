"""MCP Skill Server - Local skill development and testing for MCP"""

from .executor import ExecutionResult, SkillExecutor
from .loader import (
    Skill,
    SkillCommand,
    SkillLoader,
    SkillParameter,
    discover_commands,
    parse_parameters,
    parse_subcommands,
)
from .models import (
    SkillDetailResponse,
    SkillExecutionRequest,
    SkillExecutionResponse,
    SkillInfo,
    SkillListResponse,
)
from .plugins import (
    DefaultResponseFormatter,
    LocalOutputHandler,
    OutputHandler,
    ResponseFormatter,
)
from .server import create_server, create_starlette_app

__version__ = "0.1.0"

__all__ = [
    # Core classes
    "SkillLoader",
    "SkillParameter",
    "SkillCommand",
    "Skill",
    "SkillExecutor",
    "ExecutionResult",
    # Server factories
    "create_server",
    "create_starlette_app",
    # Plugins
    "OutputHandler",
    "LocalOutputHandler",
    "ResponseFormatter",
    "DefaultResponseFormatter",
    # Functions
    "discover_commands",
    "parse_subcommands",
    "parse_parameters",
    # Response models
    "SkillInfo",
    "SkillListResponse",
    "SkillDetailResponse",
    "SkillExecutionRequest",
    "SkillExecutionResponse",
]
