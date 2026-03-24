"""WhereAmI APIテストモジュール

WhereAmI APIのレスポンスJSONからshopCodeを取得し、
ウィザード入力の店舗コードと照合する。
Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import httpx

from ..models import TestResult, TestStatus, WANPath


def run_whereami_test(
    api_url: str,
    store_code: str,
    wan_path: WANPath,
) -> TestResult:
    """WhereAmI APIテストを実行する

    APIエンドポイントにGETリクエストを送信し、レスポンスJSONの
    shopCodeフィールドをstore_code（整数比較）と照合する。

    Args:
        api_url: WhereAmI APIエンドポイントURL
        store_code: ウィザード入力の店舗コード
        wan_path: テスト対象のWAN経路

    Returns:
        TestResult
    """
    test_name = "whereami_api"
    start = time.monotonic()
    try:
        response = httpx.get(api_url, timeout=10.0)
        elapsed_ms = (time.monotonic() - start) * 1000

        data = response.json()
        actual_shop_code = data["shopCode"]

        # 整数として比較（先頭ゼロの差異を吸収）
        match = int(actual_shop_code) == int(store_code)
        status = TestStatus.PASS if match else TestStatus.FAIL

        return TestResult(
            test_name=test_name,
            wan_path=wan_path,
            status=status,
            timestamp=datetime.now(timezone.utc),
            details={
                "api_url": api_url,
                "expected_store_code": store_code,
                "actual_shop_code": actual_shop_code,
                "match": match,
                "response_time_ms": round(elapsed_ms, 2),
            },
        )
    except (httpx.HTTPError, ConnectionError, TimeoutError) as e:
        # 接続エラー・タイムアウト
        elapsed_ms = (time.monotonic() - start) * 1000
        return TestResult(
            test_name=test_name,
            wan_path=wan_path,
            status=TestStatus.FAIL,
            timestamp=datetime.now(timezone.utc),
            details={
                "api_url": api_url,
                "response_time_ms": round(elapsed_ms, 2),
            },
            error_message=str(e),
        )
    except (ValueError, KeyError, TypeError) as e:
        # JSONパースエラーまたはshopCodeフィールド欠損
        elapsed_ms = (time.monotonic() - start) * 1000
        return TestResult(
            test_name=test_name,
            wan_path=wan_path,
            status=TestStatus.FAIL,
            timestamp=datetime.now(timezone.utc),
            details={
                "api_url": api_url,
                "response_time_ms": round(elapsed_ms, 2),
            },
            error_message=f"レスポンスの解析に失敗しました: {e}",
        )
