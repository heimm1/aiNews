"""Tests for notifier module."""

import pytest
import httpx
from unittest.mock import Mock, patch

from src.notifier import send_markdown, send_report


class TestSendMarkdown:
    def test_sends_markdown_message(self):
        with patch("src.notifier.httpx.Client") as mock_client:
            mock_instance = Mock()
            mock_instance.post.return_value = Mock(
                status_code=200,
                json=lambda: {"errcode": 0, "errmsg": "ok"},
                raise_for_status=Mock(),
            )
            mock_client.return_value.__enter__.return_value = mock_instance

            result = send_markdown("Hello World", webhook_url="https://example.com/webhook")

        assert result is True
        mock_instance.post.assert_called_once()

    def test_handles_wecom_error_response(self):
        with patch("src.notifier.httpx.Client") as mock_client:
            mock_instance = Mock()
            mock_instance.post.return_value = Mock(
                status_code=200,
                json=lambda: {"errcode": 40001, "errmsg": "invalid url"},
                raise_for_status=Mock(),
            )
            mock_client.return_value.__enter__.return_value = mock_instance

            result = send_markdown("Hello", webhook_url="https://example.com/webhook")

        assert result is False

    def test_handles_network_error(self):
        with patch("src.notifier.httpx.Client") as mock_client:
            mock_instance = Mock()
            mock_instance.post.side_effect = httpx.HTTPError("timeout")
            mock_client.return_value.__enter__.return_value = mock_instance

            result = send_markdown("Hello", webhook_url="https://example.com/webhook")

        assert result is False

    def test_no_webhook_url_returns_false(self):
        result = send_markdown("Hello", webhook_url="")
        assert result is False


class TestSendReport:
    def test_sends_and_splits_long_report(self):
        with patch("src.notifier.send_markdown") as mock_send:
            mock_send.return_value = True

            result = send_report("short message", webhook_url="https://example.com/webhook")

        assert result is True
        mock_send.assert_called()

    def test_sends_multiple_parts(self):
        with patch("src.notifier.send_markdown") as mock_send:
            mock_send.return_value = True

            long_msg = "x" * 5000
            result = send_report(long_msg, webhook_url="https://example.com/webhook")

        assert result is True
        assert mock_send.call_count >= 2
