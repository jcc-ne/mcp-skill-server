"""MCP Skill Server - Local skill development and testing for MCP"""

from .loader import (
    SkillLoader,
    SkillParameter,
    SkillCommand,
    Skill,
    discover_commands,
    parse_subcommands,
    parse_parameters,
)
from .executor import SkillExecutor, ExecutionResult
from .models import (
    SkillInfo,
    SkillListResponse,
    SkillDetailResponse,
    SkillExecutionRequest,
    SkillExecutionResponse,
)
from .plugins import (
    OutputHandler,
    LocalOutputHandler,
    ResponseFormatter,
    DefaultResponseFormatter,
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
