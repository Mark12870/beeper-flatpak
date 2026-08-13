#!/bin/bash
# Beeper is unpacked into /app/extra at install time by apply_extra.
# Extra Chromium flags can be appended: flatpak run <app-id> --some-flag
set -eu

# ozone-platform-hint=auto picks Wayland when it is there and falls back to X11.
FLAGS=(
    --ozone-platform-hint=auto
    --enable-wayland-ime
    --enable-features=WaylandWindowDecorations,WebRTCPipeWireCapturer
)

# Store data where a non-Flatpak Beeper does, so an existing install carries
# over. XDG_CONFIG_HOME is redirected into the sandbox and cannot reach it, so
# the host path is spelled out. Falls back to the sandbox when the permission
# has been revoked -- starting empty beats not starting.
USER_DATA="${HOME}/.config/BeeperTexts"
mkdir -p "${USER_DATA}" 2>/dev/null || USER_DATA="${XDG_CONFIG_HOME}/BeeperTexts"
FLAGS+=("--user-data-dir=${USER_DATA}")

# zypak-wrapper replaces Chromium's SUID sandbox, which cannot work inside a
# Flatpak. Do not add --no-sandbox.
exec zypak-wrapper /app/extra/beepertexts "${FLAGS[@]}" "$@"
