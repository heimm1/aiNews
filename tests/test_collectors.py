"""Tests for collectors module."""

import httpx
from unittest.mock import patch, Mock
from src.collectors import (
    fetch_rss_items,
    fetch_arxiv_items,
    fetch_github_items,
    collect_all,
    load_config,
    _parse_trending_html,
)


SAMPLE_RSS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Blog</title>
    <item>
      <title>GPT-5 Released</title>
      <link>https://example.com/gpt5</link>
      <description>OpenAI released GPT-5 today with major improvements.</description>
      <pubDate>Mon, 23 Jun 2026 10:00:00 GMT</pubDate>
    </item>
    <item>
      <title> </title>
      <link>https://example.com/empty</link>
      <description>   </description>
    </item>
  </channel>
</rss>"""


class TestFetchRssItems:
    def test_fetches_and_parses_rss(self):
        with patch("src.collectors.httpx.Client") as mock_client:
            mock_instance = Mock()
            mock_instance.get.return_value = Mock(
                status_code=200, text=SAMPLE_RSS_XML, raise_for_status=Mock()
            )
            mock_client.return_value.__enter__.return_value = mock_instance

            items = fetch_rss_items("https://example.com/rss", "TestSource", "en")

        assert len(items) == 1  # empty title item skipped
        assert items[0]["title"] == "GPT-5 Released"
        assert items[0]["url"] == "https://example.com/gpt5"
        assert items[0]["source"] == "TestSource"
        assert items[0]["language"] == "en"
        assert items[0]["item_type"] == "news"

    def test_handles_http_error_gracefully(self):
        with patch("src.collectors.httpx.Client") as mock_client:
            mock_instance = Mock()
            mock_instance.get.side_effect = httpx.HTTPError("Connection refused")
            mock_client.return_value.__enter__.return_value = mock_instance

            items = fetch_rss_items("https://bad.example.com/rss", "Bad", "en")

        assert items == []

    def test_handles_non_200_status(self):
        with patch("src.collectors.httpx.Client") as mock_client:
            mock_instance = Mock()
            resp = Mock(status_code=404)
            resp.raise_for_status.side_effect = httpx.HTTPStatusError(
                "not found", request=Mock(), response=resp
            )
            mock_instance.get.return_value = resp
            mock_client.return_value.__enter__.return_value = mock_instance

            items = fetch_rss_items("https://example.com/rss", "Test", "en")

        assert items == []


SAMPLE_ARXIV_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>A Novel Approach to LLM Alignment</title>
    <summary>We propose a new method for aligning LLMs...</summary>
    <id>http://arxiv.org/abs/2606.12345</id>
    <published>2026-06-22T00:00:00Z</published>
  </entry>
  <entry>
    <title>  </title>
    <summary>  </summary>
    <id>http://arxiv.org/abs/2606.00000</id>
    <published>2026-06-20T00:00:00Z</published>
  </entry>
</feed>"""


class TestFetchArxivItems:
    def test_fetches_and_parses_arxiv(self):
        with patch("src.collectors.httpx.Client") as mock_client:
            mock_instance = Mock()
            mock_instance.get.return_value = Mock(
                status_code=200, text=SAMPLE_ARXIV_XML, raise_for_status=Mock()
            )
            mock_client.return_value.__enter__.return_value = mock_instance

            items = fetch_arxiv_items(category="cs.AI", max_results=10)

        assert len(items) == 1
        assert "LLM Alignment" in items[0]["title"]
        assert "arxiv.org" in items[0]["url"]
        assert items[0]["language"] == "en"
        assert items[0]["item_type"] == "news"


SAMPLE_GITHUB_SEARCH_RESPONSE = {
    "items": [
        {
            "full_name": "acme/super-ai",
            "html_url": "https://github.com/acme/super-ai",
            "description": "An amazing AI framework",
            "stargazers_count": 5432,
            "language": "Python",
            "created_at": "2026-06-20T10:00:00Z",
        },
        {
            "full_name": "foo/bar",
            "html_url": "https://github.com/foo/bar",
            "description": None,
            "stargazers_count": 10,
            "language": "Python",
            "created_at": "2026-06-20T10:00:00Z",
        },
    ]
}


