"""Setup Wizard（対話入力）

questionaryを使用したステップバイステップの対話入力インターフェース。
店舗名 → NW領域 → VLAN → WAN経路 → テストプロファイル の順で入力を収集する。
Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 2.8, 2.9, 2.10
"""

from __future__ import annotations

from dataclasses import dataclass

import questionary
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .models import TestProfile, WANPath, WizardInput

console = Console()

# NW領域の選択肢（店舗で一般的なネットワーク領域）
DEFAULT_NW_AREAS = [
    "バックヤード",
    "客席",
    "POS周辺",
    "事務所",
    "その他",
]

# WAN経路の選択肢
WAN_PATH_CHOICES = [
    {"name": "両方（FTTH + LTE）", "value": "both"},
    {"name": "FTTHのみ", "value": "ftth"},
    {"name": "LTEのみ", "value": "lte"},
]


@dataclass
class ProfileSummary:
    """プロファイル選択用のサマリー情報"""
    name: str
    description: str


def validate_store_name(name: str) -> str | None:
    """店舗名バリデーション

    空文字列・空白のみの文字列はエラー、
    1文字以上の非空白文字を含む文字列はNoneを返す。

    Args:
        name: 入力された店舗名

    Returns:
        エラーメッセージ（バリデーション失敗時）またはNone（成功時）
    """
    if not name or not name.strip():
        return "店舗名を入力してください（空白のみは不可）"
    return None


def validate_vlan(vlan: str) -> str | None:
    """VLANバリデーション

    空文字列・空白のみの文字列はエラー、
    非空白文字を含む文字列はNoneを返す。

    Args:
        vlan: 入力されたVLAN識別子

    Returns:
        エラーメッセージ（バリデーション失敗時）またはNone（成功時）
    """
    if not vlan or not vlan.strip():
        return "VLAN識別子を入力してください（空白のみは不可）"
    return None


def _build_confirmation_text(inputs: WizardInput) -> str:
    """確認サマリー用のテキストを構築する

    Args:
        inputs: ウィザード入力結果

    Returns:
        全フィールドの値を含むサマリー文字列
    """
    wan_display = ", ".join(wp.value.upper() for wp in inputs.wan_paths)
    return (
        f"店舗名: {inputs.store_name}\n"
        f"NW領域: {inputs.nw_area}\n"
        f"VLAN: {inputs.vlan}\n"
        f"WAN経路: {wan_display}\n"
        f"テストプロファイル: {inputs.test_profile}"
    )


def display_confirmation(inputs: WizardInput) -> bool:
    """確認サマリーを表示し、承認/却下を返す

    Args:
        inputs: ウィザード入力結果

    Returns:
        True（承認）またはFalse（却下）
    """
    summary_text = _build_confirmation_text(inputs)

    # richのPanelで見やすく表示
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("項目", style="cyan")
    table.add_column("値", style="white")

    wan_display = ", ".join(wp.value.upper() for wp in inputs.wan_paths)
    table.add_row("店舗名", inputs.store_name)
    table.add_row("NW領域", inputs.nw_area)
    table.add_row("VLAN", inputs.vlan)
    table.add_row("WAN経路", wan_display)
    table.add_row("テストプロファイル", inputs.test_profile)

    console.print()
    console.print(Panel(table, title="[bold]入力内容の確認[/bold]", border_style="blue"))
    console.print()

    confirmed = questionary.confirm(
        "この内容でテストを開始しますか？",
        default=True,
    ).ask()

    # Ctrl+C等でNoneが返る場合はFalse扱い
    return confirmed is True


def _parse_wan_selection(value: str) -> list[WANPath]:
    """WAN経路選択値をWANPathリストに変換する"""
    if value == "both":
        return [WANPath.FTTH, WANPath.LTE]
    elif value == "ftth":
        return [WANPath.FTTH]
    elif value == "lte":
        return [WANPath.LTE]
    return [WANPath.FTTH, WANPath.LTE]


def run_wizard(
    available_profiles: list[TestProfile],
    nw_areas: list[str] | None = None,
) -> WizardInput:
    """ウィザードを実行し、入力結果を返す

    確認サマリーで却下された場合は最初から再開する。
    Requirements: 2.1〜2.10

    Args:
        available_profiles: 選択可能なテストプロファイルのリスト
        nw_areas: NW領域の選択肢リスト（Noneの場合はデフォルト値を使用）

    Returns:
        WizardInputオブジェクト
    """
    areas = nw_areas if nw_areas is not None else DEFAULT_NW_AREAS

    console.print()
    console.print("[bold blue]🔧 店舗ネットワークテスト Setup Wizard[/bold blue]")
    console.print("─" * 40)
    console.print()

    while True:
        # Step 1: 店舗名入力 (Req 2.1, 2.8)
        store_name = questionary.text(
            "店舗名を入力してください:",
            validate=lambda val: True if validate_store_name(val) is None else validate_store_name(val),
        ).ask()

        if store_name is None:
            # Ctrl+C等で中断された場合
            raise KeyboardInterrupt("ウィザードが中断されました")

        # Step 2: NW領域選択 (Req 2.2)
        nw_area = questionary.select(
            "NW領域を選択してください:",
            choices=areas,
        ).ask()

        if nw_area is None:
            raise KeyboardInterrupt("ウィザードが中断されました")

        # Step 3: VLAN入力 (Req 2.3, 2.8)
        vlan = questionary.text(
            "VLAN識別子を入力してください:",
            validate=lambda val: True if validate_vlan(val) is None else validate_vlan(val),
        ).ask()

        if vlan is None:
            raise KeyboardInterrupt("ウィザードが中断されました")

        # Step 4: WAN経路選択 (Req 2.4, 2.9, 2.10)
        # デフォルトは"both"（両方）
        wan_choices = [
            questionary.Choice(title=c["name"], value=c["value"])
            for c in WAN_PATH_CHOICES
        ]
        wan_selection = questionary.select(
            "WAN経路を選択してください:",
            choices=wan_choices,
            default="both",
        ).ask()

        if wan_selection is None:
            raise KeyboardInterrupt("ウィザードが中断されました")

        wan_paths = _parse_wan_selection(wan_selection)

        # Step 5: テストプロファイル選択 (Req 2.5)
        profile_choices = [
            questionary.Choice(
                title=f"{p.name} - {p.description}",
                value=p.name,
            )
            for p in available_profiles
        ]
        selected_profile = questionary.select(
            "テストプロファイルを選択してください:",
            choices=profile_choices,
        ).ask()

        if selected_profile is None:
            raise KeyboardInterrupt("ウィザードが中断されました")

        # WizardInputを構築
        wizard_input = WizardInput(
            store_name=store_name.strip(),
            nw_area=nw_area,
            vlan=vlan.strip(),
            wan_paths=wan_paths,
            test_profile=selected_profile,
        )

        # Step 6: 確認サマリー表示 (Req 2.6)
        if display_confirmation(wizard_input):
            # 承認 → 入力結果を返す
            return wizard_input

        # 却下 → 最初から再開 (Req 2.7)
        console.print()
        console.print("[yellow]入力をやり直します。[/yellow]")
        console.print()
