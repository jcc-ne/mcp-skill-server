"""Tests for skill loader: parsing, schema discovery, and skill management."""

import shutil
import tempfile
from pathlib import Path

import pytest

from mcp_skill_server.loader import (
    Skill,
    SkillCommand,
    SkillLoader,
    SkillParameter,
    discover_commands,
    infer_type,
    parse_parameters,
    parse_subcommands,
)

# ---------------------------------------------------------------------------
# infer_type
# ---------------------------------------------------------------------------


class TestInferType:
    def test_year_metavar(self):
        assert infer_type("YEAR", "") == "int"

    def test_count_metavar(self):
        assert infer_type("COUNT", "") == "int"

    def test_num_metavar(self):
        assert infer_type("NUM", "") == "int"

    def test_file_metavar(self):
        assert infer_type("FILE", "") == "string"

    def test_path_metavar(self):
        assert infer_type("PATH", "") == "string"

    def test_no_metavar_is_bool(self):
        assert infer_type(None, "") == "bool"

    def test_integer_in_description(self):
        assert infer_type("VALUE", "an integer value") == "int"

    def test_float_in_description(self):
        assert infer_type("VALUE", "a float threshold") == "float"

    def test_bool_in_description(self):
        assert infer_type("VALUE", "enable feature") == "bool"

    def test_unknown_defaults_to_string(self):
        assert infer_type("FOO", "some description") == "string"


# ---------------------------------------------------------------------------
# parse_parameters
# ---------------------------------------------------------------------------


class TestParseParameters:
    def test_single_optional(self):
        help_text = (
            "usage: script.py [-h] [--name NAME]\n"
            "\n"
            "A test script\n"
            "\n"
            "options:\n"
            "  -h, --help   show this help message and exit\n"
            "  --name NAME  Name to greet\n"
        )
        params = parse_parameters(help_text)
        assert len(params) == 1
        assert params[0].name == "name"
        assert params[0].required is False
        assert params[0].type == "string"

    def test_required_parameter(self):
        help_text = (
            "usage: script.py [-h] --year YEAR\n"
            "\n"
            "options:\n"
            "  -h, --help   show this help message and exit\n"
            "  --year YEAR  Year to analyze\n"
        )
        params = parse_parameters(help_text)
        assert len(params) == 1
        assert params[0].name == "year"
        assert params[0].required is True
        assert params[0].type == "int"

    def test_multiple_parameters(self):
        help_text = (
            "usage: script.py [-h] --year YEAR [--file FILE] [--count COUNT]\n"
            "\n"
            "options:\n"
            "  -h, --help     show this help message and exit\n"
            "  --year YEAR    Year to analyze\n"
            "  --file FILE    Input file path\n"
            "  --count COUNT  Number of items\n"
        )
        params = parse_parameters(help_text)
        assert len(params) == 3
        names = {p.name for p in params}
        assert names == {"year", "file", "count"}

        year = next(p for p in params if p.name == "year")
        assert year.required is True
        file_ = next(p for p in params if p.name == "file")
        assert file_.required is False

    def test_flag_no_metavar(self):
        help_text = (
            "usage: script.py [-h] [--verbose]\n"
            "\n"
            "options:\n"
            "  -h, --help  show this help message and exit\n"
            "  --verbose   Enable verbose output\n"
        )
        params = parse_parameters(help_text)
        assert len(params) == 1
        assert params[0].name == "verbose"
        assert params[0].type == "bool"

    def test_hyphenated_name_converted(self):
        help_text = (
            "usage: script.py [-h] [--input-file INPUT_FILE]\n"
            "\n"
            "options:\n"
            "  -h, --help                 show this help message and exit\n"
            "  --input-file INPUT_FILE    Input file to process\n"
        )
        params = parse_parameters(help_text)
        assert len(params) == 1
        assert params[0].name == "input_file"

    def test_short_and_long_flag(self):
        help_text = (
            "usage: script.py [-h] [-n NAME]\n"
            "\n"
            "options:\n"
            "  -h, --help            show this help message and exit\n"
            "  -n, --name NAME       Name to greet\n"
        )
        params = parse_parameters(help_text)
        assert len(params) == 1
        assert params[0].name == "name"

    def test_empty_help(self):
        assert parse_parameters("") == []

    def test_help_only(self):
        help_text = (
            "usage: script.py [-h]\n\noptions:\n  -h, --help  show this help message and exit\n"
        )
        assert parse_parameters(help_text) == []

    def test_required_in_description(self):
        help_text = (
            "usage: script.py [-h] [--name NAME]\n"
            "\n"
            "options:\n"
            "  -h, --help   show this help message and exit\n"
            "  --name NAME  Name to greet (required)\n"
        )
        params = parse_parameters(help_text)
        assert len(params) == 1
        assert params[0].required is True


