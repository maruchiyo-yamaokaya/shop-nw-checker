"""ネットワークユーティリティのテスト

utils/network.pyのis_private_ip、get_default_gateway、get_local_ip関数を検証する。
Requirements: 1.1, 1.2, 9.1, 9.2, 9.3, 10.1, 10.2, 10.3
"""

from __future__ import annotations

import socket
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from store_net_test.utils.network import (
    get_default_gateway,
    get_local_ip,
    is_private_ip,
    _get_gateway_unix,
    _get_gateway_windows,
)


# --- is_private_ip テスト ---


class TestIsPrivateIp:
    """is_private_ip: RFC 1918プライベートIPアドレス判定"""

    # --- プライベートIP範囲内（True） ---

    def test_10系プライベートIPはTrue(self):
        """10.0.0.0/8 範囲"""
        assert is_private_ip("10.0.0.1") is True
        assert is_private_ip("10.255.255.255") is True
        assert is_private_ip("10.100.50.25") is True

    def test_172_16系プライベートIPはTrue(self):
        """172.16.0.0/12 範囲"""
        assert is_private_ip("172.16.0.1") is True
        assert is_private_ip("172.31.255.255") is True
        assert is_private_ip("172.20.10.5") is True

    def test_192_168系プライベートIPはTrue(self):
        """192.168.0.0/16 範囲"""
        assert is_private_ip("192.168.0.1") is True
        assert is_private_ip("192.168.255.255") is True
        assert is_private_ip("192.168.1.100") is True

    # --- パブリックIP（False） ---

    def test_パブリックIPはFalse(self):
        """RFC 1918範囲外のパブリックIP"""
        assert is_private_ip("8.8.8.8") is False
        assert is_private_ip("1.1.1.1") is False

    def test_172範囲外はFalse(self):
        """172.16-31以外の172.x.x.xはパブリック"""
        assert is_private_ip("172.15.255.255") is False
        assert is_private_ip("172.32.0.0") is False

    # --- エッジケース ---

    def test_ループバックアドレスはFalse(self):
        """127.0.0.1はRFC 1918ではないのでFalse"""
        assert is_private_ip("127.0.0.1") is False

    def test_不正な文字列はFalse(self):
        """IPアドレスとして無効な文字列"""
        assert is_private_ip("not-an-ip") is False

    def test_空文字列はFalse(self):
        assert is_private_ip("") is False


# --- get_default_gateway テスト ---


