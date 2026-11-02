# Install the host plugin

Install LabLedger as a plugin in Codex or Claude Code. Both packages include the
backend and resources. Do not install a separate LabLedger wheel, pipx tool, or
executable. All research workflows run inside a coding-agent session.

Python 3.11+ on macOS/Linux must be available to the host's command tool. The first
skill invocation prepares pinned dependencies in an isolated user cache, requiring
package-index access. The agent handles this inside the session; no research-project
dependencies or global LabLedger installation are changed. Subsequent requests use
the cached environment. If setup fails, the agent diagnoses the failure in-session.

## Build from this repository

For local development, run `uv sync`, then `uv run python scripts/build_plugins.py`.
The generated directories and zip archives are under `dist/plugins/`. They can be
moved or extracted elsewhere; resources resolve relative to the plugin root.
Builds bundle the current core, so no separate version matching is required.

## Claude Code

Load `dist/plugins/labledger-claude` through Claude Code's plugin installation
controls. For local development, the host supports:

```sh
claude plugin validate dist/plugins/labledger-claude
claude --plugin-dir ./dist/plugins/labledger-claude
```

Inside the session, invoke `/labledger:init` and discuss your research goals.
The agent creates the JSON and initializes the repository. Verify the remaining
skills are discoverable. Do not replace the host's native `/init`.

For team distribution, use a Claude Code marketplace. Follow the official
[plugin documentation](https://code.claude.com/docs/en/plugins). Only the manifest
belongs inside `.claude-plugin/`; skills, resources, runtime, and helpers remain
at the package root. Validate on the exact host version being released.

## Codex

Add `dist/plugins/labledger-codex` to a local/repository marketplace through Codex's
plugin installation controls. The folder contains a portable root manifest,
compatibility manifest, skills, resources, and the bundled backend.

In a fresh session in your research repository, select the LabLedger init skill
(`$labledger-init` where supported) and discuss your goals. Verify skill discovery
on the Codex surface in use; plugin skills may be shown with the plugin namespace.

Follow [OpenAI packaging documentation](https://developers.openai.com/plugins/build/plugins)
and [skill discovery documentation](https://learn.chatgpt.com/docs/build-skills).
Plugin installation and native planning controls vary by surface. An installed
host executable does not establish that an interactive workflow was tested.

## Optional reminder hooks

Developers can build separate variants with `uv run python scripts/build_plugins.py --hooks`.
Default packages have no hooks. Never install default and hook variants together
under the same plugin identity. Review/trust hooks through the host's controls.

Hooks read bounded reminders from an already prepared bundled runtime. With no
runtime, invalid input, or no ledger, they exit harmlessly. They never install
dependencies, change phases, approve work, run experiments, or block host tools.
Set adapters.hooks to disabled in project configuration to suppress reminders.

Codex hook support must be verified for the installed surface; OpenAI documents
hooks for manually installed desktop plugins. See [OpenAI hooks packaging](https://developers.openai.com/plugins/build/plugins)
and [Claude hooks reference](https://code.claude.com/docs/en/hooks).
All core workflows must also work with hooks absent. Public publication, publisher
identity, licensing, and marketplace submission remain separate release actions.
