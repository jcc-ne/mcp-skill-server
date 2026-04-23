"""Tests for MCP server tool handlers."""

import shutil
import tempfile
from pathlib import Path

import pytest
from mcp.types import CallToolRequest, ListToolsRequest

from mcp_skill_server.server import create_server


@pytest.fixture
def skills_dir():
    """Create a temp skills directory with a working hello skill."""
    tmp = tempfile.mkdtemp()
    skill_dir = Path(tmp) / "hello"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(
        "---\n"
        "name: hello\n"
        "description: A greeting skill\n"
        "entry: python hello.py\n"
        "---\n"
        "\n"
        "# Hello Skill\n"
        "\n"
        "Greets the user.\n"
    )
    (skill_dir / "hello.py").write_text(
        "import argparse\n"
        'p = argparse.ArgumentParser(description="Greeting")\n'
        'p.add_argument("--name", default="World", help="Name to greet")\n'
        "a = p.parse_args()\n"
        'print(f"Hello, {a.name}!")\n'
    )
    yield Path(tmp)
    shutil.rmtree(tmp)


def _list_tools_req():
    return ListToolsRequest(method="tools/list")


def _call_tool_req(name, arguments=None):
    return CallToolRequest(
        method="tools/call",
        params={"name": name, "arguments": arguments or {}},
    )


# ---------------------------------------------------------------------------
# list_tools (MCP tool listing)
# ---------------------------------------------------------------------------


class TestListTools:
    @pytest.mark.asyncio
    async def test_returns_four_tools(self, skills_dir):
        server = create_server(skills_dir)
        handler = server.request_handlers[ListToolsRequest]
        result = await handler(_list_tools_req())
        tools = result.root.tools
        names = {t.name for t in tools}
        assert names == {"list_skills", "get_skill", "run_skill", "refresh_skills"}

    @pytest.mark.asyncio
    async def test_tool_prefix_applied_to_all_names(self, skills_dir):
        server = create_server(skills_dir, tool_prefix="coding")
        handler = server.request_handlers[ListToolsRequest]
        result = await handler(_list_tools_req())
        names = {t.name for t in result.root.tools}
        assert names == {
            "coding_list_skills",
            "coding_get_skill",
            "coding_run_skill",
            "coding_refresh_skills",
        }

    @pytest.mark.asyncio
    async def test_no_prefix_keeps_original_names(self, skills_dir):
        server = create_server(skills_dir, tool_prefix=None)
        handler = server.request_handlers[ListToolsRequest]
        result = await handler(_list_tools_req())
        names = {t.name for t in result.root.tools}
        assert "list_skills" in names
        assert not any(n.startswith("_") for n in names)


# ---------------------------------------------------------------------------
# call_tool – list_skills
# ---------------------------------------------------------------------------


class TestListSkills:
    @pytest.mark.asyncio
    async def test_lists_discovered_skills(self, skills_dir):
        server = create_server(skills_dir)
        handler = server.request_handlers[CallToolRequest]
        result = await handler(_call_tool_req("list_skills"))
        text = result.root.content[0].text
        assert "hello" in text
        assert "1" in text  # count

    @pytest.mark.asyncio
    async def test_empty_directory(self):
        tmp = tempfile.mkdtemp()
        try:
            server = create_server(tmp)
            handler = server.request_handlers[CallToolRequest]
            result = await handler(_call_tool_req("list_skills"))
            text = result.root.content[0].text
            assert "0" in text
        finally:
            shutil.rmtree(tmp)


# ---------------------------------------------------------------------------
# call_tool – get_skill
# ---------------------------------------------------------------------------


class TestGetSkill:
    @pytest.mark.asyncio
    async def test_existing_skill(self, skills_dir):
        server = create_server(skills_dir)
        handler = server.request_handlers[CallToolRequest]
        result = await handler(_call_tool_req("get_skill", {"skill_name": "hello"}))
        text = result.root.content[0].text
        assert "hello" in text.lower()
        assert "Greeting" in text or "greeting" in text

    @pytest.mark.asyncio
    async def test_missing_skill(self, skills_dir):
        server = create_server(skills_dir)
        handler = server.request_handlers[CallToolRequest]
        result = await handler(_call_tool_req("get_skill", {"skill_name": "nonexistent"}))
        text = result.root.content[0].text
        assert "not found" in text.lower()


# ---------------------------------------------------------------------------
# call_tool – run_skill
# ---------------------------------------------------------------------------


