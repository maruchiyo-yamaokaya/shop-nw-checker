"""メインエントリーポイント

インターネット接続確認 → Setup Wizard → テストスイート実行 →
結果サマリー表示 → Airtable投入の一連フローを統合する。
Requirements: 8.1, 8.2, 8.3
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from rich.console import Console

from .profile import load_profiles
from .reporters.airtable import load_webhook_config, submit_results
from .runner import display_summary, run_test_suite
from .utils.network import check_internet_connectivity
from .utils.platform import check_platform_or_exit
from .wizard import run_wizard

console = Console()

# プロファイルディレクトリのデフォルトパス
DEFAULT_PROFILES_DIR = Path("profiles")


def _run() -> None:
    """メインフローを実行する（同期部分）"""
    # OS判定 (Req 9.7)
    check_platform_or_exit()

    console.print()
    console.print("[bold blue]🏪 店舗ネットワークテスト自動化ツール[/bold blue]")
    console.print("─" * 40)

    # インターネット接続確認 (Req 8.1, 8.2)
    console.print()
    console.print("インターネット接続を確認中...")
    if not check_internet_connectivity():
        console.print(
            "[bold red]❌ インターネット接続を確認できません。[/bold red]\n"
            "ネットワーク接続を確認してください。"
        )
        sys.exit(1)
    console.print("[green]✓ インターネット接続OK[/green]")

    # テストプロファイル読み込み
    try:
        profiles = load_profiles(DEFAULT_PROFILES_DIR)
    except (FileNotFoundError, ValueError) as e:
        console.print(f"[bold red]❌ プロファイル読み込みエラー: {e}[/bold red]")
        sys.exit(1)

    # Setup Wizard (Req 2.1〜2.10)
    try:
        wizard_input = run_wizard(available_profiles=profiles)
    except KeyboardInterrupt:
        console.print("\n[yellow]中断されました。[/yellow]")
        sys.exit(0)

    # 選択されたプロファイルを取得
    selected_profile = next(
        (p for p in profiles if p.name == wizard_input.test_profile),
        None,
    )
    if selected_profile is None:
        console.print(
            f"[bold red]❌ プロファイル '{wizard_input.test_profile}' が見つかりません。[/bold red]"
        )
        sys.exit(1)

    # テストスイート実行 (Req 3.1〜3.6)
    suite_results = run_test_suite(selected_profile, wizard_input)

    # 結果サマリー表示 (Req 3.6)
    display_summary(suite_results)

    # Airtable投入 (Req 6.1〜6.7)
    webhook_config = load_webhook_config()
    if webhook_config is not None:
        console.print("Airtableに結果を投入中...")
        success_count = asyncio.run(submit_results(webhook_config, suite_results))
        console.print(
            f"[green]✓ {success_count}/{len(suite_results)} 件の結果を投入しました。[/green]"
        )
    else:
        console.print(
            "[yellow]⚠ AIRTABLE_WEBHOOK_URL が未設定のため、Airtable投入をスキップしました。[/yellow]"
        )

    console.print()
    console.print("[bold green]テスト完了。[/bold green]")


def main() -> None:
    """エントリーポイント"""
    try:
        _run()
    except KeyboardInterrupt:
        console.print("\n[yellow]中断されました。[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"[bold red]❌ 予期しないエラー: {e}[/bold red]")
        sys.exit(1)


if __name__ == "__main__":
    main()