# ---------------------------------------------------------------------------
# parse_subcommands
# ---------------------------------------------------------------------------


class TestParseSubcommands:
    def test_with_subcommands(self):
        help_text = (
            "usage: script.py [-h] {analyze,list} ...\n"
            "\n"
            "A test script\n"
            "\n"
            "positional arguments:\n"
            "  {analyze,list}\n"
            "    analyze        Run analysis\n"
            "    list           List outputs\n"
            "\n"
            "options:\n"
            "  -h, --help     show this help message and exit\n"
        )
        subcmds = parse_subcommands(help_text)
        assert subcmds == {"analyze": "Run analysis", "list": "List outputs"}

    def test_no_subcommands(self):
        help_text = (
            "usage: script.py [-h] [--name NAME]\n"
            "\n"
            "options:\n"
            "  -h, --help   show this help message and exit\n"
            "  --name NAME  Name to greet\n"
        )
        assert parse_subcommands(help_text) == {}

    def test_empty_help(self):
        assert parse_subcommands("") == {}


# ---------------------------------------------------------------------------
# Skill.to_tool_definition
# ---------------------------------------------------------------------------


class TestSkillToToolDefinition:
    def test_basic_conversion(self):
        skill = Skill(
            name="my-skill",
            description="Test skill",
            entry_command="python script.py",
            content="docs",
            directory=Path("/tmp/test"),
            commands={
                "default": SkillCommand(
                    name="default",
                    description="Run it",
                    bash_template="python script.py",
                    parameters=[
                        SkillParameter(
                            name="name",
                            required=False,
                            type="string",
                            description="Name",
                        ),
                        SkillParameter(
                            name="year",
                            required=True,
                            type="int",
                            description="Year",
                        ),
                    ],
                )
            },
        )

        td = skill.to_tool_definition()
        assert td["name"] == "my_skill"
        assert td["description"] == "Test skill"
        assert "default" in td["commands"]
        params = td["commands"]["default"]["parameters"]
        assert len(params) == 2
        assert params[0]["name"] == "name"
        assert params[1]["required"] is True

    def test_name_normalisation(self):
        skill = Skill(
            name="My Cool Skill",
            description="d",
            entry_command="python s.py",
            content="",
            directory=Path("/tmp"),
        )
        assert skill.to_tool_definition()["name"] == "my_cool_skill"


# ---------------------------------------------------------------------------
# SkillLoader._parse_skill_file
# ---------------------------------------------------------------------------


class TestParseSkillFile:
    @pytest.fixture
    def base_dir(self):
        tmp = tempfile.mkdtemp()
        yield Path(tmp)
        shutil.rmtree(tmp)

    def _make_skill(self, base_dir, name, content):
        d = base_dir / name
        d.mkdir()
        md = d / "SKILL.md"
        md.write_text(content)
        return md

    def test_valid_skill(self, base_dir):
        md = self._make_skill(
            base_dir,
            "good",
            "---\nname: good\ndescription: A skill\nentry: python s.py\n---\n\n# Docs\n",
        )
        loader = SkillLoader(base_dir)
        skill = loader._parse_skill_file(md)
        assert skill is not None
        assert skill.name == "good"
        assert skill.description == "A skill"
        assert skill.entry_command == "python s.py"
        assert "Docs" in skill.content
        assert skill.directory == md.parent

    def test_missing_name(self, base_dir):
        md = self._make_skill(
            base_dir,
            "no_name",
            "---\ndescription: d\nentry: python s.py\n---\ncontent",
        )
        assert SkillLoader(base_dir)._parse_skill_file(md) is None

    def test_missing_description(self, base_dir):
        md = self._make_skill(
            base_dir,
            "no_desc",
            "---\nname: x\nentry: python s.py\n---\ncontent",
        )
        assert SkillLoader(base_dir)._parse_skill_file(md) is None

    def test_missing_entry(self, base_dir):
        md = self._make_skill(
            base_dir,
            "no_entry",
            "---\nname: x\ndescription: d\n---\ncontent",
        )
        assert SkillLoader(base_dir)._parse_skill_file(md) is None

    def test_no_frontmatter(self, base_dir):
        md = self._make_skill(base_dir, "plain", "Just plain text")
        assert SkillLoader(base_dir)._parse_skill_file(md) is None

    def test_invalid_yaml(self, base_dir):
        md = self._make_skill(
            base_dir,
            "bad_yaml",
            "---\nname: [broken\n---\ncontent",
        )
        assert SkillLoader(base_dir)._parse_skill_file(md) is None

    def test_empty_frontmatter(self, base_dir):
        md = self._make_skill(base_dir, "empty_fm", "---\n---\ncontent")
        assert SkillLoader(base_dir)._parse_skill_file(md) is None


