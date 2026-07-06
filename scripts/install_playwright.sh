#!/usr/bin/env bash
# Install Playwright Chromium browser and Linux system dependencies
# required for JavaScript website URL ingestion in the knowledge base.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV_PYTHON="${ROOT}/venv/bin/python"
PLAYWRIGHT="${ROOT}/venv/bin/playwright"

if [[ ! -x "${PLAYWRIGHT}" ]]; then
  echo "Playwright not found. Install Python packages first:"
  echo "  cd ${ROOT} && ./venv/bin/pip install -r requirements.txt"
  exit 1
fi

echo "Installing Playwright Chromium browser..."
"${PLAYWRIGHT}" install chromium

echo ""
echo "Installing Playwright system dependencies (requires sudo)..."
if command -v sudo >/dev/null 2>&1; then
  sudo "${PLAYWRIGHT}" install-deps chromium
else
  "${PLAYWRIGHT}" install-deps chromium
fi

echo ""
echo "Verifying Playwright Chromium..."
"${VENV_PYTHON}" -c "
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    browser.close()
print('Playwright Chromium is ready.')
"
