# Orca lab base image: Ubuntu 26.04 with what @guidepup/setup --ci installs, Node 24 and Firefox deps.
# guidepup's own Orca asset (Orca 51.1) is installed into GUIDEPUP_SCREEN_READERS_PATH by sf.sh.
FROM ubuntu:26.04

ARG USER_UID=1000
ARG USER_GID=1000
ARG NODE_MAJOR=24
ARG PLAYWRIGHT_VERSION=1.62.1
ARG GUIDEPUP_SETUP_VERSION=0.29.2

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl git gnupg sudo xz-utils \
 && curl -fsSL "https://deb.nodesource.com/setup_${NODE_MAJOR}.x" | bash - \
 && apt-get install -y --no-install-recommends nodejs \
 && npm install -g npm@11 \
 && rm -rf /var/lib/apt/lists/*

# Same apt layer CI gets from `@guidepup/setup setup --ci` (orca, xvfb, dbus-x11, dconf, pulseaudio...).
RUN npx -y --min-release-age=0 --ignore-scripts=false "@guidepup/setup@${GUIDEPUP_SETUP_VERSION}" setup --ci \
 && rm -rf /var/lib/apt/lists/*

# GitHub's ubuntu-26.04 runners ship Firefox's host libraries; a bare image doesn't.
RUN npx -y --min-release-age=0 "playwright@${PLAYWRIGHT_VERSION}" install-deps firefox \
 && rm -rf /var/lib/apt/lists/*

# A window manager, so the active window can hold X input focus as on a desktop.
# sf.sh runs without one (like upstream CI), so key echo is reported three times.
RUN apt-get update \
 && apt-get install -y --no-install-recommends openbox \
 && rm -rf /var/lib/apt/lists/*

# ubuntu:26.04 already has an `ubuntu` user at uid 1000, which matches the host
# owner of the bind-mounted repo. Remap it if the host uid differs.
RUN usermod -u "${USER_UID}" ubuntu && groupmod -g "${USER_GID}" ubuntu \
 && echo "ubuntu ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/ubuntu

USER ubuntu
# Pre-create ~/.cache so the named volume mounted there is owned by ubuntu.
RUN mkdir -p /home/ubuntu/.cache
WORKDIR /work
