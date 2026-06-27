"""Tests for processor module."""

import pytest
from unittest.mock import patch, Mock, MagicMock
from src.processor import build_prompt, parse_llm_response, process_items


RAW_ITEMS = [
    {"title": "GPT-5 Released", "summary": "OpenAI releases GPT-5.", "url": "https://x.com/gpt5", "source": "OpenAI Blog", "language": "en", "item_type": "news"},
    {"title": "量子位AI大会召开", "summary": "量子位举办AI大会。", "url": "https://qbitai.com/1", "source": "量子位", "language": "zh", "item_type": "news"},
    {"title": "cool-ai ⭐5000", "summary": "An AI tool.", "url": "https://github.com/x/cool-ai", "source": "GitHub Search", "language": "en", "item_type": "github", "stars": 5000},
]


class TestBuildPrompt:
    def test_includes_all_items(self):
        prompt = build_prompt(RAW_ITEMS)
        assert "GPT-5 Released" in prompt
        assert "量子位AI大会召开" in prompt
        assert "cool-ai" in prompt

    def test_includes_format_instructions(self):
        prompt = build_prompt(RAW_ITEMS)
        assert "JSON" in prompt


class TestBuildPromptEdgeCases:
    def test_empty_items_produces_valid_prompt(self):
        prompt = build_prompt([])
        assert "AI" in prompt or "JSON" in prompt
        # Should not crash

    def test_missing_fields_handled_gracefully(self):
        bad_items = [{"item_type": "news"}]  # missing title, summary, url, source
        prompt = build_prompt(bad_items)
        # Should not raise KeyError
        assert "JSON" in prompt

    def test_none_summary_handled_gracefully(self):
        items_with_none_summary = [
            {"item_type": "news", "title": "Test", "summary": None, "url": "https://example.com", "source": "Test"}
        ]
        prompt = build_prompt(items_with_none_summary)
        assert "None" not in prompt
        assert "Test" in prompt


class TestParseLlmResponse:
    def test_parses_valid_json_response(self):
        response = '''{
            "news": [
                {"title": "GPT-5震撼发布", "summary": "OpenAI发布GPT-5，性能大幅提升。", "url": "https://x.com/gpt5", "source": "OpenAI Blog"},
                {"title": "量子位AI大会召开", "summary": "量子位举办AI大会，探讨AGI未来。", "url": "https://qbitai.com/1", "source": "量子位"}
            ],
            "github_projects": [
                {"title": "cool-ai", "summary": "一个强大的AI工具。", "url": "https://github.com/x/cool-ai", "stars": 5000}
            ]
        }'''
        result = parse_llm_response(response)
        assert len(result["news"]) == 2
        assert len(result["github_projects"]) == 1
        assert result["news"][0]["summary"] == "OpenAI发布GPT-5，性能大幅提升。"

    def test_strips_markdown_fences(self):
        response = '```json\n{"news": [], "github_projects": []}\n```'
        result = parse_llm_response(response)
        assert result == {"news": [], "github_projects": []}

    def test_handles_malformed_json(self):
        response = 'not json at all'
        result = parse_llm_response(response)
        assert result == {"news": [], "github_projects": []}


class TestProcessItems:
    def test_returns_structured_result(self):
        mock_response = MagicMock()
        mock_response.content = [
            MagicMock(
                type="text",
                text='{"news": [{"title": "T", "summary": "S", "url": "U", "source": "X"}], "github_projects": [{"title": "R", "summary": "D", "url": "G", "stars": 100}]}',
            )
        ]

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}), \
             patch("src.processor.anthropic.Anthropic") as mock_anthro:
            mock_instance = Mock()
            mock_instance.messages.create.return_value = mock_response
            mock_anthro.return_value = mock_instance

            result = process_items(RAW_ITEMS, model="claude-sonnet-4-6")

        assert len(result["news"]) == 1
        assert result["news"][0]["title"] == "T"
        assert len(result["github_projects"]) == 1
        assert result["github_projects"][0]["title"] == "R"

    def test_handles_api_error(self):
        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-test"}), \
             patch("src.processor.anthropic.Anthropic") as mock_anthro:
            mock_anthro.side_effect = Exception("API key invalid")

            result = process_items(RAW_ITEMS, model="claude-sonnet-4-6")

        assert "news" in result
        assert len(result["news"]) > 0  # fallback returns raw items


class TestProcessItemsEdgeCases:
    def test_missing_api_key_returns_fallback(self):
        with patch.dict("os.environ", {}, clear=True):  # Remove ANTHROPIC_API_KEY
            from src.processor import process_items
            result = process_items(RAW_ITEMS, model="claude-sonnet-4-6")
            assert "news" in result
            assert "github_projects" in result
