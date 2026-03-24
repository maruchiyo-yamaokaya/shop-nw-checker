"""Setup Wizard（対話入力）

questionaryを使用したステップバイステップの対話入力インターフェース。
店舗コード → VLAN種別 → WAN経路 の3ステップで入力を収集する。
Requirements: 1.1〜1.5, 2.1〜2.3, 3.1〜3.4, 6.1〜6.4, 10.1〜10.3, 11.1〜11.6
"""

from __future__ import annotations

import re

import questionary
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .models import WANPath, WizardInput

console = Console()

# VLAN種別の選択肢
VLAN_TYPE_CHOICES = ["店舗", "POS", "公共"]

# WAN経路の選択肢
WAN_PATH_CHOICES = [
    {"name": "FTTH", "value": "ftth"},
    {"name": "LTE", "value": "lte"},
]


def validate_store_code(code: str) -> str | None:
    """店舗コードバリデーション

    入力を strip() した後、正規表現 ^[0-9]{4}$ に一致するか検証する。

    Args:
        code: 入力された店舗コード

    Returns:
        エラーメッセージ（バリデーション失敗時）またはNone（成功時）
    """
    if re.fullmatch(r"[0-9]{4}", code.strip()):
        return None
    return "店舗コードは4桁の数字で入力してください（例: 0001）"


def _build_confirmation_text(inputs: WizardInput) -> str:
    """確認サマリー用のテキストを構築する

    Args:
        inputs: ウィザード入力結果

    Returns:
        全フィールドの値を含むサマリー文字列
    """
    return (
        f"店舗コード: {inputs.store_code}\n"
        f"VLAN種別: {inputs.vlan_type}\n"
        f"WAN経路: {inputs.wan_path.value.upper()}"
    )


def display_confirmation(inputs: WizardInput) -> bool:
    """確認サマリーを表示し、承認/却下を返す

    Args:
        inputs: ウィザード入力結果

    Returns:
        True（承認）またはFalse（却下）
    """
    # richのPanelで見やすく表示
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("項目", style="cyan")
    table.add_column("値", style="white")

    table.add_row("店舗コード", inputs.store_code)
    table.add_row("VLAN種別", inputs.vlan_type)
    table.add_row("WAN経路", inputs.wan_path.value.upper())

    console.print()
    console.print(Panel(table, title="[bold]入力内容の確認[/bold]", border_style="blue"))
    console.print()

    confirmed = questionary.confirm(
        "この内容でテストを開始しますか？",
        default=True,
    ).ask()

    # Ctrl+C等でNoneが返る場合はFalse扱い
    return confirmed is True


def run_wizard() -> WizardInput:
    """ウィザードを実行し、入力結果を返す

    確認サマリーで却下された場合は最初から再開する。
    3ステップ構成: 店舗コード → VLAN種別 → WAN経路

    Returns:
        WizardInputオブジェクト
    """
    console.print()
    console.print("[bold blue]🔧 店舗ネットワークテスト Setup Wizard[/bold blue]")
    console.print("─" * 40)
    console.print()

    while True:
        # ステップ1: 店舗コード入力 (Req 1.1〜1.5, 11.1〜11.2)
        store_code = questionary.text(
            "店舗コードを入力してください（4桁数字）:",
            validate=lambda val: True if validate_store_code(val) is None else validate_store_code(val),
        ).ask()

        if store_code is None:
            raise KeyboardInterrupt("ウィザードが中断されました")

        # ステップ2: VLAN種別選択 (Req 2.1〜2.3)
        vlan_type = questionary.select(
            "VLAN種別を選択してください:",
            choices=VLAN_TYPE_CHOICES,
        ).ask()

        if vlan_type is None:
            raise KeyboardInterrupt("ウィザードが中断されました")

        # ステップ3: WAN経路選択 (Req 6.1〜6.4)
        wan_choices = [
            questionary.Choice(title=c["name"], value=c["value"])
            for c in WAN_PATH_CHOICES
        ]
        wan_selection = questionary.select(
            "WAN経路を選択してください:",
            choices=wan_choices,
        ).ask()

        if wan_selection is None:
            raise KeyboardInterrupt("ウィザードが中断されました")

        wan_path = WANPath(wan_selection)

        # WizardInputを構築
        wizard_input = WizardInput(
            store_code=store_code.strip(),
            vlan_type=vlan_type,
            wan_path=wan_path,
        )

        # 確認サマリー表示 (Req 10.1〜10.3)
        if display_confirmation(wizard_input):
            return wizard_input

        # 却下 → 最初から再開
        console.print()
        console.print("[yellow]入力をやり直します。[/yellow]")
        console.print()
