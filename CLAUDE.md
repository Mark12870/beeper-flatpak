# CLAUDE.md

Flatpak packaging of the proprietary Beeper desktop app, published as a self-hosted
remote on GitHub Pages. App ID `io.github.mark12870.beeper`. `x86_64` only — the
maintainer runs one machine, so there is deliberately no arm build.

## Code style

Aim for clean code. Keep it minimal and readable — no dead config, no scaffolding
that isn't used. Comment only what is non-obvious, and say *why*, not *what*.
Keep the code as simple as possible.

## Build and test

```sh
flatpak run org.flatpak.Builder --repo=repo --force-clean \
  --default-branch=stable build io.github.mark12870.beeper.yml
flatpak install --user beeper-local io.github.mark12870.beeper   # remote: file://$PWD/repo
```

Validate with `desktop-file-validate`, `appstreamcli validate`, and `bash -n`.

## Gotchas

- **Never use `flatpak-builder --install`.** `apply_extra` needs its own bwrap
  sandbox and `org.flatpak.Builder` cannot nest one. Build to `--repo` and install
  from a local `file://` remote.
- **`--appimage-extract` does not work in `apply_extra`.** That sandbox mounts no
  `/proc`. `apply_extra` reads the ELF header to find the appended squashfs and
  unpacks it with `unsquashfs`.
- **Upstream is AppImage-only, with no version manifest and no checksums.** The
  only version signal is the redirect from `api.beeper.com`;
  `scripts/update-version.py` parses it and computes hashes itself. Anything
  referencing `download.todesktop.com` is stale.
- **Upstream's internal name is `beepertexts`**, not `beeper`.
- **Config deliberately lives at `~/.config/BeeperTexts`, not `~/.var/app/`.** `beeper.sh`
  passes `--user-data-dir` because `XDG_CONFIG_HOME` is redirected into the sandbox and
  cannot reach the host path. This is intentional, so installs migrating off the AppImage
  keep their data — do not "fix" it back to the sandbox default.
- **Static deltas break GPG verification.** ostree prefers a delta over plain objects on an
  HTTP remote and the delta carries no detached signature, so every install fails
  gpg-verify. Never re-add `--generate-static-deltas`.
- **Verify signing over HTTP, never `file://`.** Local pulls resolve objects directly and
  skip the delta path, so a `file://` test passes against a repo real clients reject.
- A push made with the default `GITHUB_TOKEN` raises no `push` event, so
  `update-version.yml` invokes `build-publish.yml` directly via `workflow_call`.
- GitHub disables scheduled workflows after 60 days without repository activity. If
  releases stop being picked up, re-enable the schedule from the Actions tab.
- `build-publish.yml` triggers only on the package's own inputs (manifest, `apply_extra`,
  `beeper.sh`, the metainfo/desktop/icon, and itself). A rebuild exports new commits that
  every installed client sees as an update, so docs and script pushes must not fire it.
- Fedora's system `flathub` remote is filtered; add a user-scoped one to install SDKs.

## Changing the manifest

Bump versions and hashes only via `scripts/update-version.py` — it rewrites the
url/sha256/size lines in place and keeps formatting. Re-run a full build and a
launch check after touching `apply_extra` or `beeper.sh`.
