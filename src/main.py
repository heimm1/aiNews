"""AI Daily Bot — Main entry point.

Orchestrates: collect → process → format → notify
"""

import logging
import os
import sys

from collectors import collect_all
from processor import process_items
from formatter import format_report
from notifier import send_report


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def main():
    setup_logging()
    logger = logging.getLogger("ai_daily_bot")

    logger.info("=== AI Daily Bot Starting ===")

    env_errors = []
    if not (os.environ.get("ANTHROPIC_AUTH_TOKEN") or os.environ.get("ANTHROPIC_API_KEY")):
        env_errors.append("ANTHROPIC_AUTH_TOKEN or ANTHROPIC_API_KEY")
    if not os.environ.get("WECOM_WEBHOOK_URL"):
        env_errors.append("WECOM_WEBHOOK_URL")

    if env_errors:
        logger.error(f"Missing env vars: {', '.join(env_errors)}")
        logger.error("Please set them in environment or GitHub Secrets.")
        sys.exit(1)

    # 1. Collect
    logger.info("Step 1/4: Collecting items from all sources...")
    raw_items = collect_all()
    if not raw_items:
        logger.error("No items collected. Check network or source availability.")
        sys.exit(1)

    # 2. Process
    logger.info(f"Step 2/4: Processing {len(raw_items)} items with LLM...")
    curated = process_items(raw_items)
    news_count = len(curated.get("news", []))
    github_count = len(curated.get("github_projects", []))
    logger.info(f"  Curated: {news_count} news + {github_count} GitHub projects")

    if news_count == 0 and github_count == 0:
        logger.error("LLM returned no items. Raw items were available — check API.")
        sys.exit(1)

    # 3. Format
    logger.info("Step 3/4: Formatting report...")
    markdown = format_report(curated)
    logger.info(f"  Report length: {len(markdown)} chars")

    # 4. Notify
    logger.info("Step 4/4: Sending to WeCom...")
    ok = send_report(markdown)
    if ok:
        logger.info("=== AI Daily Bot Complete ===")
    else:
        logger.error("=== AI Daily Bot Failed — Could not send to WeCom ===")
        sys.exit(1)


if __name__ == "__main__":
    main()
