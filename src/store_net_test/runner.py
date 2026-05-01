"""テストスイート実行エンジン

プロファイルに基づきDNS・Ping・安定性テストを順次実行する。
単一のWAN経路でテストスイートを実行する。
テスト項目のシステムエラー時はスキップして次に進む。
Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6
Requirements (逆方向チェック統合): 2.1, 2.2, 2.3, 2.6, 2.7, 2.8,
    3.1, 3.2, 3.3, 3.4, 5.2, 5.3, 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7, 6.8, 6.9
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime, timezone

from rich.console import Console
from rich.table import Table

from .models import (
    PingTarget,
    ReverseCheckTarget,
    SSMProbeConfig,
    SuiteResult,
    TestProfile,
    TestResult,
    TestStatus,
    WANPath,
    WizardInput,
)
from .tests.dns import run_dns_test
from .tests.gateway_dns import run_gateway_dns_test
from .tests.https_check import run_https_check
from .tests.ping import run_ping_test
from .tests.ping_output_parser import parse_ping_output
from .tests.ssm_probe import (
    check_aws_credentials,
    check_boto3_available,
    send_ssm_ping_commands_parallel,
)
from .tests.stability import run_stability_test
from .tests.whereami import run_whereami_test
from .utils.network import get_local_ip, is_ip_in_ranges

logger = logging.getLogger(__name__)

console = Console()

# 順次テスト対象のVLAN種別リスト (Req 4.4)
VLAN_TYPES: list[str] = ["店舗", "POS", "公共"]


def evaluate_reverse_ping_status(
    packet_loss_percent: float,
    loss_threshold_percent: float,
) -> TestStatus:
    """パケットロス率と閾値からステータスを判定する

    loss <= threshold なら PASS、超過なら FAIL。

    Args:
        packet_loss_percent: 実測パケットロス率
        loss_threshold_percent: 許容パケットロス率閾値

    Returns:
        判定結果のTestStatus
    """
    if packet_loss_percent <= loss_threshold_percent:
        return TestStatus.PASS
    return TestStatus.FAIL


def _should_run_reverse_check(
    profile: TestProfile,
    vlan_type: str,
    local_ip: str | None,
) -> bool:
    """逆方向チェックの実行条件を判定する

    以下の全条件を満たす場合にTrueを返す:
    1. profile.ssm_probeが存在する
    2. 当該VLANのreverse_check_targetsが存在する
    3. local_ipがlocal_network_rangesのいずれかの範囲内にある

    条件不成立時はスキップ理由をコンソールに表示する。
    (Req 6.1, 6.2, 6.3, 6.4)

    Args:
        profile: テストプロファイル
        vlan_type: VLAN種別名
        local_ip: ローカルPCのIPアドレス

    Returns:
        実行すべきならTrue
    """
    # 条件1: ssm_probeセクションが存在するか (Req 6.2)
    if profile.ssm_probe is None:
        return False

    # 条件2: 当該VLANのreverse_check_targetsが存在するか (Req 6.1, 6.2)
    # 全VLANで共通のvlan_tests設定を使用する
    if profile.vlan_tests is None:
        return False
    if profile.vlan_tests.reverse_check_targets is None:
        return False
    if len(profile.vlan_tests.reverse_check_targets) == 0:
        return False

    # 条件3: local_ipがlocal_network_ranges内にあるか (Req 6.3, 6.4)
    if local_ip is None:
        return False
    if not is_ip_in_ranges(local_ip, profile.ssm_probe.local_network_ranges):
        console.print(
            f"  [yellow]⚠ ローカルIP ({local_ip}) は店舗LAN範囲外です。"
            f"逆方向チェックをスキップします。[/yellow]"
        )
        return False

    return True


def _expand_reverse_check_targets(
    targets: list[ReverseCheckTarget],
    local_ip: str,
    store_code: str,
    domain: str,
) -> list[tuple[ReverseCheckTarget, str]]:
    """target_kindに応じて実ターゲット文字列に展開する

    local_pc → 1個（local_ip）
    named_terminal → terminal_prefixesからホスト名を直接構築（Route 53不要）
    デフォルトのterminal_prefixesは ["rt", "sw", "prn"]

    Args:
        targets: 逆方向チェック対象リスト
        local_ip: ローカルPCのIPアドレス
        store_code: 店舗コード
        domain: ドメイン名（例: "yamaokaya.net"）

    Returns:
        (ReverseCheckTarget, 実ターゲット文字列) のタプルリスト
    """
    default_prefixes = ["rt", "sw", "prn"]
    expanded: list[tuple[ReverseCheckTarget, str]] = []
    for target in targets:
        if target.target_kind == "local_pc":
            expanded.append((target, local_ip))
        elif target.target_kind == "named_terminal":
            prefixes = target.terminal_prefixes or default_prefixes
            for prefix in prefixes:
                hostname = f"{prefix}.s{store_code}.{domain}"
                expanded.append((target, hostname))
    return expanded


def _run_reverse_check(
    config: SSMProbeConfig,
    targets: list[ReverseCheckTarget],
    store_code: str,
    local_ip: str,
    wan_path: WANPath,
) -> list[TestResult]:
    """逆方向チェックを実行する

    1. boto3利用可否・AWS認証確認
    2. terminal_prefixesからホスト名を直接構築（Route 53不要）
    3. 各ターゲットに対してSSM Send Commandを並列発行
    4. 結果をOutput_Parserで解析（ValueError時はERROR TestResult化）
    5. 閾値判定してTestResultを生成

    Args:
        config: SSMプローブ設定
        targets: 逆方向チェック対象リスト
        store_code: 店舗コード（WizardInput.store_codeから取得）
        local_ip: ローカルPCのIPアドレス
        wan_path: WAN経路

    Returns:
        TestResultのリスト
    """
    results: list[TestResult] = []

    # boto3利用可否確認 (Req 3.1, 3.2)
    if not check_boto3_available():
        console.print(
            "  [red]⚠ boto3がインストールされていません。"
            "逆方向チェックをスキップします。[/red]"
        )
        return results

    # AWS認証確認 (Req 3.3, 3.4)
    if not check_aws_credentials(config.region):
        console.print(
            "  [red]⚠ AWS認証情報が無効です。"
            "逆方向チェックをスキップします。[/red]"
        )
        return results

    # ターゲット展開（ホスト名をパターンから直接構築、Route 53不要）
    expanded = _expand_reverse_check_targets(
        targets, local_ip, store_code, config.hosted_zone_domain
    )

    if not expanded:
        return results

    # 全ターゲットのSSM Send Commandを並列発行
    console.print(
        f"    [dim]→ 逆方向ping: {len(expanded)}ターゲットを並列実行中...[/dim]"
    )

    # 並列送信用のターゲットリスト構築
    parallel_targets: list[tuple[str, int]] = [
        (actual_target, target_config.count)
        for target_config, actual_target in expanded
    ]

    try:
        # 全ターゲットを一括送信 → まとめてポーリング
        parallel_results = send_ssm_ping_commands_parallel(config, parallel_targets)

        # 結果をTestResultに変換
        for target_config, actual_target in expanded:
            ssm_results = parallel_results.get(actual_target, [])

            for ssm_result in ssm_results:
                now = datetime.now(timezone.utc)

                # TestResult名の決定 (Req 6.5)
                if target_config.target_kind == "local_pc":
                    test_name = f"reverse_ping_localpc@{ssm_result.instance_id}"
                else:
                    test_name = f"reverse_ping_{actual_target}@{ssm_result.instance_id}"

                # SSMコマンド失敗時のハンドリング
                # 注意: pingコマンドは100%パケットロス時にexit code 1を返す。
                # status=="Success"かつResponseCode!=0の場合、stdoutにping統計が
                # 含まれていればOutput_Parserで解析を試みる。
                if ssm_result.status != "Success":
                    error_msg = ssm_result.stderr or f"SSMステータス: {ssm_result.status}"
                    status = TestStatus.ERROR if ssm_result.status in (
                        "TimedOut", "DeliveryTimedOut", "ExecutionTimedOut", "Cancelled"
                    ) else TestStatus.FAIL
                    results.append(TestResult(
                        test_name=test_name,
                        wan_path=wan_path,
                        status=status,
                        timestamp=now,
                        details={
                            "probe_instance_id": ssm_result.instance_id,
                            "target": actual_target,
                            "target_kind": target_config.target_kind,
                            "ssm_status": ssm_result.status,
                            "response_code": ssm_result.response_code,
                        },
                        error_message=error_msg,
                    ))
                    continue

                # コマンド成功 → Output_Parserで解析 (Req 5.3)
                try:
                    ping_result = parse_ping_output(ssm_result.stdout)
                except ValueError as e:
                    results.append(TestResult(
                        test_name=test_name,
                        wan_path=wan_path,
                        status=TestStatus.ERROR,
                        timestamp=now,
                        details={
                            "probe_instance_id": ssm_result.instance_id,
                            "target": actual_target,
                            "target_kind": target_config.target_kind,
                            "raw_output": ssm_result.stdout[:500],
                        },
                        error_message=f"ping出力パース失敗: {e}",
                    ))
                    continue

                # 閾値判定 (Req 5.2)
                status = evaluate_reverse_ping_status(
                    ping_result.packet_loss_percent,
                    target_config.loss_threshold_percent,
                )

                results.append(TestResult(
                    test_name=test_name,
                    wan_path=wan_path,
                    status=status,
                    timestamp=now,
                    details={
                        "probe_instance_id": ssm_result.instance_id,
                        "target": actual_target,
                        "target_kind": target_config.target_kind,
                        "packets_transmitted": ping_result.packets_transmitted,
                        "packets_received": ping_result.packets_received,
                        "packet_loss_percent": ping_result.packet_loss_percent,
                        "rtt_avg_ms": ping_result.rtt_avg_ms,
                        "loss_threshold_percent": target_config.loss_threshold_percent,
                    },
                ))

    except Exception as e:
        logger.error("逆方向チェックエラー: %s", e)
        console.print(f"  [red]⚠ 逆方向チェックでエラー: {e}[/red]")

    return results


def prompt_vlan_connection(vlan_type: str) -> None:
    """VLAN接続準備プロンプトを表示し、ユーザーのEnter入力を待つ

    各VLAN種別のテスト開始前に呼び出され、ユーザーに接続切替を促す。
    (Req 4.1, 4.2, 4.3, 4.5)

    Args:
        vlan_type: VLAN種別名（「店舗」「POS」「公共」のいずれか）
    """
    console.print(
        f"\n[bold yellow]{vlan_type}VLANに接続してください。"
        f"準備ができたら[Enter]を押してください[/bold yellow]"
    )
    input()


def _run_negative_dns_test(targets: list[str], wan_path: WANPath) -> list[TestResult]:
    """ネガティブDNSテスト: 通常のDNSテスト結果のpass/failを反転する

    名前解決が失敗すればPASS、成功すればFAIL。
    公共VLANで内部NWリソースへのアクセスが遮断されていることを検証する。
    (Req 6.1, 6.2, 6.3, 6.4, 6.5)
    """
    dns_results = run_dns_test(targets, wan_path)
    inverted: list[TestResult] = []
    for r in dns_results:
        # pass/failを反転
        if r.status == TestStatus.PASS:
            new_status = TestStatus.FAIL
        elif r.status == TestStatus.FAIL:
            new_status = TestStatus.PASS
        else:
            new_status = r.status
        inverted.append(TestResult(
            test_name=f"negative_{r.test_name}",
            wan_path=r.wan_path,
            status=new_status,
            timestamp=r.timestamp,
            details=r.details,
            error_message=r.error_message,
        ))
    return inverted


def _run_tests_for_wan_path(
    profile: TestProfile,
    wan_path: WANPath,
    wizard_input: WizardInput,
    vlan_type: str,
) -> SuiteResult:
    """指定WAN経路でテストスイートを実行する

    DNS → Ping → 安定性の順で実行。各テスト項目でエラーが発生しても
    スキップして次に進む（Req 3.5）。
    各VLANテストの最後に逆方向チェックを実行する（Req 6.1）。

    Args:
        profile: テストプロファイル
        wan_path: テスト対象のWAN経路
        wizard_input: ウィザード入力結果
        vlan_type: VLAN種別名（「店舗」「POS」「公共」のいずれか）

    Returns:
        SuiteResult
    """
    results: list[TestResult] = []
    execution_ts = datetime.now(timezone.utc)

    # ローカルIPアドレスを取得・表示する (Req 1.1, 3.1, 3.2)
    local_ip = get_local_ip()
    if local_ip is not None:
        console.print(f"  [green]🌐 ローカルIP: {local_ip}[/green]")
    else:
        console.print("  [yellow]⚠ ローカルIPアドレスを取得できませんでした[/yellow]")

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

    # HTTPS疎通確認テスト（全VLAN共通追加）(Req 1.1, 8.1)
    if profile.vlan_tests is not None:
        console.print(
            f"  [cyan]▶ HTTPS疎通確認テスト[/cyan] ({wan_path.value.upper()})"
        )
        try:
            https_results = run_https_check(profile.vlan_tests.https_urls, wan_path)
            results.extend(https_results)
            _print_test_status(https_results)
        except Exception as e:
            console.print(f"  [red]⚠ HTTPS疎通確認テストでエラー: {e}[/red]")

        # VLAN種別固有テスト (Req 8.2, 8.3, 8.4, 8.5)
        if vlan_type == "店舗":
            # デフォルトゲートウェイDNS解決テスト
            console.print(
                f"  [cyan]▶ GW DNS解決テスト[/cyan] ({wan_path.value.upper()})"
            )
            try:
                gw_dns_results = run_gateway_dns_test(
                    profile.vlan_tests.store_gateway_dns_targets, wan_path
                )
                results.extend(gw_dns_results)
                _print_test_status(gw_dns_results)
            except Exception as e:
                console.print(f"  [red]⚠ GW DNS解決テストでエラー: {e}[/red]")

            # 複合機ping疎通テスト
            console.print(
                f"  [cyan]▶ 複合機ping疎通テスト[/cyan] ({wan_path.value.upper()})"
            )
            try:
                printer_target = PingTarget(
                    host=profile.vlan_tests.store_printer_host, timeout_ms=1000
                )
                printer_results = run_ping_test([printer_target], wan_path)
                results.extend(printer_results)
                _print_test_status(printer_results)
            except Exception as e:
                console.print(f"  [red]⚠ 複合機ping疎通テストでエラー: {e}[/red]")

            # WhereAmI APIテスト
            console.print(
                f"  [cyan]▶ WhereAmI APIテスト[/cyan] ({wan_path.value.upper()})"
            )
            try:
                whereami_result = run_whereami_test(
                    profile.vlan_tests.store_whereami_url,
                    wizard_input.store_code,
                    wan_path,
                )
                results.append(whereami_result)
                _print_test_status([whereami_result])
            except Exception as e:
                console.print(f"  [red]⚠ WhereAmI APIテストでエラー: {e}[/red]")

        elif vlan_type == "POS":
            # ローカル機材ping疎通テスト
            console.print(
                f"  [cyan]▶ ローカル機材ping疎通テスト[/cyan] ({wan_path.value.upper()})"
            )
            try:
                pos_targets = [
                    PingTarget(host=d.ip, timeout_ms=1000)
                    for d in profile.vlan_tests.pos_devices
                ]
                pos_results = run_ping_test(pos_targets, wan_path)
                results.extend(pos_results)
                _print_test_status(pos_results)
            except Exception as e:
                console.print(f"  [red]⚠ ローカル機材ping疎通テストでエラー: {e}[/red]")

        elif vlan_type == "公共":
            # 内部NWリソースDNS解決不可テスト（ネガティブDNS）
            console.print(
                f"  [cyan]▶ 内部NWリソースDNS解決不可テスト[/cyan] ({wan_path.value.upper()})"
            )
            try:
                neg_dns_results = _run_negative_dns_test(
                    profile.vlan_tests.public_dns_negative_targets, wan_path
                )
                results.extend(neg_dns_results)
                _print_test_status(neg_dns_results)
            except Exception as e:
                console.print(f"  [red]⚠ 内部NWリソースDNS解決不可テストでエラー: {e}[/red]")

        # 逆方向チェック（各VLANテストの最後に実行）(Req 6.1, 6.2, 6.3, 6.4)
        if _should_run_reverse_check(profile, vlan_type, local_ip):
            console.print(
                f"  [cyan]▶ 逆方向チェック[/cyan] ({wan_path.value.upper()})"
            )
            try:
                reverse_results = _run_reverse_check(
                    config=profile.ssm_probe,  # type: ignore[arg-type]
                    targets=profile.vlan_tests.reverse_check_targets,  # type: ignore[arg-type]
                    store_code=wizard_input.store_code,
                    local_ip=local_ip,  # type: ignore[arg-type]
                    wan_path=wan_path,
                )
                results.extend(reverse_results)
                _print_test_status(reverse_results)
            except Exception as e:
                logger.error("逆方向チェック全体エラー: %s", e)
                console.print(f"  [red]⚠ 逆方向チェックでエラー: {e}[/red]")

    return SuiteResult(
        store_code=wizard_input.store_code,
        vlan_type=vlan_type,
        wan_path=wan_path,
        profile_name=profile.name,
        results=results,
        execution_timestamp=execution_ts,
        local_ip=local_ip,
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
    on_vlan_complete: Callable[[SuiteResult], None] | None = None,
) -> list[SuiteResult]:
    """全VLAN種別を順次テストし、list[SuiteResult]を返す

    VLAN_TYPES の定義順（店舗 → POS → 公共）で各VLANに対して
    接続準備プロンプトを表示後、テストスイートを実行する。
    各VLANテスト完了時にon_vlan_completeコールバックを呼び出す。
    (Req 4.4, 5.1, 5.2, 5.3, 5.4)

    Args:
        profile: テストプロファイル
        wizard_input: ウィザード入力結果
        on_vlan_complete: 各VLANテスト完了時に呼ばれるコールバック（省略可）

    Returns:
        list[SuiteResult]: 各VLAN種別のテスト結果リスト（3件）
    """
    console.print()
    console.print(
        f"[bold blue]━━━ WAN経路: {wizard_input.wan_path.value.upper()} ━━━[/bold blue]"
    )

    suite_results: list[SuiteResult] = []

    # 各VLAN種別を順次テスト (Req 4.4)
    for vlan_type in VLAN_TYPES:
        prompt_vlan_connection(vlan_type)
        result = _run_tests_for_wan_path(
            profile, wizard_input.wan_path, wizard_input, vlan_type
        )
        suite_results.append(result)

        # 各VLAN完了直後にコールバック実行
        if on_vlan_complete is not None:
            on_vlan_complete(result)

    return suite_results


def display_summary(suite_results: list[SuiteResult]) -> None:
    """全VLANの結果サマリーをコンソールに表示する (Req 9.1, 9.2, 9.3)

    各SuiteResultのVLAN種別を見出しとして表示し、
    WAN経路とVLAN種別の両方をヘッダーに含める。

    Args:
        suite_results: 各VLAN種別のテストスイート結果リスト
    """
    console.print()
    console.print("[bold]━━━ テスト結果サマリー ━━━[/bold]")

    for sr in suite_results:
        console.print()

        # 総合ステータスの色分け
        status_style = {
            TestStatus.PASS: "bold green",
            TestStatus.FAIL: "bold red",
            TestStatus.WARNING: "bold yellow",
        }.get(sr.overall_status, "bold white")

        # WAN経路とVLAN種別の両方をヘッダーに含める (Req 9.1, 9.3)
        console.print(
            f"[{status_style}]【{sr.wan_path.value.upper()} / {sr.vlan_type}】"
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
