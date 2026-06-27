"""WeCom webhook notification delivery."""

import logging
import os

import httpx

logger = logging.getLogger(__name__)


def send_markdown(content, webhook_url):
    """Send a single Markdown message to WeCom webhook. Returns True on success."""
    if not webhook_url:
        logger.error("WeCom webhook URL is empty")
        return False

    payload = {
        "msgtype": "markdown",
        "markdown": {
            "content": content,
        },
    }

    try:
        with httpx.Client(timeout=30) as client:
            resp = client.post(webhook_url, json=payload)
            resp.raise_for_status()
            data = resp.json()

            if data.get("errcode") == 0:
                logger.info("WeCom message sent successfully")
                return True
            else:
                logger.error(f"WeCom API error: {data}")
                return False
    except Exception as e:
        logger.error(f"WeCom send failed: {e}")
        return False


def send_report(markdown_content, webhook_url=None, max_chars=4096):
    """Send report to WeCom, auto-splitting if too long. Returns True on success."""
    if webhook_url is None:
        webhook_url = os.environ.get("WECOM_WEBHOOK_URL", "")

    if not webhook_url:
        logger.error("WECOM_WEBHOOK_URL not set")
        return False

    from .formatter import split_message

    parts = split_message(markdown_content, max_chars)
    all_ok = True

    for i, part in enumerate(parts):
        if len(parts) > 1:
            logger.info(f"Sending part {i+1}/{len(parts)}")

        ok = send_markdown(part, webhook_url)
        if not ok:
            logger.error(f"Failed to send part {i+1}")
            all_ok = False

    return all_ok