class TestRunSkill:
    @pytest.mark.asyncio
    async def test_run_default_command(self, skills_dir):
        server = create_server(skills_dir)
        handler = server.request_handlers[CallToolRequest]
        result = await handler(
            _call_tool_req(
                "run_skill",
                {"skill_name": "hello", "command": "default", "parameters": {}},
            )
        )
        text = result.root.content[0].text
        assert "Hello, World!" in text

    @pytest.mark.asyncio
    async def test_run_with_parameter(self, skills_dir):
        server = create_server(skills_dir)
        handler = server.request_handlers[CallToolRequest]
        result = await handler(
            _call_tool_req(
                "run_skill",
                {
                    "skill_name": "hello",
                    "command": "default",
                    "parameters": {"name": "Alice"},
                },
            )
        )
        text = result.root.content[0].text
        assert "Hello, Alice!" in text

    @pytest.mark.asyncio
    async def test_run_missing_skill(self, skills_dir):
        server = create_server(skills_dir)
        handler = server.request_handlers[CallToolRequest]
        result = await handler(_call_tool_req("run_skill", {"skill_name": "nope"}))
        text = result.root.content[0].text
        assert "not found" in text.lower()


# ---------------------------------------------------------------------------
# call_tool – refresh_skills
# ---------------------------------------------------------------------------


class TestRefreshSkills:
    @pytest.mark.asyncio
    async def test_refresh_picks_up_new_skill(self, skills_dir):
        server = create_server(skills_dir)
        handler = server.request_handlers[CallToolRequest]

        # Initial list
        result = await handler(_call_tool_req("list_skills"))
        assert "1" in result.root.content[0].text

        # Add another skill
        new_skill = Path(skills_dir) / "bye"
        new_skill.mkdir()
        (new_skill / "SKILL.md").write_text(
            "---\nname: bye\ndescription: Say bye\nentry: python bye.py\n---\n"
        )
        (new_skill / "bye.py").write_text('print("bye")')

        # Refresh
        result = await handler(_call_tool_req("refresh_skills"))
        text = result.root.content[0].text
        assert "2" in text

    @pytest.mark.asyncio
    async def test_refresh_returns_skill_names(self, skills_dir):
        server = create_server(skills_dir)
        handler = server.request_handlers[CallToolRequest]
        result = await handler(_call_tool_req("refresh_skills"))
        text = result.root.content[0].text
        assert "hello" in text


# ---------------------------------------------------------------------------
# Tool prefix – dispatch works with prefixed names
# ---------------------------------------------------------------------------


class TestToolPrefix:
    @pytest.mark.asyncio
    async def test_prefixed_list_skills(self, skills_dir):
        server = create_server(skills_dir, tool_prefix="myenv")
        handler = server.request_handlers[CallToolRequest]
        result = await handler(_call_tool_req("myenv_list_skills"))
        text = result.root.content[0].text
        assert "hello" in text

    @pytest.mark.asyncio
    async def test_prefixed_run_skill(self, skills_dir):
        server = create_server(skills_dir, tool_prefix="myenv")
        handler = server.request_handlers[CallToolRequest]
        result = await handler(
            _call_tool_req(
                "myenv_run_skill",
                {"skill_name": "hello", "command": "default", "parameters": {}},
            )
        )
        text = result.root.content[0].text
        assert "Hello, World!" in text

    @pytest.mark.asyncio
    async def test_unprefixed_name_unknown_when_prefix_set(self, skills_dir):
        server = create_server(skills_dir, tool_prefix="myenv")
        handler = server.request_handlers[CallToolRequest]
        result = await handler(_call_tool_req("list_skills"))
        text = result.root.content[0].text
        assert "Unknown tool" in text

    @pytest.mark.asyncio
    async def test_prefixed_refresh_skills(self, skills_dir):
        server = create_server(skills_dir, tool_prefix="myenv")
        handler = server.request_handlers[CallToolRequest]
        result = await handler(_call_tool_req("myenv_refresh_skills"))
        text = result.root.content[0].text
        assert "hello" in text


# ---------------------------------------------------------------------------
# call_tool – unknown tool
# ---------------------------------------------------------------------------


class TestUnknownTool:
    @pytest.mark.asyncio
    async def test_unknown_tool(self, skills_dir):
        server = create_server(skills_dir)
        handler = server.request_handlers[CallToolRequest]
        result = await handler(_call_tool_req("does_not_exist"))
        text = result.root.content[0].text
        assert "Unknown tool" in text
