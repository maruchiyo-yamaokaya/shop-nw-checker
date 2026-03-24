"""Ping到達性テストモジュール

icmplibを使用したクロスプラットフォームICMP ping実装。
Requirements: 4.1, 4.3, 4.4, 9.4
"""

from __future__ import annotations

from datetime import datetime, timezone

from icmplib import ping

from ..models import PingTarget, TestResult, TestStatus, WANPath


def run_ping_test(targets: list[PingTarget], wan_path: WANPath) -> list[TestResult]:
    """Ping到達性テストを実行する

    各ターゲットホストにICMP pingを送信し、閾値に基づいてpass/failを判定する。

    Args:
        targets: Pingテスト対象のリスト
        wan_path: テスト対象のWAN経路

    Returns:
        各ターゲットに対するTestResultのリスト
    """
    results: list[TestResult] = []
    for target in targets:
        result = _ping_single(target, wan_path)
        results.append(result)
    return results


def _ping_single(target: PingTarget, wan_path: WANPath) -> TestResult:
    """単一ホストへのpingを実行する"""
    try:
        timeout_sec = target.timeout_ms / 1000.0
        host = ping(target.host, count=1, timeout=timeout_sec, privileged=False)

        if host.is_alive:
            rtt_ms = host.avg_rtt
            status = evaluate_ping_status(rtt_ms, target.timeout_ms)
            return TestResult(
                test_name=f"ping_{target.host}",
                wan_path=wan_path,
                status=status,
                timestamp=datetime.now(timezone.utc),
                details={
                    "rtt_ms": round(rtt_ms, 2),
                    "threshold_ms": target.timeout_ms,
                },
            )
        else:
            return TestResult(
                test_name=f"ping_{target.host}",
                wan_path=wan_path,
                status=TestStatus.FAIL,
                timestamp=datetime.now(timezone.utc),
                details={"threshold_ms": target.timeout_ms},
                error_message="ホストが応答しません",
            )
    except Exception as e:
        return TestResult(
            test_name=f"ping_{target.host}",
            wan_path=wan_path,
            status=TestStatus.FAIL,
            timestamp=datetime.now(timezone.utc),
            details={"threshold_ms": target.timeout_ms},
            error_message=str(e),
        )


def evaluate_ping_status(rtt_ms: float, threshold_ms: int) -> TestStatus:
    """RTTと閾値からステータスを判定する

    RTT ≤ 閾値なら"pass"、RTT > 閾値なら"fail"。

    Args:
        rtt_ms: 応答時間（ミリ秒）
        threshold_ms: 閾値（ミリ秒）

    Returns:
        判定結果のTestStatus
    """
    if rtt_ms <= threshold_ms:
        return TestStatus.PASS
    return TestStatus.FAIL
