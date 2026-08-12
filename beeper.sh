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

# The GPU sandbox and the proprietary NVIDIA driver do not get along.
[ -e /dev/nvidia0 ] && FLAGS+=(--disable-gpu-sandbox)

# zypak-wrapper replaces Chromium's SUID sandbox, which cannot work inside a
# Flatpak. Do not add --no-sandbox.
exec zypak-wrapper /app/extra/beepertexts "${FLAGS[@]}" "$@"
