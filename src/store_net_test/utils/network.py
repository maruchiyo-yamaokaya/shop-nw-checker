"""ネットワークユーティリティ

インターネット接続確認等のネットワーク関連ヘルパー。
Requirements: 8.1, 8.2, 8.3, 9.1, 9.2, 9.3, 10.1, 10.2, 10.3
"""

from __future__ import annotations

import ipaddress
import platform
import re
import socket
import subprocess

# RFC 1918 プライベートIPアドレス範囲
_RFC1918_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
]


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


def is_private_ip(ip_address: str) -> bool:
    """IPアドレスがRFC 1918プライベートIPアドレスかを判定する

    対象範囲:
    - 10.0.0.0/8
    - 172.16.0.0/12
    - 192.168.0.0/16

    Args:
        ip_address: 判定対象のIPアドレス文字列

    Returns:
        プライベートIPならTrue、それ以外はFalse
    """
    try:
        addr = ipaddress.ip_address(ip_address)
        return any(addr in net for net in _RFC1918_NETWORKS)
    except ValueError:
        return False


def get_default_gateway() -> str | None:
    """システムのデフォルトゲートウェイIPアドレスを取得する

    Windows: `ipconfig` コマンドの出力をパース
    macOS/Linux: `ip route` または `netstat -rn` の出力をパース

    Returns:
        デフォルトゲートウェイIPアドレス文字列。取得失敗時はNone
    """
    try:
        system = platform.system()
        if system == "Windows":
            return _get_gateway_windows()
        else:
            return _get_gateway_unix()
    except Exception:
        return None


def _get_gateway_windows() -> str | None:
    """Windows: ipconfigからデフォルトゲートウェイを取得する"""
    output = subprocess.check_output(["ipconfig"], text=True, timeout=10)
    # "Default Gateway" または "デフォルト ゲートウェイ" パターンに対応
    for line in output.splitlines():
        if "gateway" in line.lower() or "ゲートウェイ" in line:
            match = re.search(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", line)
            if match:
                return match.group(1)
    return None


def _get_gateway_unix() -> str | None:
    """macOS/Linux: ip route または netstat -rn からデフォルトゲートウェイを取得する"""
    # まず ip route を試す
    try:
        output = subprocess.check_output(
            ["ip", "route", "show", "default"], text=True, timeout=10
        )
        match = re.search(
            r"default via (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", output
        )
        if match:
            return match.group(1)
    except (FileNotFoundError, subprocess.SubprocessError):
        pass

    # フォールバック: netstat -rn
    try:
        output = subprocess.check_output(
            ["netstat", "-rn"], text=True, timeout=10
        )
        for line in output.splitlines():
            parts = line.split()
            if len(parts) >= 2 and parts[0] == "default":
                match = re.search(
                    r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", parts[1]
                )
                if match:
                    return match.group(1)
    except (FileNotFoundError, subprocess.SubprocessError):
        pass

    return None

def get_system_dns_servers() -> list[str]:
    """OSに設定されたDNSサーバーのIPアドレスリストを取得する

    macOS: `scutil --dns` の出力をパース
    Windows: `ipconfig /all` の出力をパース
    Linux: `/etc/resolv.conf` をパース

    Returns:
        DNSサーバーIPアドレスのリスト（重複排除済み）。取得失敗時は空リスト
    """
    try:
        system = platform.system()
        if system == "Darwin":
            return _get_dns_servers_macos()
        elif system == "Windows":
            return _get_dns_servers_windows()
        else:
            return _get_dns_servers_linux()
    except Exception:
        return []


def _get_dns_servers_macos() -> list[str]:
    """macOS: scutil --dns からDNSサーバーを取得する"""
    output = subprocess.check_output(
        ["scutil", "--dns"], text=True, timeout=10
    )
    servers: list[str] = []
    for line in output.splitlines():
        match = re.search(r"nameserver\[\d+\]\s*:\s*(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", line)
        if match:
            ip = match.group(1)
            if ip not in servers:
                servers.append(ip)
    return servers


def _get_dns_servers_windows() -> list[str]:
    """Windows: ipconfig /all からDNSサーバーを取得する"""
    output = subprocess.check_output(
        ["ipconfig", "/all"], text=True, timeout=10
    )
    servers: list[str] = []
    for line in output.splitlines():
        if "dns" in line.lower() or "DNS" in line:
            match = re.search(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", line)
            if match:
                ip = match.group(1)
                if ip not in servers:
                    servers.append(ip)
    return servers


def _get_dns_servers_linux() -> list[str]:
    """Linux: /etc/resolv.conf からDNSサーバーを取得する"""
    servers: list[str] = []
    try:
        with open("/etc/resolv.conf") as f:
            for line in f:
                line = line.strip()
                if line.startswith("nameserver"):
                    match = re.search(r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})", line)
                    if match:
                        ip = match.group(1)
                        if ip not in servers:
                            servers.append(ip)
    except OSError:
        pass
    return servers


def get_local_ip() -> str | None:
    """アクティブNICのローカルIPアドレスを取得する

    UDPソケットで外部ホスト(8.8.8.8:80)への接続を試み、
    バインドされたローカルIPを返す。実際のパケットは送信されない。
    取得失敗時はNoneを返し、例外を発生させない。

    Returns:
        ローカルIPアドレス文字列、または取得失敗時None
    """
    try:
        # UDPソケットでconnectし、ローカルIPを取得する
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.connect(("8.8.8.8", 80))
            local_ip = sock.getsockname()[0]
        finally:
            sock.close()
        return local_ip
    except OSError:
        return None



def is_ip_in_ranges(ip_str: str, ranges: list[str]) -> bool:
    """IPアドレスがCIDR範囲リストのいずれかに含まれるか判定する

    Python標準ライブラリのipaddressモジュールを使用。

    Args:
        ip_str: 判定対象のIPv4アドレス文字列
        ranges: CIDR表記のネットワーク範囲リスト（例: ["192.168.2.0/23", "192.168.4.0/22"]）

    Returns:
        いずれかの範囲に含まれればTrue、含まれなければFalse
    """
    try:
        addr = ipaddress.ip_address(ip_str)
    except ValueError:
        return False

    for cidr in ranges:
        try:
            network = ipaddress.ip_network(cidr, strict=False)
            if addr in network:
                return True
        except ValueError:
            continue

    return False
