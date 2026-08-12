# Beeper Flatpak

An unofficial Flatpak packaging of the [Beeper](https://www.beeper.com) desktop app,
published as a self-hosted Flatpak remote via GitHub Pages.

> **Not affiliated with, endorsed by, or supported by Beeper or Automattic.**
> Beeper itself is proprietary software. This repository contains only the packaging.

## Install

```sh
flatpak remote-add --if-not-exists beeper \
  https://mark12870.github.io/beeper-flatpak/io.github.mark12870.beeper.flatpakrepo
flatpak install beeper io.github.mark12870.beeper
flatpak run io.github.mark12870.beeper
```

Builds are published for `x86_64` and `aarch64`.

## How it works

Beeper ships Linux builds only as an AppImage, from a versioned URL behind a redirect at
`api.beeper.com`. There is no version manifest and no published checksums.

The manifest therefore declares that AppImage as **`extra-data`**: nothing of Beeper's is
stored in this repository or in the published OSTree repo. `flatpak install` fetches the
AppImage straight from Beeper's servers, verifies it against a SHA-256 pinned in
[`io.github.mark12870.beeper.yml`](io.github.mark12870.beeper.yml), and then unpacks it into
`/app/extra` on your machine. That keeps the hosted repo a few hundred kilobytes instead of
~270 MB per architecture, which matters because GitHub Pages caps a site at 1 GB.

[`apply_extra`](apply_extra) does that unpacking, and it does not use
`--appimage-extract`: Flatpak's install-time sandbox mounts no `/proc`, and the AppImage
runtime resolves its own path through `/proc/self/exe`. Instead it reads the ELF header to
find the squashfs appended after the section header table, and unpacks that with
`unsquashfs` — which is why the manifest builds `squashfs-tools`.

The app runs under `zypak-wrapper` from `org.electronjs.Electron2.BaseApp`, which stands in for
Chromium's SUID sandbox — so unlike the AppImage, this build does **not** need `--no-sandbox`.

[`scripts/update-version.py`](scripts/update-version.py) runs daily at **05:17 UTC**, resolves
the redirect to detect a new release, re-computes the hashes, and commits the bump. It then
invokes the build workflow directly, passing the commit it just made — a push made with the
default `GITHUB_TOKEN` does not raise a `push` event, so the bump would otherwise never build.

Editing the packaging itself (any push to `main` outside `README.md`/`.gitignore`) builds and
republishes on its own. Both workflows can also be run by hand from the **Actions** tab.

> GitHub disables scheduled workflows after **60 days without repository activity**, and pauses
> them on public repos that go inactive. If releases stop being picked up, re-enable the
> schedule from the Actions tab.

## Extra launch flags

Add one flag per line to `~/.config/beeper-flags.conf` (blank lines and `#` comments are ignored):

```
--disable-gpu
```

## Building it yourself

```sh
flatpak install flathub org.flatpak.Builder \
  org.freedesktop.Platform//25.08 org.freedesktop.Sdk//25.08 \
  org.electronjs.Electron2.BaseApp//25.08

# Build into a local repo.
flatpak run org.flatpak.Builder --repo=repo --force-clean \
  --default-branch=stable build io.github.mark12870.beeper.yml

# Then install from it, from outside the builder's sandbox.
flatpak remote-add --user --if-not-exists --no-gpg-verify \
  beeper-local "file://$PWD/repo"
flatpak install --user beeper-local io.github.mark12870.beeper

flatpak run io.github.mark12870.beeper
```

> Install from a repo rather than with `flatpak-builder --install`. `apply_extra`
> runs inside its own `bwrap` sandbox, and `org.flatpak.Builder` cannot nest one,
> so `--install` fails with a namespace error. The host's `flatpak` handles it fine.

## Publishing setup

**Enable Pages once** at *Settings → Pages → Source: GitHub Actions*. This cannot be
automated: creating a Pages site needs `administration: write`, which the workflow's
`GITHUB_TOKEN` cannot be granted — `pages: write` only allows deploying to a site that
already exists.

Publishing **requires** a `GPG_PRIVATE_KEY` repository secret; the workflow fails without
one rather than publishing unsigned. That is deliberate — clients that added the remote
while it was signed break on an unsigned update, so a green build must never quietly
downgrade it.

Use a key with **no passphrase**: CI imports it with `gpg --batch`, which cannot answer a
prompt.

To set it up, generate a key and store the private half as the secret:

```sh
gpg --quick-generate-key "Beeper Flatpak <you@example.com>" default default never
gpg --list-secret-keys --keyid-format=long          # note the key id
gpg --export-secret-keys --armor <KEY_ID> > beeper-flatpak-key.asc
```

Paste the file's contents into *Settings → Secrets and variables → Actions → New repository
secret*, name it `GPG_PRIVATE_KEY`, then delete the file. The next run picks it up; no code
change is needed.

Each publish rebuilds the OSTree repo from scratch. Because the payload is `extra-data` the
commits are tiny, but it does mean a manual re-run of the workflow shows up to clients as an
available update even when nothing changed.

## Layout

| Path                                      | Purpose                                                      |
| ----------------------------------------- | ------------------------------------------------------------ |
| `io.github.mark12870.beeper.yml`          | Flatpak manifest                                             |
| `apply_extra`                             | Unpacks the AppImage at install time, on the user's machine  |
| `beeper.sh`                               | Launcher: Wayland/proxy flag detection, then `zypak-wrapper` |
| `io.github.mark12870.beeper.desktop`      | Desktop entry                                                |
| `io.github.mark12870.beeper.metainfo.xml` | AppStream metadata                                           |
| `scripts/update-version.py`               | Release tracking and hash re-pinning                         |
| `.github/workflows/`                      | Version check, build, and Pages publish                      |

## License

The packaging in this repository is MIT licensed (see [LICENSE](LICENSE)). Beeper itself is
proprietary and is covered by its own terms.
