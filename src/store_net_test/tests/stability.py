"""安定性テストモジュール

icmplibを使用した継続的pingによるパケットロス率・ジッター計測。
Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 9.5
"""

from __future__ import annotations

from datetime import datetime, timezone

from icmplib import ping

from ..models import StabilityConfig, TestResult, TestStatus, WANPath


def run_stability_test(config: StabilityConfig, wan_path: WANPath) -> TestResult:
    """安定性テストを実行する

    指定期間にわたり継続的にpingを送信し、パケットロス率とジッターを計測する。

    Args:
        config: 安定性テスト設定
        wan_path: テスト対象のWAN経路

    Returns:
        安定性テストのTestResult
    """
    try:
        # 1秒間隔でpingを送信（duration_seconds回）
        count = max(config.duration_seconds, 2)
        host = ping(
            config.target_host,
            count=count,
            interval=1.0,
            timeout=2.0,
            privileged=False,
        )

        packets_sent = host.packets_sent
        packets_received = host.packets_received
        rtts = host.rtts

        # パケットロス率の計算
        packet_loss = calculate_packet_loss(packets_sent, packets_received)

        # ジッターの計算
        jitter = calculate_jitter(rtts)

        # 閾値判定
        status = evaluate_stability_status(
            packet_loss,
            jitter,
            config.max_packet_loss_percent,
            config.max_jitter_ms,
        )

        return TestResult(
            test_name=f"stability_{config.target_host}",
            wan_path=wan_path,
            status=status,
            timestamp=datetime.now(timezone.utc),
            details={
                "packet_loss_percent": round(packet_loss, 2),
                "jitter_ms": round(jitter, 2),
                "duration_seconds": config.duration_seconds,
                "packets_sent": packets_sent,
                "packets_received": packets_received,
            },
        )
    except Exception as e:
        return TestResult(
            test_name=f"stability_{config.target_host}",
            wan_path=wan_path,
            status=TestStatus.FAIL,
            timestamp=datetime.now(timezone.utc),
            details={"duration_seconds": config.duration_seconds},
            error_message=str(e),
        )


def calculate_packet_loss(sent: int, received: int) -> float:
    """パケットロス率を計算する

    Args:
        sent: 送信パケット数（> 0）
        received: 受信パケット数（0 ≤ received ≤ sent）

    Returns:
        パケットロス率（パーセント）
    """
    if sent <= 0:
        return 100.0
    return (sent - received) / sent * 100


def calculate_jitter(rtts: list[float]) -> float:
    """ジッターを計算する

    連続するRTT値の差の絶対値の平均を返す。

    Args:
        rtts: RTT値のリスト（ミリ秒）

    Returns:
        ジッター値（ミリ秒）。RTTが2つ未満の場合は0.0
    """
    if len(rtts) < 2:
        return 0.0
    diffs = [abs(rtts[i + 1] - rtts[i]) for i in range(len(rtts) - 1)]
    return sum(diffs) / len(diffs)


def evaluate_stability_status(
    packet_loss_percent: float,
    jitter_ms: float,
    max_packet_loss_percent: float,
    max_jitter_ms: float,
) -> TestStatus:
    """安定性テストの閾値判定を行う

    パケットロス率またはジッターが閾値を超過した場合はfail、
    両方が閾値以内であればpass。

    Args:
        packet_loss_percent: 計測されたパケットロス率
        jitter_ms: 計測されたジッター値
        max_packet_loss_percent: パケットロス率の閾値
        max_jitter_ms: ジッターの閾値

    Returns:
        判定結果のTestStatus
    """
    if packet_loss_percent > max_packet_loss_percent:
        return TestStatus.FAIL
    if jitter_ms > max_jitter_ms:
        return TestStatus.FAIL
    return TestStatus.PASS