class TestFetchGithubItems:
    def test_fetches_and_formats_github_results(self):
        with patch("src.collectors.httpx.Client") as mock_client:
            mock_instance = Mock()
            resp = Mock(status_code=200, json=lambda: SAMPLE_GITHUB_SEARCH_RESPONSE)
            resp.raise_for_status = Mock()
            mock_instance.get.return_value = resp
            mock_client.return_value.__enter__.return_value = mock_instance

            items = fetch_github_items(
                queries=["topic:ai"],
                max_per_query=5,
                github_token=None,
            )

        assert len(items) == 2
        assert items[0]["title"] == "acme/super-ai ⭐5432"
        assert items[0]["url"] == "https://github.com/acme/super-ai"
        assert items[0]["source"] == "GitHub Search"
        assert items[0]["language"] == "en"
        assert items[0]["item_type"] == "github"

    def test_handles_api_error(self):
        with patch("src.collectors.httpx.Client") as mock_client:
            mock_instance = Mock()
            mock_instance.get.side_effect = httpx.HTTPError("rate limited")
            mock_client.return_value.__enter__.return_value = mock_instance

            items = fetch_github_items(
                queries=["topic:ai"],
                max_per_query=5,
                github_token=None,
            )

        assert items == []


SAMPLE_TRENDING_HTML = """<html>
<body>
  <article class="Box-row">
    <h2><a href="/openai/whisper">openai/whisper</a></h2>
    <p class="col-9">Speech recognition with AI</p>
    <span>10,234 stars</span>
  </article>
  <article class="Box-row">
    <h2><a href="/john/utility-tools">john/utility-tools</a></h2>
    <p class="col-9">A collection of utility functions</p>
    <span>100 stars</span>
  </article>
</body>
</html>"""


class TestLoadConfig:
    def test_loads_valid_config(self):
        expected = {
            "rss_feeds": [{"name": "Test", "url": "http://test.com/rss", "language": "en"}],
            "arxiv": {"category": "cs.AI", "max_results": 15},
            "github": {"search_queries": ["topic:ai"]},
        }
        with patch("builtins.open") as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = "dummy"
            with patch("src.collectors.yaml.safe_load", return_value=expected):
                config = load_config("dummy.yaml")

        assert config == expected

    def test_handles_missing_file(self):
        with patch("builtins.open", side_effect=FileNotFoundError):
            config = load_config("nonexistent.yaml")

        assert config == {"rss_feeds": [], "arxiv": {}, "github": {}}

    def test_handles_malformed_yaml(self):
        import yaml

        with patch("builtins.open") as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = "bad: yaml: : : :"
            with patch("src.collectors.yaml.safe_load", side_effect=yaml.YAMLError("bad")):
                config = load_config("bad.yaml")

        assert config == {"rss_feeds": [], "arxiv": {}, "github": {}}


class TestCollectAll:
    def test_dedup_by_url(self):
        fake_config = {
            "rss_feeds": [{"name": "TestFeed", "url": "http://test.com/rss", "language": "en"}],
            "arxiv": {"category": "cs.AI", "max_results": 15},
            "github": {"search_queries": ["topic:ai"], "max_results_per_query": 5},
        }

        with patch("src.collectors.load_config", return_value=fake_config):
            with patch("src.collectors.fetch_rss_items") as mock_rss:
                mock_rss.return_value = [
                    {"title": "Same URL", "url": "https://example.com/dup", "source": "RSS"},
                ]
                with patch("src.collectors.fetch_arxiv_items") as mock_arxiv:
                    mock_arxiv.return_value = [
                        {"title": "Same URL", "url": "https://example.com/dup", "source": "ArXiv"},
                        {"title": "Unique ArXiv", "url": "https://arxiv.org/abs/9999.99999", "source": "ArXiv"},
                    ]
                    with patch("src.collectors.fetch_github_items") as mock_gh:
                        mock_gh.return_value = [
                            {"title": "Unique GH", "url": "https://github.com/foo/bar", "source": "GitHub"},
                        ]
                        items = collect_all("dummy.yaml")

        assert len(items) == 3
        urls = {item["url"] for item in items}
        assert urls == {"https://example.com/dup", "https://arxiv.org/abs/9999.99999", "https://github.com/foo/bar"}


class TestParseTrendingHtml:
    def test_parses_trending_html_and_filters_ai(self):
        items = _parse_trending_html(SAMPLE_TRENDING_HTML)

        # only "openai/whisper" matches AI keywords
        assert len(items) == 1
        assert items[0]["title"] == "openai/whisper ⭐10234"
        assert items[0]["url"] == "https://github.com/openai/whisper"
        assert items[0]["source"] == "GitHub Trending"
        assert items[0]["language"] == "en"
        assert items[0]["item_type"] == "github"
        assert items[0]["stars"] == 10234