# ---------------------------------------------------------------------------
# discover_commands (integration – runs real subprocess)
# ---------------------------------------------------------------------------


class TestDiscoverCommands:
    @pytest.fixture
    def script_dir(self):
        tmp = tempfile.mkdtemp()
        yield Path(tmp)
        shutil.rmtree(tmp)

    @pytest.mark.asyncio
    async def test_single_command(self, script_dir):
        (script_dir / "script.py").write_text(
            "import argparse\n"
            "p = argparse.ArgumentParser()\n"
            'p.add_argument("--name", default="World", help="Name to greet")\n'
            "p.parse_args()\n"
        )
        commands = await discover_commands("python script.py", script_dir)
        assert "default" in commands
        names = [p.name for p in commands["default"].parameters]
        assert "name" in names

    @pytest.mark.asyncio
    async def test_multi_command(self, script_dir):
        (script_dir / "script.py").write_text(
            "import argparse\n"
            "p = argparse.ArgumentParser()\n"
            'sp = p.add_subparsers(dest="command")\n'
            'r = sp.add_parser("run", help="Run it")\n'
            'r.add_argument("--input", required=True, help="Input file")\n'
            'sp.add_parser("list", help="List items")\n'
            "p.parse_args()\n"
        )
        commands = await discover_commands("python script.py", script_dir)
        assert "run" in commands
        assert "list" in commands
        run_params = [p.name for p in commands["run"].parameters]
        assert "input" in run_params

    @pytest.mark.asyncio
    async def test_bad_script(self, script_dir):
        (script_dir / "bad.py").write_text("raise RuntimeError('boom')\n")
        commands = await discover_commands("python bad.py", script_dir)
        assert commands == {}


# ---------------------------------------------------------------------------
# SkillLoader
# ---------------------------------------------------------------------------


class TestSkillLoader:
    @pytest.fixture
    def skills_dir(self):
        tmp = tempfile.mkdtemp()
        yield Path(tmp)
        shutil.rmtree(tmp)

    def _add_skill(self, skills_dir, name, desc="desc", entry="python s.py"):
        d = skills_dir / name
        d.mkdir(exist_ok=True)
        (d / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: {desc}\nentry: {entry}\n---\n# {name}\n"
        )
        (d / "s.py").write_text('print("ok")')

    def test_discover_finds_skills(self, skills_dir):
        self._add_skill(skills_dir, "alpha")
        self._add_skill(skills_dir, "beta")
        loader = SkillLoader(skills_dir)
        loader.discover_skills()
        assert len(loader.skills) == 2
        assert "alpha" in loader.skills
        assert "beta" in loader.skills

    def test_discover_skips_invalid(self, skills_dir):
        self._add_skill(skills_dir, "good")
        bad = skills_dir / "bad"
        bad.mkdir()
        (bad / "SKILL.md").write_text("no frontmatter")
        loader = SkillLoader(skills_dir)
        loader.discover_skills()
        assert len(loader.skills) == 1

    def test_discover_nonexistent_path(self):
        loader = SkillLoader("/nonexistent/path")
        skills = loader.discover_skills()
        assert skills == {}

    def test_list_skills(self, skills_dir):
        self._add_skill(skills_dir, "one")
        loader = SkillLoader(skills_dir)
        loader.discover_skills()
        assert "one" in loader.list_skills()

    def test_get_skill(self, skills_dir):
        self._add_skill(skills_dir, "target")
        loader = SkillLoader(skills_dir)
        loader.discover_skills()
        assert loader.get_skill("target") is not None
        assert loader.get_skill("missing") is None

    def test_name_normalisation(self, skills_dir):
        d = skills_dir / "my-skill"
        d.mkdir()
        (d / "SKILL.md").write_text(
            "---\nname: my-skill\ndescription: d\nentry: python s.py\n---\n"
        )
        (d / "s.py").write_text('print("ok")')
        loader = SkillLoader(skills_dir)
        loader.discover_skills()
        assert "my_skill" in loader.skills
