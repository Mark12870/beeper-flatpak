#!/usr/bin/env python3
"""Render the Pages front page and the .flatpakrepo from the published repo.

The version table is read back out of the OSTree history rather than tracked
separately, so it lists exactly what a client can install: every commit still in
the repo, with the AppImage URL that commit would actually download.

Because the app is `extra-data`, a rollback also depends on Beeper still serving
that AppImage. Each distinct URL is checked here, and retired ones are reported
as workflow warnings.

Usage locally, against a repo built by flatpak-builder:

    python3 scripts/render-site.py --repo repo --out /tmp/site
"""

from __future__ import annotations

import argparse
import configparser
import html
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from string import Template

REPO = Path(__file__).resolve().parent.parent
TEMPLATE = REPO / "site" / "index.html.in"

# Same reason as in update-version.py: Cloudflare 403s the default urllib agent.
USER_AGENT = "beeper-flatpak/render-site (+https://github.com/Mark12870/beeper-flatpak)"

VERSION_RE = re.compile(r"Beeper-(\d+(?:\.\d+)*)-x86_64\.AppImage")

AVAILABLE, RETIRED, UNKNOWN = "available", "retired", "unknown"


def ostree(repo: Path, *args: str) -> str:
    # LC_ALL=C so `log` timestamps stay parseable under any runner locale.
    result = subprocess.run(
        ["ostree", f"--repo={repo}", *args],
        check=True, capture_output=True, text=True, env={**os.environ, "LC_ALL": "C"},
    )
    return result.stdout


def app_ref(repo: Path) -> str:
    refs = [r for r in ostree(repo, "refs").split() if r.startswith("app/")]
    if len(refs) != 1:
        raise SystemExit(f"expected exactly one app/ ref in {repo}, found {refs}")
    return refs[0]


def history(repo: Path, ref: str) -> list[tuple[str, datetime]]:
    """Return (commit, timestamp) newest first, for every commit still present."""
    commits, commit = [], None
    for line in ostree(repo, "log", ref).splitlines():
        if line.startswith("commit "):
            commit = line.split()[1]
        elif line.startswith("Date:") and commit:
            when = datetime.strptime(line.split(":", 1)[1].strip(), "%Y-%m-%d %H:%M:%S %z")
            commits.append((commit, when))
            commit = None
    return commits


def extra_data(repo: Path, commit: str) -> tuple[str, str, int] | None:
    """Return (version, uri, size) from the commit's [Extra Data] stanza."""
    parser = configparser.ConfigParser()
    parser.read_string(ostree(repo, "cat", commit, "/metadata"))
    if not parser.has_section("Extra Data"):
        return None
    uri = parser.get("Extra Data", "uri")
    match = VERSION_RE.search(uri)
    return (match.group(1) if match else "?", uri, parser.getint("Extra Data", "size"))


def upstream_status(uri: str) -> str:
    """Is Beeper still serving this AppImage?

    Only a definite 404/410 counts as retired -- a timeout or a Cloudflare block
    would otherwise raise a false alarm on a version that is still fine.
    """
    request = urllib.request.Request(uri, method="HEAD", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return AVAILABLE if response.status == 200 else UNKNOWN
    except urllib.error.HTTPError as err:
        return RETIRED if err.code in (404, 410) else UNKNOWN
    except (urllib.error.URLError, TimeoutError):
        return UNKNOWN


def human_size(size: int) -> str:
    return f"{size / 1_000_000:.0f} MB"


def render_rows(versions: list[tuple[str, datetime, str, str]]) -> str:
    rows = []
    for index, (version, when, status, commit) in enumerate(versions):
        current = ' class="is-current"' if index == 0 else ""
        rows.append(
            f"    <tr{current}>"
            f"<td>{html.escape(version)}</td>"
            f'<td>{when.strftime("%Y-%m-%d")}</td>'
            f'<td class="status-{status}">{status}</td>'
            f'<td class="commit"><code>{commit}</code></td></tr>'
        )
    return "\n".join(rows)


def write_flatpakrepo(path: Path, base: str, homepage: str, key: str) -> None:
    lines = [
        "[Flatpak Repo]",
        "Title=Beeper (unofficial)",
        f"Url={base}/repo/",
        f"Homepage={homepage}",
        "Comment=Unofficial Flatpak build of the Beeper desktop app",
        "Description=Unofficial Flatpak packaging of the official Beeper desktop"
        " application. Not affiliated with Beeper or Automattic.",
    ]
    if key:
        lines.append(f"GPGKey={key}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True, help="OSTree repo to describe")
    parser.add_argument("--out", type=Path, required=True, help="directory to write into")
    parser.add_argument("--base-url", default=".", help="public URL of --out, no trailing slash")
    parser.add_argument("--homepage", default="https://github.com/Mark12870/beeper-flatpak")
    parser.add_argument("--gpg-fingerprint", default="")
    parser.add_argument("--gpg-key", default="", help="base64 of the exported public key")
    parser.add_argument("--unsigned", action="store_true", help="local previews only")
    args = parser.parse_args()

    # A .flatpakrepo with no GPGKey adds the remote with gpg-verify off, which is a
    # silent downgrade for everyone who installs from it. Make it a deliberate choice.
    if not args.gpg_key and not args.unsigned:
        raise SystemExit("--gpg-key is required; pass --unsigned for a local preview")

    ref = app_ref(args.repo)
    app_id = ref.split("/")[1]
    base = args.base_url.rstrip("/")

    commits = history(args.repo, ref)
    known = [(commit, when, extra_data(args.repo, commit)) for commit, when in commits]
    known = [(commit, when, data) for commit, when, data in known if data]
    if not known:
        raise SystemExit(f"no commits with extra-data found in {args.repo}")

    # Deduplicated: a rebuild of the same release shares its URL, and there is no
    # sense hammering Beeper's CDN once per commit when it answers once per file.
    uris = list(dict.fromkeys(data[1] for _, _, data in known))
    with ThreadPoolExecutor(max_workers=8) as pool:
        checked = dict(zip(uris, pool.map(upstream_status, uris)))

    versions = []
    for commit, when, (version, uri, _) in known:
        status = checked[uri]
        print(f"{version:<10} {when:%Y-%m-%d}  {status:<9} {commit[:12]}")
        if status == RETIRED:
            print(f"::warning::Beeper no longer serves {uri}; {version} can no longer be installed")
        versions.append((version, when, status, commit))

    _, current_when, (current_version, _, current_size) = known[0]

    args.out.mkdir(parents=True, exist_ok=True)
    page = Template(TEMPLATE.read_text(encoding="utf-8")).substitute(
        app_id=app_id,
        repo_url=f"{base}/repo/",
        flatpakrepo_url=f"{base}/{app_id}.flatpakrepo",
        homepage=html.escape(args.homepage),
        current_version=html.escape(current_version),
        current_date=f"{current_when:%Y-%m-%d}",
        current_size=human_size(current_size),
        history_depth=len(versions),
        gpg_fingerprint=html.escape(args.gpg_fingerprint) or "unsigned build",
        rows=render_rows(versions),
        generated=f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC}",
    )
    (args.out / "index.html").write_text(page, encoding="utf-8")
    write_flatpakrepo(args.out / f"{app_id}.flatpakrepo", base, args.homepage, args.gpg_key)
    print(f"wrote {args.out}/index.html and {app_id}.flatpakrepo", file=sys.stderr)


if __name__ == "__main__":
    main()
