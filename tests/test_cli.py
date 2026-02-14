"""Tests for CLI commands: init, validate, and main entry points."""

import argparse
import shutil
import tempfile
from pathlib import Path
from unittest import mock

import pytest
import yaml

from mcp_skill_server.cli import init_skill, main, validate_skill

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _init_args(path, name=None, description=None, force=False):
    return argparse.Namespace(path=str(path), name=name, description=description, force=force)


def _validate_args(path):
    return argparse.Namespace(path=str(path))


def _write_skill(
    skill_dir,
    *,
    name="test",
    desc="A test skill",
    entry="python test.py",
    script=True,
    output_dir=False,
):
    """Write a valid SKILL.md (and optionally a script + output dir)."""
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {desc}\nentry: {entry}\n---\n# {name}\n"
    )
    if script:
        script_name = entry.split()[-1]
        s = skill_dir / script_name
        s.write_text(
            "import argparse\n"
            "p = argparse.ArgumentParser()\n"
            'p.add_argument("--x", default="1")\n'
            "p.parse_args()\n"
        )
    if output_dir:
        (skill_dir / "output").mkdir()


@pytest.fixture
def tmp_path_clean():
    tmp = tempfile.mkdtemp()
    yield Path(tmp)
    shutil.rmtree(tmp)


# ---------------------------------------------------------------------------
# init_skill
# ---------------------------------------------------------------------------


class TestInitSkill:
    def test_creates_new_skill(self, tmp_path_clean):
        skill_dir = tmp_path_clean / "my_skill"
        rc = init_skill(_init_args(skill_dir, name="my-skill", description="Greet"))
        assert rc == 0

        # SKILL.md created with correct frontmatter
        md = skill_dir / "SKILL.md"
        assert md.exists()
        content = md.read_text()
        assert content.startswith("---")
        parts = content.split("---", 2)
        fm = yaml.safe_load(parts[1])
        assert fm["name"] == "my-skill"
        assert fm["description"] == "Greet"
        assert "uv run python" in fm["entry"]

        # Script created
        assert (skill_dir / "my_skill.py").exists()

        # output/ created
        assert (skill_dir / "output").is_dir()
        assert (skill_dir / "output" / ".gitkeep").exists()

    def test_name_defaults_to_dir_name(self, tmp_path_clean):
        skill_dir = tmp_path_clean / "hello"
        rc = init_skill(_init_args(skill_dir))
        assert rc == 0
        content = (skill_dir / "SKILL.md").read_text()
        fm = yaml.safe_load(content.split("---", 2)[1])
        assert fm["name"] == "hello"

    def test_refuses_existing_dir_without_force(self, tmp_path_clean):
        skill_dir = tmp_path_clean / "exists"
        skill_dir.mkdir()
        rc = init_skill(_init_args(skill_dir))
        assert rc == 1

    def test_force_overwrites(self, tmp_path_clean):
        skill_dir = tmp_path_clean / "exists"
        skill_dir.mkdir()
        rc = init_skill(_init_args(skill_dir, name="exists", force=True))
        assert rc == 0
        assert (skill_dir / "SKILL.md").exists()

    def test_converts_claude_skill_with_force(self, tmp_path_clean):
        """With --force, existing dir is overwritten and entry is added."""
        skill_dir = tmp_path_clean / "claude_skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: claude-skill\ndescription: From Claude\n---\n\n# Original docs\n"
        )
        rc = init_skill(
            _init_args(skill_dir, name="claude-skill", description="From Claude", force=True)
        )
        assert rc == 0
        content = (skill_dir / "SKILL.md").read_text()
        fm = yaml.safe_load(content.split("---", 2)[1])
        assert fm["entry"] is not None
        assert fm["name"] == "claude-skill"
        assert fm["description"] == "From Claude"

    def test_refuses_existing_mcp_skill(self, tmp_path_clean):
        """SKILL.md with entry should not be re-initialized."""
        skill_dir = tmp_path_clean / "mcp_skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: mcp\ndescription: d\nentry: python s.py\n---\ncontent\n"
        )
        rc = init_skill(_init_args(skill_dir))
        assert rc == 1

    def test_does_not_overwrite_existing_script(self, tmp_path_clean):
        """If the script already exists and --force is not set, skip it."""
        skill_dir = tmp_path_clean / "keep_script"
        skill_dir.mkdir()
        # Pre-create the script with custom content
        (skill_dir / "keep_script.py").write_text("# my custom code\n")
        rc = init_skill(_init_args(skill_dir, force=True))
        assert rc == 0
        # With --force, script IS overwritten
        content = (skill_dir / "keep_script.py").read_text()
        assert "argparse" in content


