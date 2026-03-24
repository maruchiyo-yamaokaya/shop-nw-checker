"""プラットフォームユーティリティ

OS判定、未サポートOS検出時のエラー表示。
Requirements: 9.1, 9.3, 9.7
"""

from __future__ import annotations

import sys

# サポート対象プラットフォーム
SUPPORTED_PLATFORMS = {"win32", "darwin", "linux"}


def get_platform() -> str:
    """現在のプラットフォーム識別子を返す"""
    return sys.platform


def is_supported_platform() -> bool:
    """現在のOSがサポート対象か判定する"""
    return get_platform() in SUPPORTED_PLATFORMS


def check_platform_or_exit() -> None:
    """未サポートOS検出時にエラーメッセージを表示して終了する

    サポート対象: Windows, macOS, Linux
    """
    if is_supported_platform():
        return

    platform = get_platform()
    supported = ", ".join(sorted(SUPPORTED_PLATFORMS))
    print(
        f"❌ 未サポートのOS: {platform}\n"
        f"サポート対象: {supported}"
    )
    sys.exit(1)
