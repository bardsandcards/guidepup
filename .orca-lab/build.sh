#!/usr/bin/env bash
# Build the lab images: guidepup-orca:26.04 (base), then guidepup-orca:26.04-audio (speech/braille tooling).
set -euo pipefail
cd "$(dirname "$0")"
docker build --build-arg USER_UID="$(id -u)" --build-arg USER_GID="$(id -g)" -t guidepup-orca:26.04 .
docker build -t guidepup-orca:26.04-audio speech-fidelity/image
