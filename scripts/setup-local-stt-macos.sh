#!/usr/bin/env bash
set -euo pipefail

ROOT="$HOME/.fcc-assistant"
SRC="$ROOT/src/whisper.cpp"
BIN_DIR="$ROOT/bin"
MODEL_DIR="$ROOT/models"
MODEL_NAME="large-v3-turbo"
MODEL_FILE="$MODEL_DIR/ggml-${MODEL_NAME}.bin"

mkdir -p "$ROOT/src" "$BIN_DIR" "$MODEL_DIR"

if ! command -v git >/dev/null 2>&1; then
  echo "git is required" >&2
  exit 1
fi
if ! command -v cmake >/dev/null 2>&1; then
  echo "cmake is required. Install it first (for example with Homebrew)." >&2
  exit 1
fi

if [ ! -d "$SRC/.git" ]; then
  git clone --depth 1 https://github.com/ggml-org/whisper.cpp.git "$SRC"
else
  git -C "$SRC" pull --ff-only
fi

cmake -S "$SRC" -B "$SRC/build" -DCMAKE_BUILD_TYPE=Release
cmake --build "$SRC/build" --config Release -j

WHISPER_BIN="$SRC/build/bin/whisper-cli"
if [ ! -x "$WHISPER_BIN" ]; then
  echo "whisper-cli was not produced at $WHISPER_BIN" >&2
  exit 1
fi
ln -sf "$WHISPER_BIN" "$BIN_DIR/whisper-cli"

if [ ! -f "$MODEL_FILE" ]; then
  "$SRC/models/download-ggml-model.sh" "$MODEL_NAME" "$MODEL_DIR"
fi

printf '\nLocal speech runtime ready.\n'
printf 'Binary: %s\n' "$BIN_DIR/whisper-cli"
printf 'Model:  %s\n' "$MODEL_FILE"
printf 'Language default: el (Greek)\n'
printf 'Audio and transcription stay local.\n'
