import json
import re
import zipfile
from pathlib import Path

from labledger.packaging import DESCRIPTIONS, build_plugins


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
