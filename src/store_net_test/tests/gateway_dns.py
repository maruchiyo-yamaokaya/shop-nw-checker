"""デフォルトゲートウェイDNS解決テストモジュール

デフォルトゲートウェイIPをDNSサーバーとして使用し、
内部ドメインの名前解決結果を検証する。
Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import dns.resolver

from ..models import GatewayDnsTarget, TestResult, TestStatus, WANPath
from ..utils.network import get_default_gateway, is_private_ip


def run_gateway_dns_test(
    targets: list[GatewayDnsTarget],
    wan_path: WANPath,
) -> list[TestResult]:
    """デフォルトゲートウェイDNS解決テストを実行する

    システムのデフォルトゲートウェイIPをDNSサーバーとして使用し、
    各ホスト名の解決結果を期待値と照合する。

    Args:
        targets: テスト対象ホスト名と期待結果のリスト（TestProfileから取得）
        wan_path: テスト対象のWAN経路

    Returns:
        各ホスト名に対するTestResultのリスト
    """
    gateway_ip = get_default_gateway()

    # ゲートウェイ取得失敗時は全テスト項目をFAIL
    if gateway_ip is None:
        return [
            TestResult(
                test_name=f"gw_dns_{t.hostname}",
                wan_path=wan_path,
                status=TestStatus.FAIL,
                timestamp=datetime.now(timezone.utc),
                details={"hostname": t.hostname, "expect": t.expect},
                error_message="デフォルトゲートウェイの取得に失敗しました",
            )
            for t in targets
        ]

    results: list[TestResult] = []
    for target in targets:
        result = _resolve_single(target, gateway_ip, wan_path)
        results.append(result)
    return results


def _resolve_single(
    target: GatewayDnsTarget, gateway_ip: str, wan_path: WANPath
) -> TestResult:
    """単一ホスト名のゲートウェイDNS解決を実行する"""
    test_name = f"gw_dns_{target.hostname}"
    start = time.monotonic()

    # ゲートウェイIPをDNSサーバーとして指定
    resolver = dns.resolver.Resolver()
    resolver.nameservers = [gateway_ip]
    resolver.lifetime = 10.0

    try:
        answers = resolver.resolve(target.hostname, "A")
        elapsed_ms = (time.monotonic() - start) * 1000
        resolved_ips = [rdata.address for rdata in answers]

        # 期待値に基づく判定
        status = _evaluate_result(target.expect, resolved_ips, resolved=True)

        return TestResult(
            test_name=test_name,
            wan_path=wan_path,
            status=status,
            timestamp=datetime.now(timezone.utc),
            details={
                "gateway_ip": gateway_ip,
                "hostname": target.hostname,
                "expect": target.expect,
                "resolved_ips": resolved_ips,
                "is_private": any(is_private_ip(ip) for ip in resolved_ips),
            },
        )
    except dns.resolver.NXDOMAIN:
        elapsed_ms = (time.monotonic() - start) * 1000
        # NXDOMAINのみ「名前解決ブロック」として扱う
        status = _evaluate_result(target.expect, [], resolved=False, nxdomain=True)
        return TestResult(
            test_name=test_name,
            wan_path=wan_path,
            status=status,
            timestamp=datetime.now(timezone.utc),
            details={
                "gateway_ip": gateway_ip,
                "hostname": target.hostname,
                "expect": target.expect,
                "resolved_ips": [],
                "reason": "NXDOMAIN",
            },
        )
    except (
        dns.resolver.NoAnswer,
        dns.resolver.NoNameservers,
    ) as e:
        elapsed_ms = (time.monotonic() - start) * 1000
        # NoAnswer/NoNameserversは「解決できなかった」だが「ブロック」とは限らない
        status = _evaluate_result(target.expect, [], resolved=False, nxdomain=False)
        return TestResult(
            test_name=test_name,
            wan_path=wan_path,
            status=status,
            timestamp=datetime.now(timezone.utc),
            details={
                "gateway_ip": gateway_ip,
                "hostname": target.hostname,
                "expect": target.expect,
                "resolved_ips": [],
                "reason": type(e).__name__,
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
                "gateway_ip": gateway_ip,
                "hostname": target.hostname,
                "expect": target.expect,
                "reason": type(e).__name__,
            },
            error_message=str(e),
        )


def _evaluate_result(
    expect: str,
    resolved_ips: list[str],
    resolved: bool,
    nxdomain: bool = False,
) -> TestStatus:
    """期待値に基づいてテスト結果を判定する

    Args:
        expect: 期待値 ("private_ip" | "nxdomain" | "resolve_success")
        resolved_ips: 解決されたIPアドレスリスト
        resolved: 名前解決が成功したかどうか
        nxdomain: NXDOMAIN応答だったかどうか（NoAnswer等と区別するため）
    """
    if expect == "private_ip":
        # 解決成功かつプライベートIPならPASS
        if resolved and any(is_private_ip(ip) for ip in resolved_ips):
            return TestStatus.PASS
        return TestStatus.FAIL
    elif expect == "nxdomain":
        # NXDOMAINが返った場合のみPASS（NoAnswer/NoNameserversはFAIL）
        return TestStatus.PASS if nxdomain else TestStatus.FAIL
    elif expect == "resolve_success":
        # 名前解決成功ならPASS
        return TestStatus.PASS if resolved else TestStatus.FAIL
    else:
        return TestStatus.FAIL
