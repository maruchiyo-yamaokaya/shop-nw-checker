"""テストスイート実行エンジン

プロファイルに基づきDNS・Ping・安定性テストを順次実行する。
単一のWAN経路でテストスイートを実行する。
テスト項目のシステムエラー時はスキップして次に進む。
Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6
"""

from __future__ import annotations

from datetime import datetime, timezone

from rich.console import Console
from rich.table import Table

from .models import (
    SuiteResult,
    TestProfile,
    TestResult,
    TestStatus,
    WizardInput,
)
from .tests.dns import run_dns_test
from .tests.ping import run_ping_test
from .tests.stability import run_stability_test

console = Console()


def _run_tests_for_wan_path(
    profile: TestProfile,
    wan_path: WANPath,
    wizard_input: WizardInput,
) -> SuiteResult:
    """指定WAN経路でテストスイートを実行する

    DNS → Ping → 安定性の順で実行。各テスト項目でエラーが発生しても
    スキップして次に進む（Req 3.5）。

    Args:
        profile: テストプロファイル
        wan_path: テスト対象のWAN経路
        wizard_input: ウィザード入力結果

    Returns:
        SuiteResult
    """
    results: list[TestResult] = []
    execution_ts = datetime.now(timezone.utc)

    # DNS解決テスト (Req 4.2)
    console.print(
        f"  [cyan]▶ DNS解決テスト[/cyan] ({wan_path.value.upper()})"
    )
    try:
        dns_results = run_dns_test(profile.dns_targets, wan_path)
        results.extend(dns_results)
        _print_test_status(dns_results)
    except Exception as e:
        console.print(f"  [red]⚠ DNS解決テストでエラー: {e}[/red]")

    # Ping到達性テスト (Req 4.1)
    console.print(
        f"  [cyan]▶ Ping到達性テスト[/cyan] ({wan_path.value.upper()})"
    )
    try:
        ping_results = run_ping_test(profile.ping_targets, wan_path)
        results.extend(ping_results)
        _print_test_status(ping_results)
    except Exception as e:
        console.print(f"  [red]⚠ Ping到達性テストでエラー: {e}[/red]")

    # 安定性テスト (Req 5.1)
    console.print(
        f"  [cyan]▶ 安定性テスト[/cyan] ({wan_path.value.upper()})"
    )
    try:
        stability_result = run_stability_test(profile.stability, wan_path)
        results.append(stability_result)
        _print_test_status([stability_result])
    except Exception as e:
        console.print(f"  [red]⚠ 安定性テストでエラー: {e}[/red]")

    return SuiteResult(
        store_code=wizard_input.store_code,
        vlan_type=wizard_input.vlan_type,
        wan_path=wan_path,
        profile_name=profile.name,
        results=results,
        execution_timestamp=execution_ts,
    )


def _print_test_status(results: list[TestResult]) -> None:
    """テスト結果のステータスを簡易表示する"""
    for r in results:
        icon = {
            TestStatus.PASS: "[green]✓[/green]",
            TestStatus.FAIL: "[red]✗[/red]",
            TestStatus.WARNING: "[yellow]⚠[/yellow]",
            TestStatus.ERROR: "[red]⚠[/red]",
        }.get(r.status, "?")
        console.print(f"    {icon} {r.test_name}: {r.status.value}")


def run_test_suite(
    profile: TestProfile,
    wizard_input: WizardInput,
) -> SuiteResult:
    """テストスイートを実行する

    単一のWAN経路でテストスイートを実行する。

    Args:
        profile: テストプロファイル
        wizard_input: ウィザード入力結果

    Returns:
        SuiteResult
    """
    console.print()
    console.print(
        f"[bold blue]━━━ WAN経路: {wizard_input.wan_path.value.upper()} ━━━[/bold blue]"
    )

    return _run_tests_for_wan_path(profile, wizard_input.wan_path, wizard_input)


def display_summary(suite_result: SuiteResult) -> None:
    """結果サマリーをコンソールに表示する (Req 3.6)

    Args:
        suite_result: テストスイート結果
    """
    console.print()
    console.print("[bold]━━━ テスト結果サマリー ━━━[/bold]")
    console.print()

    sr = suite_result

    # 総合ステータスの色分け
    status_style = {
        TestStatus.PASS: "bold green",
        TestStatus.FAIL: "bold red",
        TestStatus.WARNING: "bold yellow",
    }.get(sr.overall_status, "bold white")

    console.print(
        f"[{status_style}]【{sr.wan_path.value.upper()}】"
        f" 総合: {sr.overall_status.value.upper()}[/{status_style}]"
    )

    # ステータス別カウント
    summary = sr.summary
    parts = []
    for status in [TestStatus.PASS, TestStatus.FAIL, TestStatus.WARNING, TestStatus.ERROR]:
        count = summary.get(status, 0)
        if count > 0:
            parts.append(f"{status.value}: {count}")
    console.print(f"  {' / '.join(parts)}")

    # 個別結果テーブル
    table = Table(show_header=True, box=None, padding=(0, 1))
    table.add_column("テスト名", style="cyan")
    table.add_column("ステータス")
    table.add_column("詳細")

    for r in sr.results:
        status_text = {
            TestStatus.PASS: "[green]PASS[/green]",
            TestStatus.FAIL: "[red]FAIL[/red]",
            TestStatus.WARNING: "[yellow]WARN[/yellow]",
            TestStatus.ERROR: "[red]ERROR[/red]",
        }.get(r.status, r.status.value)

        detail = r.error_message or _format_details(r.details)
        table.add_row(r.test_name, status_text, detail)

    console.print(table)
    console.print()


def _format_details(details: dict) -> str:
    """テスト詳細を簡潔な文字列にフォーマットする"""
    parts = []
    if "rtt_ms" in details:
        parts.append(f"RTT: {details['rtt_ms']}ms")
    if "resolution_time_ms" in details:
        parts.append(f"解決時間: {details['resolution_time_ms']}ms")
    if "packet_loss_percent" in details:
        parts.append(f"ロス: {details['packet_loss_percent']}%")
    if "jitter_ms" in details:
        parts.append(f"ジッター: {details['jitter_ms']}ms")
    return ", ".join(parts) if parts else "-"
