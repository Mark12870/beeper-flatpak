#!/usr/bin/env python3
"""Point the manifest at the current Beeper release.

Beeper publishes no version manifest and no checksums for its Linux builds. The
only machine-readable signal is the redirect served by

    https://api.beeper.com/desktop/download/linux/<arch>/stable/com.automattic.beeper.desktop

whose Location header names a versioned AppImage. So: resolve the redirect to
learn the current version, and if it moved, download each architecture's
AppImage to compute the sha256 and size that `type: extra-data` requires.

Exit status is 0 whether or not an update was found; check the `updated` value
written to $GITHUB_OUTPUT (or the final line of stdout) to tell the difference.
"""

from __future__ import annotations

import email.utils
import hashlib
import os
import re
import sys
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MANIFEST = REPO / "io.github.mark12870.beeper.yml"
METAINFO = REPO / "io.github.mark12870.beeper.metainfo.xml"

DOWNLOAD_URL = (
    "https://api.beeper.com/desktop/download/linux/{endpoint}/stable"
    "/com.automattic.beeper.desktop"
)

# Cloudflare fronts both beeper.com hosts and 403s the default Python-urllib
# User-Agent, so identify as something else.
USER_AGENT = "beeper-flatpak/update-version (+https://github.com/Mark12870/beeper-flatpak)"

# Beeper's endpoint name -> the filename suffix it serves, which is also how the
# two extra-data sources are told apart in the manifest.
ARCHES = {"x64": "x86_64", "arm64": "arm64"}

VERSION_RE = re.compile(r"^Beeper-(\d+(?:\.\d+)*)-(?:x86_64|arm64)\.AppImage$")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):  # noqa: D102
        return None


def resolve(endpoint: str) -> tuple[str, str, str]:
    """Return (version, filename, absolute url) for an architecture endpoint."""
    opener = urllib.request.build_opener(NoRedirect)
    request = urllib.request.Request(
        DOWNLOAD_URL.format(endpoint=endpoint),
        method="HEAD",
        headers={"User-Agent": USER_AGENT},
    )
    try:
        opener.open(request, timeout=60)
    except urllib.error.HTTPError as err:
        if err.code not in (301, 302, 303, 307, 308):
            raise
        location = err.headers["Location"]
    else:
        raise SystemExit(f"expected a redirect for {endpoint}, got a direct response")

    filename = location.rsplit("/", 1)[-1]
    match = VERSION_RE.match(filename)
    if not match:
        raise SystemExit(f"cannot parse a version out of {filename!r}")
    return match.group(1), filename, location


def fetch(url: str) -> tuple[str, int, str | None]:
    """Download `url`, returning (sha256, size, release date as YYYY-MM-DD)."""
    digest = hashlib.sha256()
    size = 0
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=900) as response:
        last_modified = response.headers.get("Last-Modified")
        while chunk := response.read(1 << 20):
            digest.update(chunk)
            size += len(chunk)

    date = None
    if last_modified:
        date = email.utils.parsedate_to_datetime(last_modified).strftime("%Y-%m-%d")
    return digest.hexdigest(), size, date


def current_version(manifest: str) -> str | None:
    match = re.search(r"/builds/Beeper-(\d+(?:\.\d+)*)-x86_64\.AppImage", manifest)
    return match.group(1) if match else None


def rewrite_source(manifest: str, suffix: str, url: str, sha256: str, size: int) -> str:
    """Replace the url/sha256/size triple of one architecture's extra-data source.

    Edits the lines in place rather than round-tripping the YAML, so the
    manifest's comments and formatting survive untouched.
    """
    lines = manifest.splitlines(keepends=True)
    url_re = re.compile(
        r"^(\s*url: )https://beeper-desktop\.download\.beeper\.com/builds/"
        rf"Beeper-\S*-{re.escape(suffix)}\.AppImage\s*$"
    )

    for i, line in enumerate(lines):
        match = url_re.match(line)
        if not match:
            continue
        lines[i] = f"{match.group(1)}{url}\n"
        # sha256 and size are the next two keys of the same source.
        for j in range(i + 1, min(i + 4, len(lines))):
            lines[j] = re.sub(r"^(\s*sha256: )\S+$", rf"\g<1>{sha256}", lines[j])
            lines[j] = re.sub(r"^(\s*size: )\d+$", rf"\g<1>{size}", lines[j])
        return "".join(lines)

    raise SystemExit(f"no extra-data source found for {suffix} in {MANIFEST.name}")


def emit(**values: str) -> None:
    for key, value in values.items():
        print(f"{key}={value}")
    if output := os.environ.get("GITHUB_OUTPUT"):
        with open(output, "a", encoding="utf-8") as handle:
            for key, value in values.items():
                handle.write(f"{key}={value}\n")


def main() -> None:
    manifest = MANIFEST.read_text(encoding="utf-8")
    have = current_version(manifest)

    resolved = {arch: resolve(endpoint) for endpoint, arch in ARCHES.items()}
    versions = {version for version, _, _ in resolved.values()}
    if len(versions) > 1:
        # Architectures are usually released in lockstep; if they ever diverge,
        # stop rather than pin the two sources to different versions.
        raise SystemExit(f"architectures disagree on the version: {sorted(versions)}")
    latest = versions.pop()

    print(f"manifest: {have}\nupstream: {latest}")
    if have == latest:
        emit(updated="false", version=latest)
        return

    release_date = None
    for arch, (_, filename, url) in resolved.items():
        print(f"hashing {filename} ...", flush=True)
        sha256, size, date = fetch(url)
        release_date = release_date or date
        manifest = rewrite_source(manifest, arch, url, sha256, size)
        print(f"  sha256={sha256} size={size}")

    MANIFEST.write_text(manifest, encoding="utf-8")

    metainfo = METAINFO.read_text(encoding="utf-8")
    release = f'<release version="{latest}"'
    if release_date:
        release += f' date="{release_date}"'
    metainfo, count = re.subn(
        r'<release version="[^"]*"(?: date="[^"]*")?', release, metainfo, count=1
    )
    if count:
        METAINFO.write_text(metainfo, encoding="utf-8")
    else:
        print(f"warning: no <release> element to update in {METAINFO.name}", file=sys.stderr)

    emit(updated="true", version=latest)


if __name__ == "__main__":
    main()
