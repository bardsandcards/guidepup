# Speech/braille fidelity lab: the Orca lab image plus audio, TTS, braille and Python tooling.
FROM guidepup-orca:26.04
USER root
RUN apt-get update \
 && apt-get install -y --no-install-recommends espeak-ng brltty python3-venv python3-pip sox ffmpeg \
      liblouis-bin socat strace \
 && rm -rf /var/lib/apt/lists/*
USER ubuntu
