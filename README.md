# AI Daily Bot

Daily AI news + GitHub trending AI projects, delivered to WeCom.

## Setup

1. `pip install -r requirements.txt`
2. Set env vars: `ANTHROPIC_API_KEY`, `WECOM_WEBHOOK_URL`
3. Run: `python src/main.py`

## GitHub Actions

Add `ANTHROPIC_API_KEY` and `WECOM_WEBHOOK_URL` to repository Secrets.
Schedule: daily at 08:00 Beijing time (UTC 00:00).
