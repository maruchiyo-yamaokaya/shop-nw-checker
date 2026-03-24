"""ネットワークユーティリティ

インターネット接続確認等のネットワーク関連ヘルパー。
Requirements: 8.1, 8.2, 8.3
"""

from __future__ import annotations

import socket


def check_internet_connectivity(
    host: str = "8.8.8.8",
    port: int = 53,
    timeout_seconds: float = 5.0,
) -> bool:
    """インターネット接続を確認する

    Google Public DNSへのTCP接続を試みて判定する。

    Args:
        host: 接続先ホスト
        port: 接続先ポート（DNS=53）
        timeout_seconds: タイムアウト秒数

    Returns:
        接続可能ならTrue、不可ならFalse
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout_seconds)
        sock.connect((host, port))
        sock.close()
        return True
    except OSError:
        return False
