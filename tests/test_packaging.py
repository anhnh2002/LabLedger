import json
import re
import zipfile
from pathlib import Path

from labledger import __version__
from labledger.packaging import DESCRIPTIONS, build_marketplace, build_plugins


def test_generated_packages_share_workflows_and_resolve_paths(tmp_path):
    results = build_plugins(tmp_path / "plugins")
    roots = [Path(result["directory"]) for result in results]
    for action in DESCRIPTIONS:
        assert (roots[0] / "resources/workflows" / f"{action}.md").read_bytes() == (
            roots[1] / "resources/workflows" / f"{action}.md"
        ).read_bytes()
    for root in roots:
        assert not (root / "hooks").exists()
        assert (root / "scripts/backend.py").is_file()
        assert (root / "runtime/labledger/backend.py").is_file()
        assert (root / "runtime/labledger/resources/schema.json").is_file()
        assert (root / "runtime/requirements.txt").is_file()
        assert not (root / "runtime/labledger/cli.py").exists()
        assert not (root / "runtime/labledger/__main__.py").exists()
        assert len(list((root / "skills").glob("*/SKILL.md"))) == 10
        for skill in (root / "skills").glob("*/SKILL.md"):
            for relative in re.findall(r"\]\(([^)]+)\)", skill.read_text()):
                assert (skill.parent / relative).resolve().is_file()
        for path in root.rglob("*"):
            if path.is_file():
                assert str(Path.home()).encode() not in path.read_bytes()
        with zipfile.ZipFile(
            next(result["archive"] for result in results if result["directory"] == str(root))
        ) as archive:
            assert all(
                not name.startswith("/") and ".." not in Path(name).parts
                for name in archive.namelist()
            )
    first = Path(results[0]["archive"]).read_bytes()
    build_plugins(tmp_path / "plugins")
    assert Path(results[0]["archive"]).read_bytes() == first


def test_optional_hooks_are_separate_variants(tmp_path):
    default = build_plugins(tmp_path)
    optional = build_plugins(tmp_path, hooks=True)
    for result in optional:
        root = Path(result["directory"])
        hooks = json.loads((root / "hooks/hooks.json").read_text())
        assert set(hooks["hooks"]) == {"SessionStart", "Stop"}
        assert "PreToolUse" not in hooks["hooks"]
        assert (root / "scripts/remind.py").exists()
    assert all(not (Path(result["directory"]) / "hooks").exists() for result in default)


def test_marketplace_is_relocatable_and_contains_only_default_packages(tmp_path):
    import shutil

    staged = tmp_path / "staged"
    archives = tmp_path / "archives"
    result = build_marketplace(staged, archives)
    # Rebuilding must remove stale generated plugin files, including optional hooks.
    (staged / "plugins/labledger-codex/hooks").mkdir()
    (staged / "plugins/labledger-codex/stale.py").touch()
    build_marketplace(staged, archives)
    relocated = tmp_path / "relocated marketplace"
    shutil.move(staged, relocated)
    for host, relative in zip(("codex", "claude"), result["catalogs"], strict=True):
        catalog = json.loads((relocated / relative).read_text())
        assert catalog["name"] == "labledger"
        assert len(catalog["plugins"]) == 1
        entry = catalog["plugins"][0]
        source = entry["source"]
        if host == "codex":
            assert entry["policy"]["installation"] == "AVAILABLE"
            assert entry["category"] == "Productivity"
            source = source["path"]
        root = relocated / source
        assert root.resolve().is_relative_to(relocated)
        manifest = root / ("plugin.json" if host == "codex" else ".claude-plugin/plugin.json")
        identity = json.loads(manifest.read_text())
        assert identity["name"] == entry["name"] == "labledger"
        assert identity["version"] == entry["version"] == __version__
        assert (root / "runtime/labledger/backend.py").is_file()
        assert not (root / "hooks").exists()
        assert not (root / "stale.py").exists()
        assert len(list((root / "skills").glob("*/SKILL.md"))) == len(DESCRIPTIONS)
    assert not list(relocated.rglob("*.zip"))
    assert len(list(archives.glob("*.zip"))) == 2


def test_release_package_versions_agree():
    import tomllib

    project = tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_text())
    assert project["project"]["version"] == __version__
