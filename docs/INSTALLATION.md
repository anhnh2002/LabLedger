# Install LabLedger

Install LabLedger from its GitHub marketplace in Codex or Claude Code. Each plugin
includes its Python backend, schemas, workflows, and private helpers. Users do not
need to clone the source, install `uv`, or build a package.

## Requirements

- A Codex or Claude Code version with marketplace plugin support.
- macOS or Linux, with Python 3.11+ available to the host's command tool.
- Git and GitHub access for the host to fetch the marketplace.
- Package-index access on the first skill invocation to prepare pinned dependencies.

The agent prepares an isolated runtime in your user cache on first use. Subsequent
requests reuse it. Research-project dependencies and global Python packages are
unchanged. No separate LabLedger executable, server, or API key is required.

## Codex

Run in your terminal:

```sh
codex plugin marketplace add anhnh2002/LabLedger --ref marketplace
codex plugin add labledger@labledger
```

Start a fresh session in your research repository and invoke `$labledger-init`.
Discuss your goals with the agent; it prepares the requests and initializes the
ledger. Verify all ten skills are discoverable. Some surfaces display skills with
the plugin namespace.

If your version supports adding marketplaces but has no `codex plugin add`, open
the desktop app's Plugins Directory, select **LabLedger**, and install the plugin.
See [OpenAI's marketplace documentation](https://developers.openai.com/plugins/build/plugins)
for supported surfaces and installation controls.

To fetch a newer release and refresh the installed package:

```sh
codex plugin marketplace upgrade labledger
codex plugin add labledger@labledger
```

Restart the host or start a new session to load updated skills.

## Claude Code

Run inside a Claude Code session:

```text
/plugin marketplace add anhnh2002/LabLedger#marketplace
/plugin install labledger@labledger
```

You can also install from your terminal:

```sh
claude plugin marketplace add 'anhnh2002/LabLedger#marketplace'
claude plugin install labledger@labledger
```

Start a fresh session in your research repository and invoke `/labledger:init`.
Discuss your goals with the agent; it creates the requests and initializes the
repository. Verify all ten skills are discoverable. LabLedger does not replace
Claude Code's native `/init`.

To update inside a session:

```text
/plugin marketplace update labledger
/plugin update labledger@labledger
```

Start a new session after updating. See Claude Code's
[marketplace guide](https://code.claude.com/docs/en/plugin-marketplaces) and
[plugin commands](https://code.claude.com/docs/en/plugins/cli-reference).

## Releases and ZIP downloads

The `marketplace` branch contains generated, ready-to-install packages. The release
workflow updates it for each stable release. Maintainers should follow the
[release guide](RELEASING.md) to publish a new version.

You can also download `labledger-codex-<version>.zip` or
`labledger-claude-<version>.zip` from
[GitHub Releases](https://github.com/anhnh2002/LabLedger/releases). Release assets
include `SHA256SUMS`. Extract the appropriate ZIP into a dedicated directory and
load it through your host's local plugin controls. Keep the extracted directory;
its backend and resources are required at runtime.

This repository marketplace provides remote installation directly from GitHub.
Listing in a host's public plugin directory is a separate submission process.

## Contributor setup and local testing

From a source checkout:

```sh
uv sync
uv run python scripts/build_plugins.py
```

Generated directories and ZIP archives are under `dist/plugins/`. They can be moved
or extracted elsewhere; resources resolve relative to the plugin root.

For Claude Code local development:

```sh
claude plugin validate dist/plugins/labledger-claude
claude --plugin-dir ./dist/plugins/labledger-claude
```

To build the same catalogs and packages used for remote installation:

```sh
uv run python scripts/build_marketplace.py
```

Register the generated marketplace locally with your host:

```sh
codex plugin marketplace add ./dist/marketplace
codex plugin add labledger@labledger
```

or:

```sh
claude plugin validate dist/marketplace
claude plugin marketplace add ./dist/marketplace
claude plugin install labledger@labledger
```

Use an isolated host configuration when testing, or remove an existing LabLedger
marketplace before switching sources: the local and remote catalogs share the name
`labledger`. Only the appropriate manifest belongs in `.claude-plugin/` or
`.codex-plugin/`; skills, resources, runtime, and helpers stay at the plugin root.

## Optional reminder hooks

The remote marketplace and default release ZIPs contain no hooks. Developers can
build separate local variants:

```sh
uv run python scripts/build_plugins.py --hooks
```

Never install default and hook variants together under the same plugin identity.
Review and trust hooks through the host's controls. Hooks read bounded reminders
from an already prepared runtime. With no runtime, invalid input, or no ledger,
they exit harmlessly. They never install dependencies, change phases, approve work,
run experiments, or block host tools. Set `adapters.hooks` to `disabled` in project
configuration to suppress reminders.

Codex hook support must be verified for the installed surface. See
[OpenAI hooks packaging](https://developers.openai.com/plugins/build/plugins) and
the [Claude hooks reference](https://code.claude.com/docs/en/hooks). All workflows
also work with hooks absent. Installing a plugin does not establish that an
interactive research workflow has been tested.
