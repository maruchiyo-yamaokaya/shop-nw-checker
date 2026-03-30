"""Airtable Webhook E2E検証: 3レコード送信（店舗・POS・公共）"""

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


def _common(wan: WANPath) -> list[TestResult]:
    return [
        TestResult(test_name="dns_www.google.com", wan_path=wan, status=TestStatus.PASS, timestamp=now,
                   details={"resolved_ips": ["142.250.196.100"], "resolution_time_ms": 25.3}),
        TestResult(test_name="dns_dns.google", wan_path=wan, status=TestStatus.PASS, timestamp=now,
                   details={"resolved_ips": ["8.8.8.8"], "resolution_time_ms": 18.1}),
        TestResult(test_name="ping_8.8.8.8", wan_path=wan, status=TestStatus.PASS, timestamp=now,
                   details={"rtt_ms": 12.5, "threshold_ms": 1000}),
        TestResult(test_name="ping_1.1.1.1", wan_path=wan, status=TestStatus.PASS, timestamp=now,
                   details={"rtt_ms": 8.3, "threshold_ms": 1000}),
        TestResult(test_name="stability_8.8.8.8", wan_path=wan, status=TestStatus.PASS, timestamp=now,
                   details={"packet_loss_percent": 0.0, "jitter_ms": 2.1, "duration_seconds": 5, "packets_sent": 25, "packets_received": 25}),
        TestResult(test_name="https_www.google.com", wan_path=wan, status=TestStatus.PASS, timestamp=now,
                   details={"url": "https://www.google.com", "status_code": 200, "response_time_ms": 120.5}),
        TestResult(test_name="https_www.cloudflare.com", wan_path=wan, status=TestStatus.PASS, timestamp=now,
                   details={"url": "https://www.cloudflare.com", "status_code": 200, "response_time_ms": 95.2}),
        TestResult(test_name="https_www.amazon.co.jp", wan_path=wan, status=TestStatus.PASS, timestamp=now,
                   details={"url": "https://www.amazon.co.jp", "status_code": 200, "response_time_ms": 210.8}),
    ]


def _make_suites() -> list[SuiteResult]:
    return [
        SuiteResult(store_code="E2E_3REC", vlan_type="店舗", wan_path=wan, profile_name="standard",
            results=_common(wan) + [
                TestResult(test_name="gw_dns_api.yamaokaya.net", wan_path=wan, status=TestStatus.PASS, timestamp=now,
                           details={"gateway_ip": "192.168.1.1", "resolved_ips": ["10.0.0.1"]}),
                TestResult(test_name="gw_dns_nx.yamaokaya.net", wan_path=wan, status=TestStatus.PASS, timestamp=now,
                           details={"gateway_ip": "192.168.1.1", "resolved_ips": ["10.0.0.2"]}),
                TestResult(test_name="gw_dns_pornhub.com", wan_path=wan, status=TestStatus.PASS, timestamp=now,
                           details={"gateway_ip": "192.168.1.1", "resolved_ips": []}),
                TestResult(test_name="gw_dns_yamaokaya.lightning.force.com", wan_path=wan, status=TestStatus.PASS, timestamp=now,
                           details={"gateway_ip": "192.168.1.1", "resolved_ips": ["13.110.2.100"]}),
                TestResult(test_name="ping_prn.myshop.yamaokaya.net", wan_path=wan, status=TestStatus.PASS, timestamp=now,
                           details={"rtt_ms": 1.2, "threshold_ms": 1000}),
                TestResult(test_name="whereami_api", wan_path=wan, status=TestStatus.PASS, timestamp=now,
                           details={"expected_store_code": "9999", "actual_shop_code": "9999", "match": True, "response_time_ms": 350.0}),
            ], execution_timestamp=now, local_ip="192.168.1.100"),
        SuiteResult(store_code="E2E_3REC", vlan_type="POS", wan_path=wan, profile_name="standard",
            results=_common(wan) + [
                TestResult(test_name="ping_192.168.1.81", wan_path=wan, status=TestStatus.PASS, timestamp=now,
                           details={"rtt_ms": 0.8, "threshold_ms": 1000}),
                TestResult(test_name="ping_192.168.1.82", wan_path=wan, status=TestStatus.PASS, timestamp=now,
                           details={"rtt_ms": 0.9, "threshold_ms": 1000}),
                TestResult(test_name="ping_192.168.1.83", wan_path=wan, status=TestStatus.FAIL, timestamp=now,
                           details={"threshold_ms": 1000}, error_message="ホストが応答しません"),
                TestResult(test_name="ping_192.168.1.110", wan_path=wan, status=TestStatus.PASS, timestamp=now,
                           details={"rtt_ms": 1.1, "threshold_ms": 1000}),
            ], execution_timestamp=now, local_ip="192.168.2.50"),
        SuiteResult(store_code="E2E_3REC", vlan_type="公共", wan_path=wan, profile_name="standard",
            results=_common(wan) + [
                TestResult(test_name="negative_dns_nx.yamaokaya.net", wan_path=wan, status=TestStatus.PASS, timestamp=now,
                           details={"resolved_ips": [], "resolution_time_ms": 50.0}),
            ], execution_timestamp=now, local_ip="10.0.0.200"),
    ]


async def main() -> None:
    config = load_webhook_config()
    if config is None:
        print("❌ AIRTABLE_WEBHOOK_URL が未設定です。")
        sys.exit(1)

    suites = _make_suites()
    print(f"🚀 {len(suites)}件のレコードを送信中...")

    success = 0
    for suite in suites:
        record = build_airtable_record(suite)
        print(f"\n📦 [{suite.vlan_type}] {len(record)} フィールド")
        print(json.dumps(record, ensure_ascii=False, indent=2))
        success += await submit_results(config, suite, fallback_dir=Path("./results"))

    print(f"\n{'✅' if success == len(suites) else '⚠️'} {success}/{len(suites)} 件送信完了。")


if __name__ == "__main__":
    asyncio.run(main())