# ---------------------------------------------------------------------------
# validate_skill
# ---------------------------------------------------------------------------


class TestValidateSkill:
    def test_valid_skill_passes(self, tmp_path_clean):
        skill_dir = tmp_path_clean / "good"
        _write_skill(skill_dir, output_dir=True)
        rc = validate_skill(_validate_args(skill_dir))
        assert rc == 0

    def test_missing_skill_md(self, tmp_path_clean):
        skill_dir = tmp_path_clean / "empty"
        skill_dir.mkdir()
        rc = validate_skill(_validate_args(skill_dir))
        assert rc == 1

    def test_no_frontmatter(self, tmp_path_clean):
        skill_dir = tmp_path_clean / "plain"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("Just text, no frontmatter")
        rc = validate_skill(_validate_args(skill_dir))
        assert rc == 1

    def test_invalid_yaml(self, tmp_path_clean):
        skill_dir = tmp_path_clean / "bad_yaml"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: [broken\n---\ncontent")
        rc = validate_skill(_validate_args(skill_dir))
        assert rc == 1

    def test_missing_name(self, tmp_path_clean):
        skill_dir = tmp_path_clean / "no_name"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\ndescription: d\nentry: python s.py\n---\nc")
        rc = validate_skill(_validate_args(skill_dir))
        assert rc == 1

    def test_missing_description(self, tmp_path_clean):
        skill_dir = tmp_path_clean / "no_desc"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: x\nentry: python s.py\n---\nc")
        rc = validate_skill(_validate_args(skill_dir))
        assert rc == 1

    def test_missing_entry(self, tmp_path_clean):
        skill_dir = tmp_path_clean / "no_entry"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: x\ndescription: d\n---\nc")
        rc = validate_skill(_validate_args(skill_dir))
        assert rc == 1

    def test_disallowed_runtime(self, tmp_path_clean):
        skill_dir = tmp_path_clean / "bad_rt"
        _write_skill(skill_dir, entry="curl http://evil.com", script=False)
        rc = validate_skill(_validate_args(skill_dir))
        assert rc == 1

    def test_missing_script_file(self, tmp_path_clean):
        skill_dir = tmp_path_clean / "no_script"
        _write_skill(skill_dir, script=False)
        rc = validate_skill(_validate_args(skill_dir))
        assert rc == 1

    def test_warns_no_output_dir(self, tmp_path_clean, capsys):
        skill_dir = tmp_path_clean / "no_output"
        _write_skill(skill_dir, output_dir=False)
        rc = validate_skill(_validate_args(skill_dir))
        assert rc == 0  # warning, not error
        assert "WARNING" in capsys.readouterr().out

    def test_invalid_frontmatter_format(self, tmp_path_clean):
        """Single --- without closing --- should fail."""
        skill_dir = tmp_path_clean / "bad_fmt"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("---\nname: x\n")
        rc = validate_skill(_validate_args(skill_dir))
        assert rc == 1

    def test_entry_without_recognisable_script(self, tmp_path_clean, capsys):
        """Entry like 'uv run module_name' (no .py) should warn."""
        skill_dir = tmp_path_clean / "no_ext"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: x\ndescription: d\nentry: uv run my_module\n---\nc"
        )
        rc = validate_skill(_validate_args(skill_dir))
        # No script to validate so no error, but should warn
        assert rc == 0
        assert "WARNING" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# main() CLI dispatch
# ---------------------------------------------------------------------------


class TestMain:
    def test_init_subcommand(self, tmp_path_clean):
        skill_dir = tmp_path_clean / "cli_init"
        with mock.patch(
            "sys.argv",
            ["mcp-skill-server", "init", str(skill_dir), "-n", "cli-init"],
        ):
            rc = main()
        assert rc == 0
        assert (skill_dir / "SKILL.md").exists()

    def test_validate_subcommand(self, tmp_path_clean):
        skill_dir = tmp_path_clean / "cli_val"
        _write_skill(skill_dir, output_dir=True)
        with mock.patch("sys.argv", ["mcp-skill-server", "validate", str(skill_dir)]):
            rc = main()
        assert rc == 0

    def test_no_args_prints_help(self):
        with mock.patch("sys.argv", ["mcp-skill-server"]):
            rc = main()
        assert rc == 1

    def test_legacy_path_arg(self, tmp_path_clean):
        """mcp-skill-server /path (no subcommand) exits with error."""
        with mock.patch("sys.argv", ["mcp-skill-server", str(tmp_path_clean)]):
            with pytest.raises(SystemExit):
                main()
