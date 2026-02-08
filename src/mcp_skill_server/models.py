"""Pydantic models for MCP skill server"""

from typing import List, Dict, Any
from pydantic import BaseModel, Field


class SkillInfo(BaseModel):
    """Summary info for a skill"""
    name: str
    description: str


class SkillListResponse(BaseModel):
    """Response model for listing skills"""

    skills: List[SkillInfo] = Field(..., description="List of available skills")
    count: int = Field(..., description="Number of skills found")


class SkillDetailResponse(BaseModel):
    """Response model for skill details"""

    name: str
    description: str
    entry_command: str
    content: str
    directory: str
    commands: Dict[str, Dict[str, Any]] = Field(
        default_factory=dict, description="Available commands with their parameters"
    )


class SkillExecutionRequest(BaseModel):
    """Request model for executing a skill"""

    skill_name: str = Field(..., description="Name of the skill to execute")
    command: str = Field(default="default", description="Command to run")
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="Skill parameters as key-value pairs"
    )


class SkillExecutionResponse(BaseModel):
    """Response model for skill execution"""

    success: bool
    skill_name: str
    command: str
    stdout: str
    stderr: str
    return_code: int
    output_files: List[str] = Field(default_factory=list)
    message: str
