# CLAUDE.md

Flatpak packaging of the proprietary Beeper desktop app, published as a self-hosted
remote on GitHub Pages. App ID `io.github.mark12870.beeper`. `x86_64` only — the
maintainer runs one machine, so there is deliberately no arm build.

## Code style

Keep it minimal and readable — no dead config, no scaffolding that isn't used.
Comment only what is non-obvious, and say *why*, not *what*. The same goes for
prose: a doc fix should not come out longer than what it replaced.

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
  cannot reach the host path. Installs migrating off the AppImage keep their data this way
  — do not "fix" it back to the sandbox default.
- **Static deltas break GPG verification.** ostree prefers a delta over plain objects on an
  HTTP remote and the delta carries no detached signature, so every install fails gpg-verify.
  Never re-add `--generate-static-deltas`. Always verify signing over HTTP: a `file://` pull
  resolves objects directly, skips the delta path, and passes against a repo clients reject.
- A push made with the default `GITHUB_TOKEN` raises no `push` event, so
  `update-version.yml` invokes `build-publish.yml` directly via `workflow_call`.
- GitHub disables scheduled workflows after 60 days without repository activity. If
  releases stop being picked up, re-enable the schedule from the Actions tab.
- Pages had to be enabled by hand at *Settings → Pages → Source: GitHub Actions*.
  `configure-pages` with `enablement: true` fails: creating the site needs
  `administration: write`, which `GITHUB_TOKEN` cannot be granted.
- Publishing needs the `GPG_PRIVATE_KEY` secret, plus `GPG_PASSPHRASE` if the key has one.
  The workflow fails rather than publishing unsigned — a remote added while signed breaks
  on an unsigned update.
- `build-publish.yml` triggers only on the package's own inputs, never on docs, `scripts/`
  or `site/`: a rebuild exports a commit every installed client sees as an update, and burns
  a slot of rollback history. Page edits ship with the next real publish; preview locally
  with `scripts/render-site.py --repo repo --out /tmp/site --unsigned`.
- **The build seeds `repo/` from the published Pages repo before building.** Without that
  pull each export is a parentless root with no history to roll back along. The seed step
  fails loudly on any fetch error but a 404 — a network blip read as "first publish" would
  silently discard every rollback target.
- `ostree pull` defaults to `--depth=0`, which fetches no history at all. `--depth=-1` is
  safe past the pruned end — ostree stops there rather than failing — so it needs no coupling
  to `HISTORY_DEPTH`. Untested against a pruned remote; the repo has not hit the cap yet.
- `ostree gpg-sign` **fails** on a commit already signed with that key ("Commit is already
  signed with GPG key"), so the `commitmeta` check that skips heads carried in from the pull
  is load-bearing, not tidiness — without it every publish after the first dies there.
- Fedora's system `flathub` remote is filtered; add a user-scoped one to install SDKs.

## Changing the manifest

Bump versions and hashes only via `scripts/update-version.py` — it rewrites the
url/sha256/size lines in place and keeps formatting. Re-run a full build and a
launch check after touching `apply_extra` or `beeper.sh`.
