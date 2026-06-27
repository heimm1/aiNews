"""Tests for formatter module."""

import pytest
from src.formatter import format_report, split_message


CURATED = {
    "news": [
        {
            "title": "GPT-5震撼发布：性能提升10倍",
            "summary": "OpenAI今日正式发布GPT-5，在推理、编码和多模态能力上都有质的飞跃。",
            "url": "https://example.com/gpt5",
            "source": "OpenAI Blog",
        },
        {
            "title": "量子位举办AI大会",
            "summary": "量子位年度AI大会探讨了AGI发展路径。",
            "url": "https://example.com/qbitai",
            "source": "量子位",
        },
    ],
    "github_projects": [
        {
            "title": "acme/super-ai",
            "summary": "开源AI Agent框架，支持多模型协作和工具调用。",
            "url": "https://github.com/acme/super-ai",
            "stars": 5432,
        }
    ],
}


class TestFormatReport:
    def test_formats_report_with_correct_structure(self):
        result = format_report(CURATED)
        assert "AI 日报" in result
        assert "AI 行业动态" in result
        assert "GitHub 热门 AI 项目" in result
        assert "GPT-5震撼发布" in result
        assert "acme/super-ai" in result
        assert "⭐5,432" in result
        assert "https://example.com/gpt5" in result

    def test_includes_date_and_weekday(self):
        result = format_report(CURATED)
        assert "2026" in result or "日报" in result

    def test_empty_news_and_github(self):
        result = format_report({"news": [], "github_projects": []})
        assert "今日暂无" in result

    def test_only_news_no_github(self):
        result = format_report({"news": CURATED["news"], "github_projects": []})
        assert "AI 行业动态" in result
        assert "今日暂无热门AI项目" in result


class TestSplitMessage:
    def test_short_message_not_split(self):
        msg = "Hello, short message"
        parts = split_message(msg, max_chars=100)
        assert len(parts) == 1
        assert parts[0] == msg

    def test_very_long_single_section_splits_anyway(self):
        msg = "No sections here\n" + ("z" * 500)
        parts = split_message(msg, max_chars=100)
        assert len(parts) > 1
        for p in parts:
            assert len(p) <= 100
