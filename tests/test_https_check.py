"""HTTPS疎通確認テストモジュールのテスト

tests/https_check.pyのrun_https_check関数を検証する。
Requirements: 1.3, 1.4, 1.5, 1.6
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from store_net_test.models import TestStatus, WANPath
from store_net_test.tests.https_check import run_https_check


class TestRunHttpsCheck:
    """run_https_check: HTTPS疎通確認テスト"""

    # --- ステータスコード判定 ---

    def test_ステータスコード200でPASS判定(self):
        """ステータスコード200の応答を受信した場合にPASSと判定する (Req 1.3)"""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch("store_net_test.tests.https_check.httpx.get", return_value=mock_response):
            results = run_https_check(["https://example.com"], WANPath.FTTH)

        assert len(results) == 1
        assert results[0].status == TestStatus.PASS
        assert results[0].details["status_code"] == 200
        assert results[0].details["url"] == "https://example.com"
        assert results[0].error_message is None

    def test_ステータスコード404でFAIL判定(self):
        """ステータスコード404の応答を受信した場合にFAILと判定する (Req 1.4)"""
        mock_response = MagicMock()
        mock_response.status_code = 404

        with patch("store_net_test.tests.https_check.httpx.get", return_value=mock_response):
            results = run_https_check(["https://example.com"], WANPath.FTTH)

        assert len(results) == 1
        assert results[0].status == TestStatus.FAIL
        assert results[0].details["status_code"] == 404

    def test_ステータスコード500でFAIL判定(self):
        """ステータスコード500の応答を受信した場合にFAILと判定する (Req 1.4)"""
        mock_response = MagicMock()
        mock_response.status_code = 500

        with patch("store_net_test.tests.https_check.httpx.get", return_value=mock_response):
            results = run_https_check(["https://example.com"], WANPath.FTTH)

        assert len(results) == 1
        assert results[0].status == TestStatus.FAIL
        assert results[0].details["status_code"] == 500

    # --- エラーハンドリング ---

    def test_接続エラー時のFAIL判定とerror_message記録(self):
        """接続エラー発生時にFAILと判定しerror_messageを記録する (Req 1.5)"""
        with patch(
            "store_net_test.tests.https_check.httpx.get",
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            results = run_https_check(["https://example.com"], WANPath.FTTH)

        assert len(results) == 1
        assert results[0].status == TestStatus.FAIL
        assert results[0].error_message is not None
        assert "Connection refused" in results[0].error_message
        assert results[0].details["url"] == "https://example.com"

    def test_タイムアウト時のFAIL判定とerror_message記録(self):
        """タイムアウト発生時にFAILと判定しerror_messageを記録する (Req 1.5)"""
        with patch(
            "store_net_test.tests.https_check.httpx.get",
            side_effect=httpx.TimeoutException("Request timed out"),
        ):
            results = run_https_check(["https://example.com"], WANPath.FTTH)

        assert len(results) == 1
        assert results[0].status == TestStatus.FAIL
        assert results[0].error_message is not None
        assert "timed out" in results[0].error_message

    # --- 複数URL ---

    def test_複数URLに対する個別TestResult生成(self):
        """複数URLを渡した場合、各URLに対して個別のTestResultが生成される (Req 1.6)"""
        mock_response = MagicMock()
        mock_response.status_code = 200

        urls = [
            "https://www.google.com",
            "https://www.cloudflare.com",
            "https://www.amazon.co.jp",
        ]

        with patch("store_net_test.tests.https_check.httpx.get", return_value=mock_response):
            results = run_https_check(urls, WANPath.FTTH)

        assert len(results) == len(urls)
        # 各結果が対応するURLを持つことを確認
        for result, url in zip(results, urls):
            assert result.details["url"] == url
            assert result.wan_path == WANPath.FTTH
            assert result.status == TestStatus.PASS
