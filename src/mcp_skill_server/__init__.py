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
from .executor import SkillExecutor, ExecutionResult, ALLOWED_RUNTIMES
from .models import (
    SkillInfo,
    SkillListResponse,
    SkillDetailResponse,
    SkillExecutionRequest,
    SkillExecutionResponse,
)
from .plugins import OutputHandler, LocalOutputHandler

__version__ = "0.1.0"

__all__ = [
    # Core classes
    "SkillLoader",
    "SkillParameter",
    "SkillCommand",
    "Skill",
    "SkillExecutor",
    "ExecutionResult",
    # Security
    "ALLOWED_RUNTIMES",
    # Plugins
    "OutputHandler",
    "LocalOutputHandler",
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
