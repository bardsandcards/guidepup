#!/bin/sh
# Create one uv venv (python 3.12) per model family. Pinned to CPUs 12-19.
set -x
cd "$(dirname "$0")/.."
mk() { name=$1; shift; taskset -c 12-19 uv venv -q -p 3.12 venvs/$name && VIRTUAL_ENV=venvs/$name taskset -c 12-19 uv pip install -q "$@" soundfile numpy huggingface_hub && echo "VENV_OK $name"; }
mk fw faster-whisper==1.2.1
mk wcpp pywhispercpp==1.5.1
mk moon useful-moonshine-onnx==20251121
mk moonv moonshine-voice==0.1.5
mk onnxasr "onnx-asr[cpu,hub]==0.12.0"
mk sherpa sherpa-onnx==2.0.1
mk vosk vosk==0.3.45
