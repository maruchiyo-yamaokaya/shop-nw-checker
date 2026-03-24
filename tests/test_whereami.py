"""WhereAmI APIテストモジュールのテスト

tests/whereami.pyのrun_whereami_test関数を検証する。
Requirements: 4.3, 4.4, 4.5, 4.6
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from store_net_test.models import TestStatus, WANPath
from store_net_test.tests.whereami import run_whereami_test

API_URL = "https://api.yamaokaya.net/wb/whereami"


class TestRunWhereamiTest:
    """run_whereami_test: WhereAmI APIテスト"""

    # --- shopCode照合 ---

    def test_shopCode一致でPASS判定(self):
        """shopCodeがstore_codeと整数一致する場合にPASSと判定する (Req 4.3, 4.4)"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"shopCode": 1}

        with patch(
            "store_net_test.tests.whereami.httpx.get",
            return_value=mock_response,
        ):
            result = run_whereami_test(API_URL, "0001", WANPath.FTTH)

        assert result.status == TestStatus.PASS
        assert result.test_name == "whereami_api"
        assert result.wan_path == WANPath.FTTH
        assert result.details["expected_store_code"] == "0001"
        assert result.details["actual_shop_code"] == 1
        assert result.details["match"] is True
        assert result.error_message is None

    def test_shopCode不一致でFAIL判定(self):
        """shopCodeがstore_codeと不一致の場合にFAILと判定し、期待値・実際値を記録する (Req 4.5)"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"shopCode": 2}

        with patch(
            "store_net_test.tests.whereami.httpx.get",
            return_value=mock_response,
        ):
            result = run_whereami_test(API_URL, "0001", WANPath.FTTH)

        assert result.status == TestStatus.FAIL
        assert result.details["expected_store_code"] == "0001"
        assert result.details["actual_shop_code"] == 2
        assert result.details["match"] is False

    # --- エラーハンドリング ---

    def test_接続エラー時のFAIL判定とerror_message記録(self):
        """接続エラー発生時にFAILと判定しerror_messageを記録する (Req 4.6)"""
        with patch(
            "store_net_test.tests.whereami.httpx.get",
            side_effect=httpx.ConnectError("Connection refused"),
        ):
            result = run_whereami_test(API_URL, "0001", WANPath.FTTH)

        assert result.status == TestStatus.FAIL
        assert result.error_message is not None
        assert "Connection refused" in result.error_message
        assert result.details["api_url"] == API_URL

    def test_JSONパースエラー時のFAIL判定(self):
        """レスポンスJSONのパースに失敗した場合にFAILと判定する (Req 4.6)"""
        mock_response = MagicMock()
        mock_response.json.side_effect = ValueError("Invalid JSON")

        with patch(
            "store_net_test.tests.whereami.httpx.get",
            return_value=mock_response,
        ):
            result = run_whereami_test(API_URL, "0001", WANPath.FTTH)

        assert result.status == TestStatus.FAIL
        assert result.error_message is not None
        assert "レスポンスの解析に失敗しました" in result.error_message

    def test_shopCodeフィールド欠損時のFAIL判定(self):
        """レスポンスJSONにshopCodeフィールドがない場合にFAILと判定する (Req 4.6)"""
        mock_response = MagicMock()
        mock_response.json.return_value = {"otherField": "value"}

        with patch(
            "store_net_test.tests.whereami.httpx.get",
            return_value=mock_response,
        ):
            result = run_whereami_test(API_URL, "0001", WANPath.FTTH)

        assert result.status == TestStatus.FAIL
        assert result.error_message is not None
        assert "レスポンスの解析に失敗しました" in result.error_message
