# Release the remote plugins

Users install generated packages from the `marketplace` branch of this repository.
Contributors work on the source branch. Do not edit generated release files on
`marketplace` by hand.

## Prepare a release

1. Update the version in both `pyproject.toml` and `src/labledger/__init__.py`.
   Increment it for every release so hosts refresh their versioned plugin caches.
2. Run the checks below and complete the applicable manual host checks in
   [VALIDATION.md](VALIDATION.md).
3. Merge the source changes, including `.github/workflows/release.yml`, before
   creating the release tag. The tagged commit must contain the release workflow.
4. Create and push a stable version tag matching both package versions:

   ```sh
   git tag -a v0.1.0 -m 'LabLedger 0.1.0'
   git push origin v0.1.0
   ```

The tag push starts **release plugins** in GitHub Actions. For recovery, run that
workflow manually with the existing tag as its `tag` input. Use the next version
for subsequent releases; do not move a published tag.

## What the workflow publishes

The build job checks tag/version agreement, runs lint, formatting, tests, a Python
package build, and the relocated plugin smoke check. It then passes the generated
files to a publishing job with repository write permission. The publishing job:

- Creates or updates `marketplace` with both ready-to-install plugin directories.
- Includes `.agents/plugins/marketplace.json` for Codex and
  `.claude-plugin/marketplace.json` for Claude Code. Both catalogs are named
  `labledger`, and each exposes the appropriate host package as `labledger`.
- Publishes a GitHub Release with the two versioned default ZIPs and `SHA256SUMS`.

The first successful run enables the remote commands in
[INSTALLATION.md](INSTALLATION.md). Updating the branch preserves its Git history
and uses a regular push. Repository rules must allow GitHub Actions to create or
update `marketplace` and create releases. No additional publishing token is needed;
the job uses the repository's `GITHUB_TOKEN` with `contents: write`.

Only stable `vMAJOR.MINOR.PATCH` tags are supported. Release runs are serialized;
publish versions in increasing order. Publishing an older tag would move the
marketplace back to that version. Hook variants remain a local developer option.
Public plugin-directory submissions and the project's license are separate
maintainer decisions.

## Local validation

```sh
uv sync --locked
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv build
uv run python scripts/build_marketplace.py
uv run python scripts/smoke_release.py
```

`dist/marketplace/` is the complete branch payload. `dist/plugins/` contains the
default package directories, versioned ZIPs, and checksum file. Both destinations
are ignored by Git. The catalogs use paths relative to the marketplace root, so
hosts fetch all needed runtime files without executing a source build.

Use the local marketplace commands in the installation guide to check host
discovery and installation before publishing. Test in isolated host configurations
to avoid changing your existing plugin setup. After publication, verify remote
installation from GitHub on both hosts; local checks cannot prove that repository
permissions or the remote release are configured correctly.
