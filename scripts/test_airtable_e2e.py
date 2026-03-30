"""Airtable Webhook E2E検証スクリプト

全48フィールドに値が入る1レコードを送信する。

使い方:
    uv run python scripts/test_airtable_e2e.py
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from store_net_test.models import SuiteResult, TestResult, TestStatus, WANPath
from store_net_test.reporters.airtable import build_airtable_record, load_webhook_config, submit_results

now = datetime.now(timezone.utc)
wan = WANPath.FTTH


def _make_full_suite() -> SuiteResult:
    """全19テスト項目を含む1レコード用SuiteResult"""
    results = [
        # 共通8項目
        TestResult(test_name="dns_www.google.com", wan_path=wan, status=TestStatus.PASS, timestamp=now,
                   details={"resolved_ips": ["142.250.196.100"], "resolution_time_ms": 25.3}),
        TestResult(test_name="dns_dns.google", wan_path=wan, status=TestStatus.PASS, timestamp=now,
                   details={"resolved_ips": ["8.8.8.8"], "resolution_time_ms": 18.1}),
        TestResult(test_name="ping_8.8.8.8", wan_path=wan, status=TestStatus.PASS, timestamp=now,
                   details={"rtt_ms": 12.5, "threshold_ms": 1000}),
        TestResult(test_name="ping_1.1.1.1", wan_path=wan, status=TestStatus.PASS, timestamp=now,
                   details={"rtt_ms": 8.3, "threshold_ms": 1000}),
        TestResult(test_name="stability_8.8.8.8", wan_path=wan, status=TestStatus.WARNING, timestamp=now,
                   details={"packet_loss_percent": 3.2, "jitter_ms": 45.0, "duration_seconds": 5, "packets_sent": 25, "packets_received": 24}),
        TestResult(test_name="https_www.google.com", wan_path=wan, status=TestStatus.PASS, timestamp=now,
                   details={"url": "https://www.google.com", "status_code": 200, "response_time_ms": 120.5}),
        TestResult(test_name="https_www.cloudflare.com", wan_path=wan, status=TestStatus.PASS, timestamp=now,
                   details={"url": "https://www.cloudflare.com", "status_code": 200, "response_time_ms": 95.2}),
        TestResult(test_name="https_www.amazon.co.jp", wan_path=wan, status=TestStatus.PASS, timestamp=now,
                   details={"url": "https://www.amazon.co.jp", "status_code": 200, "response_time_ms": 210.8}),
        # 店舗VLAN固有6項目
        TestResult(test_name="gw_dns_api.yamaokaya.net", wan_path=wan, status=TestStatus.PASS, timestamp=now,
                   details={"gateway_ip": "192.168.1.1", "hostname": "api.yamaokaya.net", "expect": "private_ip", "resolved_ips": ["10.0.0.1"], "is_private": True}),
        TestResult(test_name="gw_dns_nx.yamaokaya.net", wan_path=wan, status=TestStatus.PASS, timestamp=now,
                   details={"gateway_ip": "192.168.1.1", "hostname": "nx.yamaokaya.net", "expect": "private_ip", "resolved_ips": ["10.0.0.2"], "is_private": True}),
        TestResult(test_name="gw_dns_pornhub.com", wan_path=wan, status=TestStatus.PASS, timestamp=now,
                   details={"gateway_ip": "192.168.1.1", "hostname": "pornhub.com", "expect": "nxdomain", "resolved_ips": []}),
        TestResult(test_name="gw_dns_yamaokaya.lightning.force.com", wan_path=wan, status=TestStatus.PASS, timestamp=now,
                   details={"gateway_ip": "192.168.1.1", "hostname": "yamaokaya.lightning.force.com", "expect": "resolve_success", "resolved_ips": ["13.110.2.100"]}),
        TestResult(test_name="ping_prn.myshop.yamaokaya.net", wan_path=wan, status=TestStatus.PASS, timestamp=now,
                   details={"rtt_ms": 1.2, "threshold_ms": 1000}),
        TestResult(test_name="whereami_api", wan_path=wan, status=TestStatus.PASS, timestamp=now,
                   details={"api_url": "https://api.yamaokaya.net/wb/whereami", "expected_store_code": "9999", "actual_shop_code": "9999", "match": True, "response_time_ms": 350.0}),
        # POS VLAN固有4項目
        TestResult(test_name="ping_192.168.1.81", wan_path=wan, status=TestStatus.PASS, timestamp=now,
                   details={"rtt_ms": 0.8, "threshold_ms": 1000}),
        TestResult(test_name="ping_192.168.1.82", wan_path=wan, status=TestStatus.PASS, timestamp=now,
                   details={"rtt_ms": 0.9, "threshold_ms": 1000}),
        TestResult(test_name="ping_192.168.1.83", wan_path=wan, status=TestStatus.FAIL, timestamp=now,
                   details={"threshold_ms": 1000}, error_message="ホストが応答しません"),
        TestResult(test_name="ping_192.168.1.110", wan_path=wan, status=TestStatus.PASS, timestamp=now,
                   details={"rtt_ms": 1.1, "threshold_ms": 1000}),
        # 公共VLAN固有1項目
        TestResult(test_name="negative_dns_nx.yamaokaya.net", wan_path=wan, status=TestStatus.PASS, timestamp=now,
                   details={"resolved_ips": [], "resolution_time_ms": 50.0}),
    ]
    return SuiteResult(
        store_code="E2E_ALL_FIELDS",
        vlan_type="店舗",
        wan_path=wan,
        profile_name="standard",
        results=results,
        execution_timestamp=now,
        local_ip="192.168.1.100",
    )


async def main() -> None:
    config = load_webhook_config()
    if config is None:
        print("❌ AIRTABLE_WEBHOOK_URL が未設定です。.env を確認してください。")
        sys.exit(1)

    print(f"📡 Webhook URL: {config.webhook_url[:60]}...")

    suite = _make_full_suite()
    record = build_airtable_record(suite)

    print(f"\n📦 送信ペイロード ({len(record)} フィールド):")
    print(json.dumps(record, ensure_ascii=False, indent=2))

    print("\n🚀 Webhookに送信中...")
    count = await submit_results(config, suite, fallback_dir=Path("./results"))

    print(f"\n{'✅' if count == 1 else '❌'} 送信{'成功' if count == 1 else '失敗'}。Airtableを確認してください。")


if __name__ == "__main__":
    asyncio.run(main())
