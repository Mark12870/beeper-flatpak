# Beeper Flatpak

An unofficial Flatpak packaging of the [Beeper](https://www.beeper.com) desktop app,
published as a self-hosted Flatpak remote via GitHub Pages. `x86_64` only.

> **Not affiliated with, endorsed by, or supported by Beeper or Automattic.**
> Beeper itself is proprietary software. This repository contains only the packaging.

## Install

```sh
flatpak remote-add --if-not-exists beeper \
  https://mark12870.github.io/beeper-flatpak/io.github.mark12870.beeper.flatpakrepo
flatpak install beeper io.github.mark12870.beeper
flatpak run io.github.mark12870.beeper
```

## Where your data lives

`~/.config/BeeperTexts` — the same path Beeper's own AppImage and deb use, not the usual
`~/.var/app/<app-id>/`, so an existing install carries over with nothing to migrate. The app
is granted that one directory and no more.

Two consequences: `flatpak uninstall --delete-data` will **not** remove it, and a native
Beeper installed alongside shares the same data. Credentials are not in there — they go to
the system keyring through libsecret.

## How it works

Beeper ships Linux builds only as an AppImage, from a versioned URL behind a redirect at
`api.beeper.com`, with no version manifest and no published checksums. A daily workflow
follows that redirect, and when the version moves it re-pins the URL, SHA-256 and size in
the manifest, rebuilds, and publishes.

The AppImage is declared as `extra-data`, so nothing of Beeper's is stored here or in the
published OSTree repo: `flatpak install` fetches it straight from Beeper, checks it against
the pinned hash, and unpacks it into `/app/extra` on your machine. That keeps the hosted
repo a few hundred kilobytes instead of ~270 MB, which matters against the 1 GB GitHub Pages
cap.

## Build it yourself

```sh
flatpak install flathub org.flatpak.Builder \
  org.freedesktop.Platform//25.08 org.freedesktop.Sdk//25.08 \
  org.electronjs.Electron2.BaseApp//25.08

flatpak run org.flatpak.Builder --repo=repo --force-clean \
  --default-branch=stable build io.github.mark12870.beeper.yml

flatpak remote-add --user --if-not-exists --no-gpg-verify \
  beeper-local "file://$PWD/repo"
flatpak install --user beeper-local io.github.mark12870.beeper
```

Install from a repo rather than with `flatpak-builder --install`: `apply_extra` needs its own
`bwrap` sandbox and `org.flatpak.Builder` cannot nest one.

## Publishing setup

Enable Pages once at *Settings → Pages → Source: GitHub Actions* — the workflow's token
cannot create the site itself.

Publishing requires a `GPG_PRIVATE_KEY` repository secret, plus `GPG_PASSPHRASE` if the key
has one. The workflow fails rather than publishing unsigned, because clients that added the
remote while it was signed break on an unsigned update.

```sh
gpg --quick-generate-key "Beeper Flatpak <you@example.com>" default default never
gpg --export-secret-keys --armor <KEY_ID> > key.asc   # paste into the secret, then delete
```

## License

The packaging in this repository is MIT licensed (see [LICENSE](LICENSE)). Beeper itself is
proprietary and is covered by its own terms.
