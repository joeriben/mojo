# Third-Party Licenses

This project uses the following third-party libraries for the abstract backfill feature
(`journal_bot/abstract_backfill.py`). Both are optional dependencies.

## curl_cffi

- **Purpose**: HTTP requests with browser TLS fingerprinting (bypasses Cloudflare for abstract retrieval)
- **License**: MIT
- **Homepage**: https://github.com/lexiforest/curl_cffi
- **Install**: `pip install curl_cffi`

## Playwright

- **Purpose**: Headless browser for JS-rendered publisher pages (fallback for curl_cffi)
- **License**: Apache-2.0
- **Homepage**: https://github.com/microsoft/playwright-python
- **Install**: `pip install playwright && playwright install chromium`

## Other dependencies (in requirements.txt)

| Package | License | Purpose |
|---------|---------|---------|
| httpx | BSD-3-Clause | HTTP client |
| feedparser | BSD-2-Clause | RSS/Atom feed parsing |
| selectolax | MIT | HTML parsing |
| openai | Apache-2.0 | OpenRouter API client |
| pyzotero | GPL-3.0 | Zotero API client |
| pypdf | BSD-3-Clause | PDF text extraction |
