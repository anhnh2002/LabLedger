"""Generate both host adapters from the same packaged workflows."""

import json
import shutil
import zipfile
from importlib.resources import files
from pathlib import Path

from . import __version__

DESCRIPTIONS = {
    "init": "Initialize LabLedger research conventions and an agreed charter in a repository.",
    "brainstorm": "Discuss a research decision and hand off the agreed direction to a fresh planning session.",
    "handoff": "Generate or validate LabLedger brief and fresh-session Plan Mode handoff documents.",
    "recall": "Find scoped LabLedger findings before trying or repeating a research approach.",
    "run": "Register and execute a traceable LabLedger experiment with an approved protocol.",
    "analyze": "Analyze LabLedger run evidence and preserve findings, uncertainty, and corrections.",
    "resume": "Recover LabLedger task context, active attempts, and next actions from durable records.",
    "doctor": "Diagnose LabLedger record integrity, stale context, and host capabilities.",
    "report": "Report LabLedger research results and claims with failures and evidence references.",
    "review-generalization": "Assess a research change against declared scope, independent cases, and leakage risks.",
}


def build_plugins(destination, hooks=False):
    destination = Path(destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    outputs = []
    for host in ("codex", "claude"):
        suffix = "-local-hooks" if hooks else ""
        root = destination / f"labledger-{host}{suffix}"
        # Only replace this known generated directory, never the output root.
        if root.exists():
            shutil.rmtree(root)
        root.mkdir()
        resources = root / "resources"
        (resources / "workflows").mkdir(parents=True)
        for name in ("schema.json", "conventions.md", "backend.md"):
            content = files("labledger").joinpath("resources", name).read_text()
            if name == "conventions.md":
                content = content.replace(
                    "`RESEARCH_DIR/CHARTER.md`",
                    "the charter under the research_dir configured in `.labledger/config.toml`",
                )
            (resources / name).write_text(content)
        runtime = root / "runtime"
        runtime.mkdir()
        package = files("labledger")
        shutil.copytree(
            str(package),
            runtime / "labledger",
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "packaging.py"),
        )
        (runtime / "requirements.txt").write_text(
            package.joinpath("resources/runtime-requirements.txt").read_text()
        )
        scripts = root / "scripts"
        scripts.mkdir()
        (scripts / "backend.py").write_text(package.joinpath("resources/backend.py").read_text())
        for action, description in DESCRIPTIONS.items():
            name = f"labledger-{action}" if host == "codex" else action
            skill = root / "skills" / name
            skill.mkdir(parents=True)
            workflow = (
                files("labledger").joinpath("resources/workflows", f"{action}.md").read_text()
            )
            (resources / "workflows" / f"{action}.md").write_text(workflow)
            text = (
                f"---\nname: {name}\ndescription: {json.dumps(description)}\n---\n\n"
                f"Use the LabLedger {__version__} backend bundled with this plugin.\n"
                "Perform the workflow inside this Codex or Claude Code session. Discuss missing\n"
                "information and material decisions with the user; inspect the repository first.\n"
                "Create every JSON request yourself from the discussion and observed evidence,\n"
                "then invoke the private helper. Never delegate payload creation or backend\n"
                "commands to the user. Continue routine steps already authorized.\n\n"
                "Read [the private backend protocol](../../resources/backend.md) for helper\n"
                "invocation, operations, schemas, runtime setup, and error handling.\n"
                f"Read [the {action} workflow](../../resources/workflows/{action}.md).\n"
                "Read [research conventions](../../resources/conventions.md) for the shared boundaries.\n"
                "In native Plan Mode, inspect and discuss without writing project files; defer\n"
                "persistence until execution. The host's tool permissions still apply.\n"
            )
            if action == "brainstorm":
                text += "After agreement, read [handoff](../../resources/workflows/handoff.md) and finish at that boundary.\n"
            (skill / "SKILL.md").write_text(text)
        identity = {
            "name": "labledger",
            "version": __version__,
            "description": "Discuss research decisions, retain evidence, and continue across coding-agent sessions.",
        }
        if host == "codex":
            manifest = {
                "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
                **identity,
            }
            if hooks:
                manifest["extensions"] = {"com.openai": {"hooks": "./hooks/hooks.json"}}
            (root / "plugin.json").write_text(json.dumps(manifest, indent=2) + "\n")
            compatibility = root / ".codex-plugin"
            compatibility.mkdir()
            (compatibility / "plugin.json").write_text(
                json.dumps({**identity, "skills": "./skills/"}, indent=2) + "\n"
            )
        else:
            manifest_dir = root / ".claude-plugin"
            manifest_dir.mkdir()
            (manifest_dir / "plugin.json").write_text(json.dumps(identity, indent=2) + "\n")
        if hooks:
            (scripts / "remind.py").write_text(
                files("labledger").joinpath("resources/remind.py").read_text()
            )
            hooks_dir = root / "hooks"
            hooks_dir.mkdir()
            variable = "PLUGIN_ROOT" if host == "codex" else "CLAUDE_PLUGIN_ROOT"
            config = {
                "hooks": {
                    event: [
                        {
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": f'python3 "${{{variable}}}/scripts/remind.py" {event}',
                                    "timeout": 5,
                                }
                            ]
                        }
                    ]
                    for event in ("SessionStart", "Stop")
                }
            }
            (hooks_dir / "hooks.json").write_text(json.dumps(config, indent=2) + "\n")
        (root / "INSTALL.md").write_text(
            f"# LabLedger {__version__} for {host}\n\nInstall this plugin through the host's plugin controls.\n"
            "Use every LabLedger workflow inside a Codex or Claude Code session. The Python\n"
            "backend is bundled; no LabLedger executable or separate core installation exists.\n"
            "Python 3.11+ is required on macOS/Linux. The agent's private helper prepares pinned\n"
            "dependencies in a user cache on first use (package-index access is needed once).\n"
            "No server or API key is required. All package resources resolve from this folder.\n"
            "Use a fresh host session after installation and verify skill discovery.\n"
            + (
                "This local variant includes reminder hooks. Review and trust hooks in the host. Codex hooks require a supported desktop installation.\n"
                if hooks
                else "This default package contains no hooks and requires no lifecycle-hook support.\n"
            )
        )
        archive = destination / f"{root.name}-{__version__}.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    info = zipfile.ZipInfo(
                        path.relative_to(root).as_posix(), date_time=(2026, 1, 1, 0, 0, 0)
                    )
                    info.compress_type = zipfile.ZIP_DEFLATED
                    info.external_attr = 0o100644 << 16
                    bundle.writestr(info, path.read_bytes())
        outputs.append(
            {"host": host, "directory": str(root), "archive": str(archive), "hooks": hooks}
        )
    return outputs
