"""DNS解決テストモジュール

dnspythonを使用したクロスプラットフォームDNS解決テスト。
Requirements: 4.2, 4.5, 9.6
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import dns.resolver

from ..models import TestResult, TestStatus, WANPath


def run_dns_test(targets: list[str], wan_path: WANPath) -> list[TestResult]:
    """DNS解決テストを実行する

    各ターゲットホスト名に対してDNS解決を試み、結果をTestResultで返す。

    Args:
        targets: DNS解決対象のホスト名リスト
        wan_path: テスト対象のWAN経路

    Returns:
        各ターゲットに対するTestResultのリスト
    """
    results: list[TestResult] = []
    for target in targets:
        result = _resolve_single(target, wan_path)
        results.append(result)
    return results


def _resolve_single(hostname: str, wan_path: WANPath) -> TestResult:
    """単一ホスト名のDNS解決を実行する"""
    start = time.monotonic()
    try:
        answers = dns.resolver.resolve(hostname, "A")
        elapsed_ms = (time.monotonic() - start) * 1000
        resolved_ips = [rdata.address for rdata in answers]
        return TestResult(
            test_name=f"dns_{hostname}",
            wan_path=wan_path,
            status=TestStatus.PASS,
            timestamp=datetime.now(timezone.utc),
            details={
                "resolved_ips": resolved_ips,
                "resolution_time_ms": round(elapsed_ms, 2),
            },
        )
    except Exception as e:
        elapsed_ms = (time.monotonic() - start) * 1000
        return TestResult(
            test_name=f"dns_{hostname}",
            wan_path=wan_path,
            status=TestStatus.FAIL,
            timestamp=datetime.now(timezone.utc),
            details={"resolution_time_ms": round(elapsed_ms, 2)},
            error_message=str(e),
        )
