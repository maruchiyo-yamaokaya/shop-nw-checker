#!/usr/bin/env python3
"""SSMプローブ逆方向チェック 実地テストスクリプト

全体フローを段階的に確認する:
1. boto3利用可否
2. AWS認証確認
3. Route 53 Hosted Zone ID解決
4. Route 53 店舗レコード取得
5. SSM Send Command発行 + 結果取得
6. ping出力パース + 閾値判定

使い方:
    uv run python scripts/test_ssm_probe_e2e.py --store-code 1234
    uv run python scripts/test_ssm_probe_e2e.py --store-code 1234 --target 192.168.2.100
    uv run python scripts/test_ssm_probe_e2e.py --store-code 1234 --step 3  # ステップ3まで実行
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def _send_ssm_direct(config, target: str, count: int, instance_id: str) -> list:
    """インスタンスID直接指定でSSM Send Commandを実行する（タグ同期待ち回避用）"""
    import boto3
    import time
    from store_net_test.tests.ssm_probe import build_ping_command, validate_ping_target, _poll_command_result
    from store_net_test.models import SSMCommandResult

    if not validate_ping_target(target):
        return [SSMCommandResult(
            instance_id="unknown", status="Failed", response_code=-1,
            stdout="", stderr=f"無効なpingターゲット: {target}",
        )]

    command = build_ping_command(target, count)
    ssm = boto3.client("ssm", region_name=config.region)

    try:
        response = ssm.send_command(
            InstanceIds=[instance_id],
            DocumentName=config.document_name,
            Parameters={"commands": [command]},
            TimeoutSeconds=config.timeout_seconds,
        )
        command_id = response["Command"]["CommandId"]
        console.print(f"    CommandId: {command_id}")

        time.sleep(1.5)

        result = _poll_command_result(
            ssm=ssm,
            command_id=command_id,
            instance_id=instance_id,
            timeout_seconds=config.timeout_seconds,
            start_time=time.monotonic() - 1.5,
            region=config.region,
        )
        return [result]

    except Exception as e:
        return [SSMCommandResult(
            instance_id=instance_id, status="Failed", response_code=-1,
            stdout="", stderr=str(e),
        )]


def step_1_check_boto3() -> bool:
    """ステップ1: boto3利用可否確認"""
    console.print("\n[bold cyan]━━━ Step 1: boto3利用可否確認 ━━━[/bold cyan]")
    from store_net_test.tests.ssm_probe import check_boto3_available

    available = check_boto3_available()
    if available:
        import boto3
        console.print(f"  [green]✓ boto3 利用可能 (version: {boto3.__version__})[/green]")
    else:
        console.print("  [red]✗ boto3 が見つかりません[/red]")
        console.print("  [dim]  → uv pip install boto3 でインストールしてください[/dim]")
    return available


def step_2_check_credentials(region: str) -> bool:
    """ステップ2: AWS認証確認"""
    console.print("\n[bold cyan]━━━ Step 2: AWS認証確認 ━━━[/bold cyan]")
    from store_net_test.tests.ssm_probe import check_aws_credentials

    valid = check_aws_credentials(region)
    if valid:
        import boto3
        sts = boto3.client("sts", region_name=region)
        identity = sts.get_caller_identity()
        console.print(f"  [green]✓ AWS認証有効[/green]")
        console.print(f"    Account: {identity['Account']}")
        console.print(f"    ARN: {identity['Arn']}")
        console.print(f"    Region: {region}")
    else:
        console.print("  [red]✗ AWS認証情報が無効です[/red]")
        console.print("  [dim]  → aws configure または環境変数を確認してください[/dim]")
    return valid


def step_3_resolve_hosted_zone(
    hosted_zone_domain: str,
    hosted_zone_id: str | None,
    region: str,
) -> str | None:
    """ステップ3: Route 53 Hosted Zone ID解決"""
    console.print("\n[bold cyan]━━━ Step 3: Route 53 Hosted Zone ID解決 ━━━[/bold cyan]")
    from store_net_test.tests.ssm_probe import resolve_hosted_zone_id

    zone_id = resolve_hosted_zone_id(hosted_zone_domain, hosted_zone_id, region)
    if zone_id:
        console.print(f"  [green]✓ Hosted Zone ID: {zone_id}[/green]")
        console.print(f"    Domain: {hosted_zone_domain}")
    else:
        console.print(f"  [red]✗ Hosted Zone IDを解決できませんでした[/red]")
        console.print(f"    Domain: {hosted_zone_domain}")
        console.print("  [dim]  → ドメイン名が正しいか、Route 53にHosted Zoneが存在するか確認してください[/dim]")
    return zone_id


def step_4_list_store_records(
    hosted_zone_id: str,
    store_code: str,
    hosted_zone_domain: str,
    region: str,
) -> list[str]:
    """ステップ4: Route 53 店舗レコード取得"""
    console.print("\n[bold cyan]━━━ Step 4: Route 53 店舗レコード取得 ━━━[/bold cyan]")
    from store_net_test.tests.ssm_probe import list_store_dns_records

    records = list_store_dns_records(hosted_zone_id, store_code, hosted_zone_domain, region)
    if records:
        console.print(f"  [green]✓ {len(records)}件のレコードを取得[/green]")
        for r in records:
            console.print(f"    • {r}")
    else:
        console.print(f"  [yellow]⚠ レコードが見つかりませんでした[/yellow]")
        console.print(f"    パターン: *.s{store_code}.{hosted_zone_domain}")
        console.print("  [dim]  → 店舗コードが正しいか確認してください[/dim]")
    return records


def step_5_send_ssm_command(
    config,
    target: str,
    count: int = 5,
    instance_id: str | None = None,
) -> list:
    """ステップ5: SSM Send Command発行"""
    console.print("\n[bold cyan]━━━ Step 5: SSM Send Command発行 ━━━[/bold cyan]")
    console.print(f"  ターゲット: {target}")
    console.print(f"  ping回数: {count}")
    if instance_id:
        console.print(f"  インスタンスID（直接指定）: {instance_id}")
    else:
        console.print(f"  タグ: {config.target_tag_key}={config.target_tag_value}")
    console.print(f"  タイムアウト: {config.timeout_seconds}秒")
    console.print()

    from store_net_test.tests.ssm_probe import send_ssm_ping_command, validate_ping_target, build_ping_command

    # インスタンスID直接指定モード
    if instance_id:
        console.print("  [dim]SSM Send Command送信中（InstanceId直接指定）...[/dim]")
        results = _send_ssm_direct(config, target, count, instance_id)
    else:
        console.print("  [dim]SSM Send Command送信中...[/dim]")
        results = send_ssm_ping_command(config, target, count)

    if not results:
        console.print("  [red]✗ 結果が返りませんでした[/red]")
        return results

    for r in results:
        if r.status == "Success" and r.response_code == 0:
            console.print(f"  [green]✓ Instance: {r.instance_id} → Success (RC=0)[/green]")
        elif r.status == "Success":
            console.print(f"  [yellow]⚠ Instance: {r.instance_id} → Success (RC={r.response_code})[/yellow]")
        else:
            console.print(f"  [red]✗ Instance: {r.instance_id} → {r.status}[/red]")

        if r.stdout:
            console.print(f"    [dim]stdout ({len(r.stdout)} chars):[/dim]")
            # 最後の数行だけ表示
            lines = r.stdout.strip().split("\n")
            for line in lines[-5:]:
                console.print(f"      {line}")
        if r.stderr:
            console.print(f"    [red]stderr: {r.stderr[:200]}[/red]")

    return results


def step_6_parse_and_judge(results: list, loss_threshold: float = 20.0) -> None:
    """ステップ6: ping出力パース + 閾値判定"""
    console.print("\n[bold cyan]━━━ Step 6: ping出力パース + 閾値判定 ━━━[/bold cyan]")
    from store_net_test.tests.ping_output_parser import parse_ping_output
    from store_net_test.runner import evaluate_reverse_ping_status
    from store_net_test.models import TestStatus

    table = Table(title="逆方向チェック結果")
    table.add_column("Instance ID", style="cyan")
    table.add_column("Loss %")
    table.add_column("RTT avg (ms)")
    table.add_column("判定")

    for r in results:
        if r.status != "Success":
            table.add_row(
                r.instance_id,
                "-",
                "-",
                f"[red]SKIP ({r.status})[/red]",
            )
            continue

        # status=="Success"ならResponseCodeに関わらずパースを試みる
        # （pingは100%ロス時にexit code 1を返すため）
        try:
            ping_result = parse_ping_output(r.stdout)
            status = evaluate_reverse_ping_status(
                ping_result.packet_loss_percent, loss_threshold
            )

            loss_str = f"{ping_result.packet_loss_percent:.1f}%"
            rtt_str = f"{ping_result.rtt_avg_ms:.3f}" if ping_result.rtt_avg_ms else "-"

            if status == TestStatus.PASS:
                judge_str = f"[green]PASS[/green] (閾値: {loss_threshold}%)"
            else:
                judge_str = f"[red]FAIL[/red] (閾値: {loss_threshold}%)"

            table.add_row(r.instance_id, loss_str, rtt_str, judge_str)

        except ValueError as e:
            table.add_row(
                r.instance_id,
                "-",
                "-",
                f"[red]PARSE ERROR: {e}[/red]",
            )

    console.print(table)


def main():
    parser = argparse.ArgumentParser(
        description="SSMプローブ逆方向チェック 実地テスト"
    )
    parser.add_argument(
        "--store-code", required=True,
        help="テスト対象の店舗コード（例: 1234）"
    )
    parser.add_argument(
        "--target",
        help="直接指定するpingターゲット（省略時はローカルIPを使用）"
    )
    parser.add_argument(
        "--region", default="ap-northeast-1",
        help="AWSリージョン（デフォルト: ap-northeast-1）"
    )
    parser.add_argument(
        "--domain", default="yamaokaya.net",
        help="Hosted Zoneドメイン（デフォルト: yamaokaya.net）"
    )
    parser.add_argument(
        "--tag-key", default="NetCheckProbe",
        help="プローブ特定タグキー（デフォルト: NetCheckProbe）"
    )
    parser.add_argument(
        "--tag-value", default="true",
        help="プローブ特定タグ値（デフォルト: true）"
    )
    parser.add_argument(
        "--count", type=int, default=5,
        help="ping回数（デフォルト: 5）"
    )
    parser.add_argument(
        "--instance-id",
        help="プローブインスタンスIDを直接指定（タグ同期待ち回避用）"
    )
    parser.add_argument(
        "--timeout", type=int, default=60,
        help="SSMタイムアウト秒数（デフォルト: 60）"
    )
    parser.add_argument(
        "--loss-threshold", type=float, default=20.0,
        help="パケットロス閾値%%（デフォルト: 20.0）"
    )
    parser.add_argument(
        "--terminals", default="rt,sw,prn",
        help="チェック対象の端末プレフィックス（カンマ区切り、デフォルト: rt,sw,prn）"
    )

    args = parser.parse_args()

    console.print(Panel(
        f"[bold]SSMプローブ逆方向チェック 実地テスト[/bold]\n"
        f"店舗コード: {args.store_code} / リージョン: {args.region}\n"
        f"ドメイン: {args.domain} / 端末: {args.terminals}",
        title="🔍 E2E Test",
    ))

    # Step 1: boto3
    if not step_1_check_boto3():
        sys.exit(1)

    # Step 2: AWS認証
    if not step_2_check_credentials(args.region):
        sys.exit(1)

    # pingターゲットの決定
    if args.target:
        ping_target = args.target
        console.print(f"\n  [dim]pingターゲット（直接指定）: {ping_target}[/dim]")
    else:
        # ローカルIPを使用
        from store_net_test.utils.network import get_local_ip
        local_ip = get_local_ip()
        if local_ip:
            ping_target = local_ip
            console.print(f"\n  [dim]pingターゲット（ローカルIP）: {ping_target}[/dim]")
        else:
            console.print("\n  [red]ローカルIPを取得できませんでした。--target で指定してください。[/red]")
            sys.exit(1)

    # Step 5+6: 全ターゲット並列実行 + 結果テーブル表示
    from store_net_test.models import SSMProbeConfig
    from store_net_test.tests.ssm_probe import send_ssm_ping_commands_parallel
    from store_net_test.tests.ping_output_parser import parse_ping_output
    from store_net_test.runner import evaluate_reverse_ping_status
    from store_net_test.models import TestStatus

    config = SSMProbeConfig(
        region=args.region,
        timeout_seconds=args.timeout,
        hosted_zone_domain=args.domain,
        local_network_ranges=[
            "192.168.2.0/23", "192.168.4.0/22", "192.168.8.0/21",
            "192.168.16.0/20", "192.168.32.0/19", "192.168.64.0/18",
            "192.168.128.0/17",
        ],
        target_tag_key=args.tag_key,
        target_tag_value=args.tag_value,
    )

    # 全ターゲットリスト構築（ローカルPC + 名前付き端末）
    # 端末ホスト名はパターンから直接構築（Route 53不要）
    terminal_prefixes = args.terminals.split(",") if args.terminals else ["rt", "sw", "prn"]

    all_targets: list[tuple[str, str]] = []  # (表示名, ターゲット)
    all_targets.append(("local_pc", ping_target))
    for prefix in terminal_prefixes:
        hostname = f"{prefix}.s{args.store_code}.{args.domain}"
        all_targets.append((hostname, hostname))

    console.print(f"\n[bold cyan]━━━ Step 5: 逆方向ping 並列実行 ({len(all_targets)}ターゲット) ━━━[/bold cyan]")
    for display_name, target in all_targets:
        console.print(f"    [dim]• {display_name} → {target}[/dim]")

    # インスタンスID直接指定モードの場合は独自の並列実行
    if args.instance_id:
        console.print(f"\n  [dim]InstanceId直接指定モード: {args.instance_id}[/dim]")
        console.print(f"  [dim]全{len(all_targets)}ターゲットを一括送信中...[/dim]")
        parallel_results = _send_parallel_direct(
            config, [(t, args.count) for _, t in all_targets], args.instance_id
        )
    else:
        console.print(f"\n  [dim]全{len(all_targets)}ターゲットを一括送信中...[/dim]")
        parallel_targets = [(target, args.count) for _, target in all_targets]
        parallel_results = send_ssm_ping_commands_parallel(config, parallel_targets)

    # Step 6: 結果テーブル表示
    console.print(f"\n[bold cyan]━━━ Step 6: 結果サマリー ━━━[/bold cyan]")

    table = Table(title=f"逆方向チェック結果 (store: {args.store_code})")
    table.add_column("ホスト名", style="cyan")
    table.add_column("ターゲット", style="dim")
    table.add_column("Loss %", justify="right")
    table.add_column("RTT avg (ms)", justify="right")
    table.add_column("判定")

    pass_count = 0
    fail_count = 0
    error_count = 0

    for display_name, target in all_targets:
        ssm_results = parallel_results.get(target, [])
        if not ssm_results:
            table.add_row(display_name, target, "-", "-", "[red]NO RESULT[/red]")
            error_count += 1
            continue

        for r in ssm_results:
            if r.status != "Success":
                table.add_row(
                    display_name, target, "-", "-",
                    f"[red]ERROR ({r.status})[/red]",
                )
                error_count += 1
                continue

            try:
                ping_result = parse_ping_output(r.stdout)
                status = evaluate_reverse_ping_status(
                    ping_result.packet_loss_percent, args.loss_threshold
                )

                loss_str = f"{ping_result.packet_loss_percent:.1f}%"
                rtt_str = f"{ping_result.rtt_avg_ms:.2f}" if ping_result.rtt_avg_ms else "-"

                if status == TestStatus.PASS:
                    judge_str = "[green]PASS[/green]"
                    pass_count += 1
                else:
                    judge_str = "[red]FAIL[/red]"
                    fail_count += 1

                table.add_row(display_name, target, loss_str, rtt_str, judge_str)

            except ValueError as e:
                table.add_row(
                    display_name, target, "-", "-",
                    f"[red]PARSE ERROR[/red]",
                )
                error_count += 1

    console.print(table)
    console.print(
        f"\n  [bold]合計: [green]PASS={pass_count}[/green] / "
        f"[red]FAIL={fail_count}[/red] / ERROR={error_count}[/bold]"
        f"  (閾値: {args.loss_threshold}%)"
    )
    console.print("\n[bold green]━━━ 実地テスト完了 ━━━[/bold green]")


def _send_parallel_direct(config, targets: list[tuple[str, int]], instance_id: str) -> dict:
    """インスタンスID直接指定での並列送信（タグ同期待ち回避用）
    
    Phase 1（send_command）もPhase 2（ポーリング）も全て並列実行する。
    """
    import boto3
    import time
    from concurrent.futures import ThreadPoolExecutor, as_completed
    from store_net_test.tests.ssm_probe import (
        build_ping_command, validate_ping_target, _poll_command_result,
        _INITIAL_WAIT_SECONDS,
    )
    from store_net_test.models import SSMCommandResult

    results: dict[str, list] = {}

    # バリデーション
    valid_targets: list[tuple[str, int]] = []
    for target, count in targets:
        if not validate_ping_target(target):
            results[target] = [SSMCommandResult(
                instance_id="unknown", status="Failed", response_code=-1,
                stdout="", stderr=f"無効なpingターゲット: {target}",
            )]
        else:
            valid_targets.append((target, count))

    if not valid_targets:
        return results

    def _send_and_poll(target: str, count: int) -> tuple[str, SSMCommandResult]:
        """1ターゲットの送信→待機→ポーリングを1スレッドで完結させる"""
        thread_ssm = boto3.client("ssm", region_name=config.region)
        command = build_ping_command(target, count)

        try:
            response = thread_ssm.send_command(
                InstanceIds=[instance_id],
                DocumentName=config.document_name,
                Parameters={"commands": [command]},
                TimeoutSeconds=config.timeout_seconds,
            )
            command_id = response["Command"]["CommandId"]
        except Exception as e:
            return (target, SSMCommandResult(
                instance_id=instance_id, status="Failed", response_code=-1,
                stdout="", stderr=str(e),
            ))

        # 初期待機
        time.sleep(_INITIAL_WAIT_SECONDS + 0.5)

        # ポーリング
        poll_start = time.monotonic()
        result = _poll_command_result(
            ssm=thread_ssm,
            command_id=command_id,
            instance_id=instance_id,
            timeout_seconds=config.timeout_seconds,
            start_time=poll_start,
            region=config.region,
        )
        return (target, result)

    # 全ターゲットを完全並列実行
    with ThreadPoolExecutor(max_workers=min(len(valid_targets), 15)) as executor:
        futures = [
            executor.submit(_send_and_poll, target, count)
            for target, count in valid_targets
        ]
        for future in as_completed(futures):
            try:
                target, result = future.result()
                results[target] = [result]
            except Exception as e:
                # futureが例外を投げた場合のフォールバック
                pass

    return results


if __name__ == "__main__":
    main()
