"""Data collection from RSS feeds, ArXiv, and GitHub."""

import logging
import os
import re
import xml.etree.ElementTree as ET

import feedparser
import httpx
import yaml

logger = logging.getLogger(__name__)

ARXIV_NS = "{http://www.w3.org/2005/Atom}"

USER_AGENT = "ai-daily-bot/1.0"


def load_config(path="config/sources.yaml"):
    try:
        with open(path, "r") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        logger.warning(f"Config file not found at {path}, using defaults")
        return {"rss_feeds": [], "arxiv": {}, "github": {}}
    except (yaml.YAMLError, OSError) as e:
        logger.warning(f"Failed to load config from {path}: {e}, using defaults")
        return {"rss_feeds": [], "arxiv": {}, "github": {}}


def fetch_rss_items(feed_url, source_name, language):
    """Fetch and parse an RSS feed. Returns list of standardized item dicts."""
    items = []
    try:
        with httpx.Client(timeout=60, follow_redirects=True) as client:
            resp = client.get(feed_url, headers={"User-Agent": USER_AGENT})
            resp.raise_for_status()

        feed = feedparser.parse(resp.text)
        for entry in feed.entries:
            title = (entry.get("title") or "").strip()
            summary = (entry.get("summary") or entry.get("description") or "").strip()
            if not title:
                continue
            url = entry.get("link", "")
            items.append({
                "title": title,
                "summary": summary,
                "url": url,
                "source": source_name,
                "language": language,
                "item_type": "news",
            })
    except Exception as e:
        logger.warning(f"Failed to fetch RSS from {source_name}: {e}")

    return items


def fetch_arxiv_items(category="cs.AI", max_results=15):
    """Fetch recent papers from ArXiv API."""
    items = []
    url = (
        f"https://export.arxiv.org/api/query?"
        f"search_query=cat:{category}&sortBy=lastUpdatedDate&max_results={max_results}"
    )
    try:
        with httpx.Client(timeout=60, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": USER_AGENT})
            resp.raise_for_status()

        root = ET.fromstring(resp.text)
        for entry in root.findall(f"{ARXIV_NS}entry"):
            title_el = entry.find(f"{ARXIV_NS}title")
            summary_el = entry.find(f"{ARXIV_NS}summary")
            id_el = entry.find(f"{ARXIV_NS}id")

            title = (title_el.text or "").strip().replace("\n", " ") if title_el is not None else ""
            summary = (summary_el.text or "").strip().replace("\n", " ")[:500] if summary_el is not None else ""
            if not title:
                continue

            items.append({
                "title": title,
                "summary": summary,
                "url": (id_el.text or "").strip() if id_el is not None else "",
                "source": "ArXiv cs.AI",
                "language": "en",
                "item_type": "news",
            })
    except Exception as e:
        logger.warning(f"Failed to fetch ArXiv: {e}")

    return items


def fetch_github_items(queries, max_per_query, github_token=None):
    """Fetch trending AI repos from GitHub Search API and Trending page."""
    items = []
    headers = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"

    with httpx.Client(timeout=30, headers=headers) as client:
        # Official Search API
        for query in queries:
            try:
                sort_params = "&sort=stars&order=desc&per_page=" + str(max_per_query)
                url = f"https://api.github.com/search/repositories?q={query}{sort_params}"
                resp = client.get(url)
                resp.raise_for_status()
                data = resp.json()

                for repo in data.get("items", []):
                    items.append({
                        "title": f"{repo['full_name']} ⭐{repo['stargazers_count']}",
                        "summary": repo.get("description") or "No description",
                        "url": repo["html_url"],
                        "source": "GitHub Search",
                        "language": "en",
                        "item_type": "github",
                        "stars": repo.get("stargazers_count", 0),
                    })
            except Exception as e:
                logger.warning(f"GitHub search failed for query '{query}': {e}")

        # Trending scrape (unofficial) — fallback
        if not items:
            try:
                resp = client.get("https://github.com/trending/python?since=daily")
                if resp.status_code == 200:
                    trending_items = _parse_trending_html(resp.text)
                    items.extend(trending_items)
            except Exception as e:
                logger.warning(f"GitHub Trending scrape failed: {e}")

    return items


def _parse_trending_html(html):
    """Parse GitHub Trending page. Uses regex fallback since no official API."""
    items = []
    pattern = re.compile(
        r'<h2[^>]*>.*?<a[^>]*href="/([^/]+/[^"]+)"[^>]*>.*?</h2>',
        re.DOTALL,
    )
    desc_pattern = re.compile(r'<p[^>]*class="[^"]*col-9[^"]*"[^>]*>(.*?)</p>', re.DOTALL)
    star_pattern = re.compile(r'(\d+[\d,]*)\s*stars', re.IGNORECASE)

    repos = pattern.findall(html)
    descs = desc_pattern.findall(html)
    stars = star_pattern.findall(html)

    for i, repo in enumerate(repos[:15]):
        repo = repo.strip()
        if not repo:
            continue
        desc = descs[i].strip() if i < len(descs) else ""
        desc = re.sub(r'<[^>]+>', '', desc)
        star_count = stars[i].replace(",", "") if i < len(stars) else "0"

        # Filter AI-related by keyword
        ai_keywords = ["ai", "llm", "gpt", "ml", "machine-learning", "deep-learning",
                       "neural", "transformer", "diffusion", "rag", "agent", "langchain"]
        combined = (repo + " " + desc).lower()
        if not any(kw in combined for kw in ai_keywords):
            continue

        items.append({
            "title": f"{repo} ⭐{star_count}",
            "summary": desc or "No description",
            "url": f"https://github.com/{repo}",
            "source": "GitHub Trending",
            "language": "en",
            "item_type": "github",
            "stars": int(star_count) if star_count.isdigit() else 0,
        })

    return items


def collect_all(config_path="config/sources.yaml"):
    """Main entry: collect from all configured sources. Returns deduplicated list."""
    config = load_config(config_path)
    all_items = []

    # RSS feeds
    for feed_cfg in config.get("rss_feeds", []):
        items = fetch_rss_items(feed_cfg["url"], feed_cfg["name"], feed_cfg["language"])
        all_items.extend(items)
        logger.info(f"  {feed_cfg['name']}: {len(items)} items")

    # ArXiv
    arxiv_cfg = config.get("arxiv", {})
    arxiv_items = fetch_arxiv_items(
        category=arxiv_cfg.get("category", "cs.AI"),
        max_results=arxiv_cfg.get("max_results", 15),
    )
    all_items.extend(arxiv_items)
    logger.info(f"  ArXiv: {len(arxiv_items)} items")

    # GitHub
    github_cfg = config.get("github", {})
    github_token = os.environ.get("GITHUB_TOKEN")

    github_items = fetch_github_items(
        queries=github_cfg.get("search_queries", []),
        max_per_query=github_cfg.get("max_results_per_query", 10),
        github_token=github_token,
    )
    all_items.extend(github_items)
    logger.info(f"  GitHub: {len(github_items)} items")

    # Deduplicate by URL
    seen = set()
    deduped = []
    for item in all_items:
        if item["url"] not in seen:
            seen.add(item["url"])
            deduped.append(item)

    logger.info(f"Total collected: {len(deduped)} items (deduplicated from {len(all_items)})")
    return deduped
