"""HTTPS疎通確認テストモジュール

httpxを使用したHTTPS疎通確認テスト。
Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import httpx

from ..models import TestResult, TestStatus, WANPath


def run_https_check(urls: list[str], wan_path: WANPath) -> list[TestResult]:
    """HTTPS疎通確認テストを実行する

    各URLにHTTPS GETリクエストを送信し、ステータスコード200の応答を確認する。

    Args:
        urls: テスト対象URLリスト
        wan_path: テスト対象のWAN経路

    Returns:
        各URLに対するTestResultのリスト
    """
    results: list[TestResult] = []
    for url in urls:
        result = _check_single(url, wan_path)
        results.append(result)
    return results


def _check_single(url: str, wan_path: WANPath) -> TestResult:
    """単一URLのHTTPS疎通確認を実行する"""
    # テスト名: URLからスキーム部分を除去
    test_name = f"https_{url.replace('https://', '').replace('http://', '')}"
    start = time.monotonic()
    try:
        response = httpx.get(url, timeout=10.0, follow_redirects=True)
        elapsed_ms = (time.monotonic() - start) * 1000
        status = TestStatus.PASS if response.status_code == 200 else TestStatus.FAIL
        return TestResult(
            test_name=test_name,
            wan_path=wan_path,
            status=status,
            timestamp=datetime.now(timezone.utc),
            details={
                "url": url,
                "status_code": response.status_code,
                "response_time_ms": round(elapsed_ms, 2),
            },
        )
    except Exception as e:
        elapsed_ms = (time.monotonic() - start) * 1000
        return TestResult(
            test_name=test_name,
            wan_path=wan_path,
            status=TestStatus.FAIL,
            timestamp=datetime.now(timezone.utc),
            details={
                "url": url,
                "response_time_ms": round(elapsed_ms, 2),
            },
            error_message=str(e),
        )
