#!/usr/bin/env bash
# Pre-download the SentenceTransformer embedding model into the local
# HuggingFace cache so live servers can run with EMBEDDING_LOCAL_FILES_ONLY=true.
#
# Usage (on a machine with internet, then copy the HF cache to live):
#   chmod +x scripts/download_embedding_model.sh
#   ./scripts/download_embedding_model.sh
#
# Optional:
#   EMBEDDING_MODEL_NAME=sentence-transformers/all-MiniLM-L6-v2 ./scripts/download_embedding_model.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -f "venv/bin/activate" ]]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
fi

MODEL_NAME="${EMBEDDING_MODEL_NAME:-sentence-transformers/all-MiniLM-L6-v2}"

python3 - <<PY
from sentence_transformers import SentenceTransformer
import os

model_name = os.environ.get(
    "EMBEDDING_MODEL_NAME",
    "sentence-transformers/all-MiniLM-L6-v2",
)
print(f"Downloading embedding model: {model_name}")
SentenceTransformer(model_name, local_files_only=False)
print("Download complete. Model is cached for offline use.")
PY
