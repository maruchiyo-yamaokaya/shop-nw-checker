"""デフォルトゲートウェイDNS解決テストモジュールのテスト

tests/gateway_dns.pyのrun_gateway_dns_testと_evaluate_resultを検証する。
Requirements: 2.4, 2.5, 2.6, 2.7, 2.8
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import dns.resolver
import pytest

from store_net_test.models import GatewayDnsTarget, TestStatus, WANPath
from store_net_test.tests.gateway_dns import _evaluate_result, run_gateway_dns_test


class TestEvaluateResult:
    """_evaluate_result: 期待値に基づく判定ロジック"""

    def test_private_ip期待でプライベートIP解決はPASS(self):
        """private_ip期待値でプライベートIPに解決された場合はPASS (Req 2.4, 2.5)"""
        status = _evaluate_result("private_ip", ["10.0.1.50"], resolved=True)
        assert status == TestStatus.PASS

    def test_private_ip期待でパブリックIP解決はFAIL(self):
        """private_ip期待値でパブリックIPに解決された場合はFAIL (Req 2.4, 2.5)"""
        status = _evaluate_result("private_ip", ["203.0.113.1"], resolved=True)
        assert status == TestStatus.FAIL

    def test_nxdomain期待で解決失敗はPASS(self):
        """nxdomain期待値でNXDOMAINが返った場合はPASS (Req 2.6)"""
        status = _evaluate_result("nxdomain", [], resolved=False, nxdomain=True)
        assert status == TestStatus.PASS

    def test_nxdomain期待で解決成功はFAIL(self):
        """nxdomain期待値で名前解決が成功した場合はFAIL (Req 2.6)"""
        status = _evaluate_result("nxdomain", ["93.184.216.34"], resolved=True)
        assert status == TestStatus.FAIL

    def test_nxdomain期待でNoAnswerはFAIL(self):
        """nxdomain期待値でNoAnswer（NXDOMAIN以外の解決失敗）はFAIL"""
        status = _evaluate_result("nxdomain", [], resolved=False, nxdomain=False)
        assert status == TestStatus.FAIL

    def test_resolve_success期待で解決成功はPASS(self):
        """resolve_success期待値で名前解決が成功した場合はPASS (Req 2.7)"""
        status = _evaluate_result("resolve_success", ["93.184.216.34"], resolved=True)
        assert status == TestStatus.PASS

    def test_resolve_success期待で解決失敗はFAIL(self):
        """resolve_success期待値で名前解決が失敗した場合はFAIL (Req 2.7)"""
        status = _evaluate_result("resolve_success", [], resolved=False)
        assert status == TestStatus.FAIL


class TestRunGatewayDnsTest:
    """run_gateway_dns_test: ゲートウェイDNS解決テスト"""

    def test_ゲートウェイ取得失敗時は全テスト項目FAIL(self):
        """ゲートウェイIP取得失敗時は全テスト項目がFAILになる (Req 2.8)"""
        targets = [
            GatewayDnsTarget(hostname="api.yamaokaya.net", expect="private_ip"),
            GatewayDnsTarget(hostname="pornhub.com", expect="nxdomain"),
        ]

        with patch(
            "store_net_test.tests.gateway_dns.get_default_gateway",
            return_value=None,
        ):
            results = run_gateway_dns_test(targets, WANPath.FTTH)

        assert len(results) == 2
        for result in results:
            assert result.status == TestStatus.FAIL
            assert result.error_message == "デフォルトゲートウェイの取得に失敗しました"
            assert result.wan_path == WANPath.FTTH

    def test_正常なDNS解決でPASS判定(self):
        """ゲートウェイDNSで正常に解決されPASS判定される (Req 2.4)"""
        targets = [
            GatewayDnsTarget(hostname="api.yamaokaya.net", expect="private_ip"),
        ]

        # モックのDNSレスポンスを構築
        mock_rdata = MagicMock()
        mock_rdata.address = "10.0.1.50"
        mock_answer = MagicMock()
        mock_answer.__iter__ = lambda self: iter([mock_rdata])

        mock_resolver = MagicMock()
        mock_resolver.resolve.return_value = mock_answer

        with patch(
            "store_net_test.tests.gateway_dns.get_default_gateway",
            return_value="192.168.1.1",
        ), patch(
            "store_net_test.tests.gateway_dns.dns.resolver.Resolver",
            return_value=mock_resolver,
        ):
            results = run_gateway_dns_test(targets, WANPath.FTTH)

        assert len(results) == 1
        assert results[0].status == TestStatus.PASS
        assert results[0].details["gateway_ip"] == "192.168.1.1"
        assert results[0].details["hostname"] == "api.yamaokaya.net"

    def test_各ターゲットに個別のTestResultが生成される(self):
        """複数ターゲットに対して各ターゲットごとに個別のTestResultが生成される (Req 2.9)"""
        targets = [
            GatewayDnsTarget(hostname="api.yamaokaya.net", expect="private_ip"),
            GatewayDnsTarget(hostname="pornhub.com", expect="nxdomain"),
            GatewayDnsTarget(
                hostname="yamaokaya.lightning.force.com", expect="resolve_success"
            ),
        ]

        # private_ip用: プライベートIPを返す
        mock_rdata_private = MagicMock()
        mock_rdata_private.address = "10.0.1.50"
        mock_answer_private = MagicMock()
        mock_answer_private.__iter__ = lambda self: iter([mock_rdata_private])

        # resolve_success用: パブリックIPを返す
        mock_rdata_public = MagicMock()
        mock_rdata_public.address = "93.184.216.34"
        mock_answer_public = MagicMock()
        mock_answer_public.__iter__ = lambda self: iter([mock_rdata_public])

        mock_resolver = MagicMock()

        def resolve_side_effect(hostname, rdtype):
            if hostname == "api.yamaokaya.net":
                return mock_answer_private
            elif hostname == "pornhub.com":
                raise dns.resolver.NXDOMAIN()
            elif hostname == "yamaokaya.lightning.force.com":
                return mock_answer_public
            raise dns.resolver.NXDOMAIN()

        mock_resolver.resolve.side_effect = resolve_side_effect

        with patch(
            "store_net_test.tests.gateway_dns.get_default_gateway",
            return_value="192.168.1.1",
        ), patch(
            "store_net_test.tests.gateway_dns.dns.resolver.Resolver",
            return_value=mock_resolver,
        ):
            results = run_gateway_dns_test(targets, WANPath.FTTH)

        assert len(results) == 3

        # api.yamaokaya.net: private_ip期待 → プライベートIP解決 → PASS
        assert results[0].test_name == "gw_dns_api.yamaokaya.net"
        assert results[0].status == TestStatus.PASS

        # pornhub.com: nxdomain期待 → 解決失敗 → PASS
        assert results[1].test_name == "gw_dns_pornhub.com"
        assert results[1].status == TestStatus.PASS

        # yamaokaya.lightning.force.com: resolve_success期待 → 解決成功 → PASS
        assert results[2].test_name == "gw_dns_yamaokaya.lightning.force.com"
        assert results[2].status == TestStatus.PASS
