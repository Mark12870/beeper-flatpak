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

[mark12870.github.io/beeper-flatpak](https://mark12870.github.io/beeper-flatpak/) lists the
versions currently installable.

## Rolling back

Around a hundred releases stay in the published repo, so a bad Beeper update can be undone:

```sh
flatpak remote-info --log beeper io.github.mark12870.beeper   # or use the site
flatpak update --commit=<COMMIT> io.github.mark12870.beeper
```

A plain `flatpak update` moves you forward again; `flatpak mask io.github.mark12870.beeper`
holds the rollback until you unmask it.

The AppImage is fetched from Beeper at install time, so a rollback only works while Beeper
still serves that version — the site's **Upstream** column tracks which ones it still does.

## App permissions and data

`~/.config/BeeperTexts` — the same path Beeper's own AppImage uses, not the usual
`~/.var/app/<app-id>/`, so an existing install carries over with nothing to migrate. That one
directory is its only home access; it also gets `~/Downloads`, PipeWire, and `--device=all`.

So `flatpak uninstall --delete-data` will **not** remove it, and a native Beeper installed
alongside shares the same data. Credentials are not in there — they go to the system keyring
through libsecret.

## How it works

Beeper ships Linux builds only as an AppImage, behind a redirect at `api.beeper.com` with no
version manifest and no published checksums. A daily workflow follows that redirect and, when
the version moves, re-pins the URL, SHA-256 and size, rebuilds, and publishes.

The AppImage is declared as `extra-data`, so nothing of Beeper's is stored here or in the
published repo: `flatpak install` fetches it straight from Beeper and checks it against the
pinned hash before unpacking it into `/app/extra` on your machine.

## License

The packaging is MIT licensed (see [LICENSE](LICENSE)). Beeper itself is proprietary, as is
its logo (`io.github.mark12870.beeper.png`), which is excluded from that grant.
