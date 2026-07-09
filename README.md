# NexGenChat Chatbot — Backend

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Playwright (required for website URL knowledge base)

JavaScript websites (React, Next.js, Vue, etc.) need Playwright to render pages before text extraction.

```bash
chmod +x scripts/install_playwright.sh
./scripts/install_playwright.sh
```

Or manually:

```bash
./venv/bin/playwright install chromium
sudo ./venv/bin/playwright install-deps chromium
```

## Run

```bash
./venv/bin/uvicorn app.main:app --reload
```
