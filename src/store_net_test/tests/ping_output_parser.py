"""pingコマンド出力パーサー（Parse層）

プローブ上のpingコマンド出力を構造化データに変換するParse層モジュール。
判定（Judge）は行わない。

Linux pingコマンドの標準出力フォーマット（LC_ALL=C相当）のみ対応。
プローブEC2はAmazon Linux 2 / Amazon Linux 2023のデフォルト設定に準拠。

Requirements: 5.1, 5.3, 7.1, 7.2, 7.3
"""

from __future__ import annotations

import re

from ..models import PingResult

# パケット統計行のパターン
# 例: "5 packets transmitted, 5 received, 0% packet loss, time 4005ms"
# 例: "5 packets transmitted, 0 received, 100% packet loss, time 4005ms"
_PACKET_STATS_RE = re.compile(
    r"(\d+)\s+packets\s+transmitted,\s+(\d+)\s+received"
    r"(?:,\s+\+\d+\s+errors)?"  # オプション: "+N errors"
    r",\s+(\d+(?:\.\d+)?)%\s+packet\s+loss"
)

# RTT統計行のパターン
# 例: "rtt min/avg/max/mdev = 1.234/2.345/3.456/0.567 ms"
_RTT_STATS_RE = re.compile(
    r"rtt\s+min/avg/max/mdev\s*=\s*"
    r"([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+)\s*ms"
)


def parse_ping_output(output: str) -> PingResult:
    """pingコマンド出力を構造化データに変換する

    Linux pingコマンドの標準出力フォーマットをパースする。
    例:
        5 packets transmitted, 5 received, 0% packet loss, time 4005ms
        rtt min/avg/max/mdev = 1.234/2.345/3.456/0.567 ms

    全パケットロス時はRTT統計行が出力されないため、RTTフィールドはNoneとなる。

    Args:
        output: pingコマンドの標準出力文字列

    Returns:
        PingResult

    Raises:
        ValueError: パケット統計行が見つからない場合
    """
    # パケット統計行をパース
    packet_match = _PACKET_STATS_RE.search(output)
    if not packet_match:
        raise ValueError(
            f"パケット統計行が見つかりません: {output[:200]}"
        )

    packets_transmitted = int(packet_match.group(1))
    packets_received = int(packet_match.group(2))
    packet_loss_percent = float(packet_match.group(3))

    # RTT統計行をパース（全パケットロス時は存在しない）
    rtt_match = _RTT_STATS_RE.search(output)
    if rtt_match:
        rtt_min_ms = float(rtt_match.group(1))
        rtt_avg_ms = float(rtt_match.group(2))
        rtt_max_ms = float(rtt_match.group(3))
        rtt_mdev_ms = float(rtt_match.group(4))
    else:
        rtt_min_ms = None
        rtt_avg_ms = None
        rtt_max_ms = None
        rtt_mdev_ms = None

    return PingResult(
        packets_transmitted=packets_transmitted,
        packets_received=packets_received,
        packet_loss_percent=packet_loss_percent,
        rtt_min_ms=rtt_min_ms,
        rtt_avg_ms=rtt_avg_ms,
        rtt_max_ms=rtt_max_ms,
        rtt_mdev_ms=rtt_mdev_ms,
    )


def format_ping_output(result: PingResult) -> str:
    """PingResultをpingコマンド出力形式の文字列に変換する

    parse_ping_outputの逆変換。ラウンドトリップ特性の検証に使用。
    判定フィールド（packet_loss_percent, rtt_avg_ms）がラウンドトリップで
    等価であることを保証する。

    Args:
        result: PingResult

    Returns:
        pingコマンド出力形式の文字列
    """
    # パケットロス率を整数または小数で表現
    if result.packet_loss_percent == int(result.packet_loss_percent):
        loss_str = f"{int(result.packet_loss_percent)}%"
    else:
        loss_str = f"{result.packet_loss_percent}%"

    lines = [
        f"{result.packets_transmitted} packets transmitted, "
        f"{result.packets_received} received, "
        f"{loss_str} packet loss, time 0ms"
    ]

    # RTT統計行（received > 0 かつ RTT値が存在する場合のみ）
    if result.rtt_min_ms is not None:
        lines.append(
            f"rtt min/avg/max/mdev = "
            f"{result.rtt_min_ms:.3f}/{result.rtt_avg_ms:.3f}/"
            f"{result.rtt_max_ms:.3f}/{result.rtt_mdev_ms:.3f} ms"
        )

    return "\n".join(lines)
