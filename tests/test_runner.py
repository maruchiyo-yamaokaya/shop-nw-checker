"""Runnerモジュールのテスト

runner.pyの_run_negative_dns_testと_run_tests_for_wan_pathを検証する。
Requirements: 8.1, 8.2, 8.3, 8.4, 8.5
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from store_net_test.models import (
    GatewayDnsTarget,
    PingTarget,
    PosDevice,
    StabilityConfig,
    TestProfile,
    TestResult,
    TestStatus,
    VlanTestConfig,
    WANPath,
    WizardInput,
)
from store_net_test.runner import _run_negative_dns_test, _run_tests_for_wan_path


# --- ヘルパー関数 ---


def _make_vlan_test_config() -> VlanTestConfig:
    return VlanTestConfig(
        https_urls=["https://www.google.com"],
        store_gateway_dns_targets=[
            GatewayDnsTarget(hostname="api.yamaokaya.net", expect="private_ip"),
        ],
        store_printer_host="prn.myshop.yamaokaya.net",
        store_whereami_url="https://api.yamaokaya.net/wb/whereami",
        pos_devices=[PosDevice(name="券売機1", ip="192.168.1.81")],
        public_dns_negative_targets=["nx.yamaokaya.net"],
    )


def _make_profile(vlan_tests: VlanTestConfig | None = None) -> TestProfile:
    return TestProfile(
        name="test",
        description="test",
        ping_targets=[PingTarget(host="8.8.8.8", timeout_ms=1000)],
        dns_targets=["www.google.com"],
        stability=StabilityConfig(
            target_host="8.8.8.8",
            duration_seconds=30,
            max_packet_loss_percent=5.0,
            max_jitter_ms=50.0,
        ),
        vlan_tests=vlan_tests,
    )


def _make_test_result(
    test_name: str = "test", status: TestStatus = TestStatus.PASS
) -> TestResult:
    return TestResult(
        test_name=test_name,
        wan_path=WANPath.FTTH,
        status=status,
        timestamp=datetime.now(timezone.utc),
    )


# --- _run_negative_dns_test テスト ---


class TestRunNegativeDnsTest:
    """_run_negative_dns_test: ネガティブDNSテストのpass/fail反転ロジック"""

    @patch("store_net_test.runner.run_dns_test")
    def test_PASSがFAILに反転される(self, mock_dns: MagicMock) -> None:
        """通常DNSテストでPASS（解決成功）の結果がFAILに反転される (Req 6.3, 6.4)"""
        mock_dns.return_value = [_make_test_result("dns_nx.yamaokaya.net", TestStatus.PASS)]

        results = _run_negative_dns_test(["nx.yamaokaya.net"], WANPath.FTTH)

        assert len(results) == 1
        assert results[0].status == TestStatus.FAIL

    @patch("store_net_test.runner.run_dns_test")
    def test_FAILがPASSに反転される(self, mock_dns: MagicMock) -> None:
        """通常DNSテストでFAIL（解決失敗）の結果がPASSに反転される (Req 6.3, 6.4)"""
        mock_dns.return_value = [_make_test_result("dns_nx.yamaokaya.net", TestStatus.FAIL)]

        results = _run_negative_dns_test(["nx.yamaokaya.net"], WANPath.FTTH)

        assert len(results) == 1
        assert results[0].status == TestStatus.PASS

    @patch("store_net_test.runner.run_dns_test")
    def test_テスト名にnegativeプレフィックスが付与される(self, mock_dns: MagicMock) -> None:
        """反転後のテスト名に"negative_"プレフィックスが付与される (Req 6.1)"""
        mock_dns.return_value = [_make_test_result("dns_nx.yamaokaya.net", TestStatus.FAIL)]

        results = _run_negative_dns_test(["nx.yamaokaya.net"], WANPath.FTTH)

        assert len(results) == 1
        assert results[0].test_name == "negative_dns_nx.yamaokaya.net"


# --- _run_tests_for_wan_path テスト ---


class TestRunTestsForWanPath:
    """_run_tests_for_wan_path: VLAN種別に応じたテスト実行フロー"""

    @patch("store_net_test.runner.get_local_ip", return_value="192.168.1.100")
    @patch("store_net_test.runner.console", new_callable=MagicMock)
    @patch("store_net_test.runner.run_whereami_test")
    @patch("store_net_test.runner.run_ping_test")
    @patch("store_net_test.runner.run_gateway_dns_test")
    @patch("store_net_test.runner.run_https_check")
    @patch("store_net_test.runner.run_stability_test")
    @patch("store_net_test.runner.run_dns_test")
    def test_店舗VLANで固有テスト3種が実行される(
        self,
        mock_dns: MagicMock,
        mock_stability: MagicMock,
        mock_https: MagicMock,
        mock_gw_dns: MagicMock,
        mock_ping: MagicMock,
        mock_whereami: MagicMock,
        mock_console: MagicMock,
        mock_get_local_ip: MagicMock,
    ) -> None:
        """店舗VLANではGW DNS、複合機ping、WhereAmIの3種が実行される (Req 8.2)"""
        profile = _make_profile(_make_vlan_test_config())
        wizard = WizardInput(store_code="0001", wan_path=WANPath.FTTH)

        # 共通テストのモック
        mock_dns.return_value = [_make_test_result("dns_test")]
        mock_ping.return_value = [_make_test_result("ping_test")]
        mock_stability.return_value = _make_test_result("stability_test")
        mock_https.return_value = [_make_test_result("https_test")]

        # 店舗VLAN固有テストのモック
        mock_gw_dns.return_value = [_make_test_result("gw_dns_test")]
        mock_whereami.return_value = _make_test_result("whereami_test")

        result = _run_tests_for_wan_path(profile, WANPath.FTTH, wizard, "店舗")

        # GW DNSテストが呼ばれたことを確認
        mock_gw_dns.assert_called_once_with(
            profile.vlan_tests.store_gateway_dns_targets, WANPath.FTTH
        )
        # 複合機pingテストが呼ばれたことを確認（run_ping_testは共通+複合機で2回呼ばれる）
        assert mock_ping.call_count == 2
        # WhereAmIテストが呼ばれたことを確認
        mock_whereami.assert_called_once_with(
            profile.vlan_tests.store_whereami_url, "0001", WANPath.FTTH
        )

    @patch("store_net_test.runner.get_local_ip", return_value="192.168.1.100")
    @patch("store_net_test.runner.console", new_callable=MagicMock)
    @patch("store_net_test.runner.run_ping_test")
    @patch("store_net_test.runner.run_https_check")
    @patch("store_net_test.runner.run_stability_test")
    @patch("store_net_test.runner.run_dns_test")
    def test_POS_VLANでローカル機材pingが実行される(
        self,
        mock_dns: MagicMock,
        mock_stability: MagicMock,
        mock_https: MagicMock,
        mock_ping: MagicMock,
        mock_console: MagicMock,
        mock_get_local_ip: MagicMock,
    ) -> None:
        """POS VLANではローカル機材（PosDevice）へのpingが実行される (Req 8.3)"""
        profile = _make_profile(_make_vlan_test_config())
        wizard = WizardInput(store_code="0001", wan_path=WANPath.FTTH)

        mock_dns.return_value = [_make_test_result("dns_test")]
        mock_ping.return_value = [_make_test_result("ping_test")]
        mock_stability.return_value = _make_test_result("stability_test")
        mock_https.return_value = [_make_test_result("https_test")]

        result = _run_tests_for_wan_path(profile, WANPath.FTTH, wizard, "POS")

        # run_ping_testは共通ping + POS機材pingで2回呼ばれる
        assert mock_ping.call_count == 2
        # 2回目の呼び出しがPOS機材のIPアドレスであることを確認
        pos_call_args = mock_ping.call_args_list[1]
        pos_targets = pos_call_args[0][0]
        assert len(pos_targets) == 1
        assert pos_targets[0].host == "192.168.1.81"

    @patch("store_net_test.runner.get_local_ip", return_value="192.168.1.100")
    @patch("store_net_test.runner.console", new_callable=MagicMock)
    @patch("store_net_test.runner.run_dns_test")
    @patch("store_net_test.runner.run_ping_test")
    @patch("store_net_test.runner.run_https_check")
    @patch("store_net_test.runner.run_stability_test")
    def test_公共VLANでネガティブDNSが実行される(
        self,
        mock_stability: MagicMock,
        mock_https: MagicMock,
        mock_ping: MagicMock,
        mock_dns: MagicMock,
        mock_console: MagicMock,
        mock_get_local_ip: MagicMock,
    ) -> None:
        """公共VLANではネガティブDNSテスト（結果反転）が実行される (Req 8.4)"""
        profile = _make_profile(_make_vlan_test_config())
        wizard = WizardInput(store_code="0001", wan_path=WANPath.FTTH)

        # 共通テスト用のモック（1回目のrun_dns_test呼び出し）
        # ネガティブDNS用のモック（2回目のrun_dns_test呼び出し）
        mock_dns.side_effect = [
            [_make_test_result("dns_www.google.com", TestStatus.PASS)],  # 共通DNS
            [_make_test_result("dns_nx.yamaokaya.net", TestStatus.PASS)],  # ネガティブDNS元結果
        ]
        mock_ping.return_value = [_make_test_result("ping_test")]
        mock_stability.return_value = _make_test_result("stability_test")
        mock_https.return_value = [_make_test_result("https_test")]

        result = _run_tests_for_wan_path(profile, WANPath.FTTH, wizard, "公共")

        # run_dns_testが2回呼ばれる（共通DNS + ネガティブDNS）
        assert mock_dns.call_count == 2
        # ネガティブDNSの結果が反転されていることを確認
        neg_results = [r for r in result.results if r.test_name.startswith("negative_")]
        assert len(neg_results) == 1
        # 元がPASSなのでFAILに反転される
        assert neg_results[0].status == TestStatus.FAIL

    @patch("store_net_test.runner.get_local_ip", return_value="192.168.1.100")
    @patch("store_net_test.runner.console", new_callable=MagicMock)
    @patch("store_net_test.runner.run_https_check")
    @patch("store_net_test.runner.run_stability_test")
    @patch("store_net_test.runner.run_ping_test")
    @patch("store_net_test.runner.run_dns_test")
    def test_vlan_testsがNoneの場合にVLAN固有テストがスキップされる(
        self,
        mock_dns: MagicMock,
        mock_ping: MagicMock,
        mock_stability: MagicMock,
        mock_https: MagicMock,
        mock_console: MagicMock,
        mock_get_local_ip: MagicMock,
    ) -> None:
        """vlan_tests=Noneの場合、HTTPS・VLAN固有テストは実行されない"""
        profile = _make_profile(vlan_tests=None)
        wizard = WizardInput(store_code="0001", wan_path=WANPath.FTTH)

        mock_dns.return_value = [_make_test_result("dns_test")]
        mock_ping.return_value = [_make_test_result("ping_test")]
        mock_stability.return_value = _make_test_result("stability_test")

        result = _run_tests_for_wan_path(profile, WANPath.FTTH, wizard, "店舗")

        # HTTPS疎通確認テストは呼ばれない
        mock_https.assert_not_called()
        # 共通テストのみ実行される
        assert len(result.results) == 3

    @patch("store_net_test.runner.get_local_ip", return_value="192.168.1.100")
    @patch("store_net_test.runner.console", new_callable=MagicMock)
    @patch("store_net_test.runner.run_whereami_test")
    @patch("store_net_test.runner.run_ping_test")
    @patch("store_net_test.runner.run_gateway_dns_test")
    @patch("store_net_test.runner.run_https_check")
    @patch("store_net_test.runner.run_stability_test")
    @patch("store_net_test.runner.run_dns_test")
    def test_VLAN固有テストでエラー発生時にスキップして次に進む(
        self,
        mock_dns: MagicMock,
        mock_stability: MagicMock,
        mock_https: MagicMock,
        mock_gw_dns: MagicMock,
        mock_ping: MagicMock,
        mock_whereami: MagicMock,
        mock_console: MagicMock,
        mock_get_local_ip: MagicMock,
    ) -> None:
        """VLAN固有テストの1つでエラーが発生しても、残りのテストは実行される (Req 8.5)"""
        profile = _make_profile(_make_vlan_test_config())
        wizard = WizardInput(store_code="0001", wan_path=WANPath.FTTH)

        # 共通テストのモック
        mock_dns.return_value = [_make_test_result("dns_test")]
        mock_ping.return_value = [_make_test_result("ping_test")]
        mock_stability.return_value = _make_test_result("stability_test")
        mock_https.return_value = [_make_test_result("https_test")]

        # GW DNSテストでエラーを発生させる
        mock_gw_dns.side_effect = Exception("GW DNS error")
        # WhereAmIテストは正常に動作する
        mock_whereami.return_value = _make_test_result("whereami_test")

        result = _run_tests_for_wan_path(profile, WANPath.FTTH, wizard, "店舗")

        # GW DNSがエラーでも、複合機pingとWhereAmIは実行される
        assert mock_ping.call_count == 2  # 共通ping + 複合機ping
        mock_whereami.assert_called_once()


# --- IP取得・表示・格納テスト ---


class TestRunTestsForWanPathLocalIp:
    """_run_tests_for_wan_path: ローカルIP取得・表示・格納ロジック (Req 1.1, 3.1, 3.2)"""

    @patch("store_net_test.runner.get_local_ip", return_value="192.168.1.100")
    @patch("store_net_test.runner.console", new_callable=MagicMock)
    @patch("store_net_test.runner.run_stability_test")
    @patch("store_net_test.runner.run_ping_test")
    @patch("store_net_test.runner.run_dns_test")
    def test_get_local_ipが呼ばれ結果がSuiteResultに格納される(
        self,
        mock_dns: MagicMock,
        mock_ping: MagicMock,
        mock_stability: MagicMock,
        mock_console: MagicMock,
        mock_get_local_ip: MagicMock,
    ) -> None:
        """get_local_ipが呼ばれ、戻り値がSuiteResult.local_ipに格納される (Req 1.1, 2.1)"""
        profile = _make_profile(vlan_tests=None)
        wizard = WizardInput(store_code="0001", wan_path=WANPath.FTTH)

        mock_dns.return_value = [_make_test_result("dns_test")]
        mock_ping.return_value = [_make_test_result("ping_test")]
        mock_stability.return_value = _make_test_result("stability_test")

        result = _run_tests_for_wan_path(profile, WANPath.FTTH, wizard, "店舗")

        # get_local_ipが1回呼ばれること
        mock_get_local_ip.assert_called_once()
        # SuiteResult.local_ipに格納されること
        assert result.local_ip == "192.168.1.100"

    @patch("store_net_test.runner.get_local_ip", return_value="10.0.0.5")
    @patch("store_net_test.runner.console", new_callable=MagicMock)
    @patch("store_net_test.runner.run_stability_test")
    @patch("store_net_test.runner.run_ping_test")
    @patch("store_net_test.runner.run_dns_test")
    def test_IP取得成功時にコンソール表示される(
        self,
        mock_dns: MagicMock,
        mock_ping: MagicMock,
        mock_stability: MagicMock,
        mock_console: MagicMock,
        mock_get_local_ip: MagicMock,
    ) -> None:
        """IP取得成功時にIPアドレスがコンソールに表示される (Req 3.1)"""
        profile = _make_profile(vlan_tests=None)
        wizard = WizardInput(store_code="0001", wan_path=WANPath.FTTH)

        mock_dns.return_value = [_make_test_result("dns_test")]
        mock_ping.return_value = [_make_test_result("ping_test")]
        mock_stability.return_value = _make_test_result("stability_test")

        _run_tests_for_wan_path(profile, WANPath.FTTH, wizard, "店舗")

        # コンソールにIPアドレスが表示されたことを確認
        print_calls = [str(c) for c in mock_console.print.call_args_list]
        ip_displayed = any("10.0.0.5" in call for call in print_calls)
        assert ip_displayed, "IP取得成功時にIPアドレスがコンソールに表示されるべき"

    @patch("store_net_test.runner.get_local_ip", return_value=None)
    @patch("store_net_test.runner.console", new_callable=MagicMock)
    @patch("store_net_test.runner.run_stability_test")
    @patch("store_net_test.runner.run_ping_test")
    @patch("store_net_test.runner.run_dns_test")
    def test_IP取得失敗時に警告メッセージが表示される(
        self,
        mock_dns: MagicMock,
        mock_ping: MagicMock,
        mock_stability: MagicMock,
        mock_console: MagicMock,
        mock_get_local_ip: MagicMock,
    ) -> None:
        """IP取得失敗（None）時に警告メッセージが表示される (Req 3.2)"""
        profile = _make_profile(vlan_tests=None)
        wizard = WizardInput(store_code="0001", wan_path=WANPath.FTTH)

        mock_dns.return_value = [_make_test_result("dns_test")]
        mock_ping.return_value = [_make_test_result("ping_test")]
        mock_stability.return_value = _make_test_result("stability_test")

        result = _run_tests_for_wan_path(profile, WANPath.FTTH, wizard, "店舗")

        # SuiteResult.local_ipがNoneであること
        assert result.local_ip is None
        # 警告メッセージがコンソールに表示されたことを確認
        print_calls = [str(c) for c in mock_console.print.call_args_list]
        warning_displayed = any("取得できませんでした" in call for call in print_calls)
        assert warning_displayed, "IP取得失敗時に警告メッセージが表示されるべき"