class TestGetDefaultGateway:
    """get_default_gateway: デフォルトゲートウェイIPアドレス取得"""

    # --- Windows: ipconfig パース ---

    def test_windows_ipconfigからゲートウェイを取得できる(self):
        """Windows環境のipconfig出力をパースしてゲートウェイIPを取得"""
        ipconfig_output = (
            "Windows IP Configuration\n"
            "\n"
            "Ethernet adapter Ethernet:\n"
            "\n"
            "   Connection-specific DNS Suffix  . :\n"
            "   IPv4 Address. . . . . . . . . . . : 192.168.1.100\n"
            "   Subnet Mask . . . . . . . . . . . : 255.255.255.0\n"
            "   Default Gateway . . . . . . . . . : 192.168.1.1\n"
        )
        with patch("store_net_test.utils.network.platform.system", return_value="Windows"), \
             patch("store_net_test.utils.network.subprocess.check_output", return_value=ipconfig_output):
            result = get_default_gateway()
            assert result == "192.168.1.1"

    def test_windows_日本語ipconfigからゲートウェイを取得できる(self):
        """日本語版Windowsのipconfig出力をパース"""
        ipconfig_output = (
            "Windows IP 構成\n"
            "\n"
            "イーサネット アダプター イーサネット:\n"
            "\n"
            "   IPv4 アドレス . . . . . . . . . . : 192.168.1.100\n"
            "   サブネット マスク . . . . . . . . : 255.255.255.0\n"
            "   デフォルト ゲートウェイ . . . . . : 10.0.0.1\n"
        )
        with patch("store_net_test.utils.network.platform.system", return_value="Windows"), \
             patch("store_net_test.utils.network.subprocess.check_output", return_value=ipconfig_output):
            result = get_default_gateway()
            assert result == "10.0.0.1"

    # --- Unix: ip route / netstat パース ---

    def test_unix_ip_routeからゲートウェイを取得できる(self):
        """Linux環境のip route出力をパース"""
        ip_route_output = "default via 192.168.1.1 dev eth0 proto dhcp metric 100\n"
        with patch("store_net_test.utils.network.platform.system", return_value="Linux"), \
             patch("store_net_test.utils.network.subprocess.check_output", return_value=ip_route_output):
            result = get_default_gateway()
            assert result == "192.168.1.1"

    def test_unix_netstatフォールバックでゲートウェイを取得できる(self):
        """ip routeが失敗した場合にnetstat -rnにフォールバック"""
        netstat_output = (
            "Routing tables\n"
            "\n"
            "Internet:\n"
            "Destination        Gateway            Flags\n"
            "default            10.0.0.1           UGSc\n"
            "10.0.0.0/24        link#4             UCS\n"
        )

        def mock_check_output(cmd, **kwargs):
            if cmd[0] == "ip":
                raise FileNotFoundError("ip command not found")
            return netstat_output

        with patch("store_net_test.utils.network.platform.system", return_value="Darwin"), \
             patch("store_net_test.utils.network.subprocess.check_output", side_effect=mock_check_output):
            result = get_default_gateway()
            assert result == "10.0.0.1"

    # --- コマンド失敗時 ---

    def test_コマンド失敗時はNoneを返す(self):
        """subprocessが例外を投げた場合はNoneを返す"""
        with patch("store_net_test.utils.network.platform.system", return_value="Linux"), \
             patch("store_net_test.utils.network.subprocess.check_output",
                   side_effect=subprocess.SubprocessError("command failed")):
            result = get_default_gateway()
            assert result is None

    def test_windows_コマンド失敗時はNoneを返す(self):
        """Windows環境でipconfigが失敗した場合"""
        with patch("store_net_test.utils.network.platform.system", return_value="Windows"), \
             patch("store_net_test.utils.network.subprocess.check_output",
                   side_effect=subprocess.SubprocessError("ipconfig failed")):
            result = get_default_gateway()
            assert result is None

    def test_ゲートウェイ行がない場合はNoneを返す(self):
        """ipconfig出力にゲートウェイ行がない場合"""
        ipconfig_output = (
            "Windows IP Configuration\n"
            "\n"
            "Ethernet adapter Ethernet:\n"
            "   IPv4 Address. . . . . . . . . . . : 192.168.1.100\n"
        )
        with patch("store_net_test.utils.network.platform.system", return_value="Windows"), \
             patch("store_net_test.utils.network.subprocess.check_output", return_value=ipconfig_output):
            result = get_default_gateway()
            assert result is None


# --- get_local_ip テスト ---


class TestGetLocalIp:
    """get_local_ip: アクティブNICのローカルIPアドレス取得
    Requirements: 1.1, 1.2
    """

    def test_ソケット正常時に有効なIPv4文字列を返す(self):
        """UDPソケットが正常に接続できた場合、有効なIPv4アドレスを返す"""
        mock_sock = MagicMock()
        mock_sock.getsockname.return_value = ("192.168.1.100", 0)

        with patch("store_net_test.utils.network.socket.socket", return_value=mock_sock):
            result = get_local_ip()

        assert result == "192.168.1.100"
        # UDPソケット(SOCK_DGRAM)で作成されていることを確認
        from store_net_test.utils.network import socket as net_socket
        # connect先が8.8.8.8:80であることを確認
        mock_sock.connect.assert_called_once_with(("8.8.8.8", 80))
        mock_sock.getsockname.assert_called_once()
        mock_sock.close.assert_called_once()

    def test_ソケットエラー時にNoneを返す(self):
        """ソケット操作でOSErrorが発生した場合、Noneを返し例外を発生させない"""
        mock_sock = MagicMock()
        mock_sock.connect.side_effect = OSError("Network is unreachable")

        with patch("store_net_test.utils.network.socket.socket", return_value=mock_sock):
            result = get_local_ip()

        assert result is None

    def test_ソケット作成失敗時にNoneを返す(self):
        """socket.socket()自体が失敗した場合もNoneを返す"""
        with patch("store_net_test.utils.network.socket.socket", side_effect=OSError("Cannot create socket")):
            result = get_local_ip()

        assert result is None
