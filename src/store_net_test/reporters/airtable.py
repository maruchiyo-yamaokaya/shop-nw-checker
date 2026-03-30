"""Airtableレポーター（Webhook方式）

テスト結果をAirtable Automations Webhookに投入する。
APIキー不要。WebhookのURLだけで動作する。
指数バックオフ付きリトライ、失敗時のローカルJSONフォールバックを提供する。
Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7
"""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path

import httpx
from rich.console import Console

from ..models import SuiteResult, TestStatus
from .local import save_results_to_json

# リトライ設定
MAX_RETRIES = 3
BASE_DELAY_SECONDS = 1.0

console = Console()


@dataclass
class WebhookConfig:
    """Airtable Webhook接続設定"""
    webhook_url: str


def _load_dotenv(env_path: Path) -> dict[str, str]:
    """シンプルな.envファイルパーサー

    外部ライブラリ不要。KEY=VALUE形式を読み込む。
    """
    values: dict[str, str] = {}
    if not env_path.exists():
        return values
    try:
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    except OSError:
        pass
    return values


# デフォルトのWebhook URL（コード内に保持）
_DEFAULT_WEBHOOK_URL = (
    "https://hooks.airtable.com/workflows/v1/genericWebhook/"
    "appHXyH8lXEf32CQM/wflebkrB9OHoCPLJf/wtrvxltzmeFAHgsq5"
)


def load_webhook_config(env_path: Path | None = None) -> WebhookConfig | None:
    """Webhook URLを取得する

    優先順位: 環境変数 > .envファイル > コード内デフォルト値
    環境変数や.envで上書き可能だが、通常はデフォルト値がそのまま使われる。

    Args:
        env_path: .envファイルのパス（省略時はプロジェクトルートの.env）

    Returns:
        WebhookConfig（常に非None）
    """
    # 環境変数で上書き可能
    webhook_url = os.environ.get("AIRTABLE_WEBHOOK_URL")

    # 環境変数になければ.envファイルから読み込む
    if not webhook_url:
        if env_path is None:
            env_path = Path(".env")
        dotenv = _load_dotenv(env_path)
        webhook_url = dotenv.get("AIRTABLE_WEBHOOK_URL")

    # どちらにもなければデフォルト値を使用
    if not webhook_url:
        webhook_url = _DEFAULT_WEBHOOK_URL

    return WebhookConfig(webhook_url=webhook_url)


def _format_detail(result: "TestResult") -> str:
    """TestResultの詳細を簡潔な文字列にフォーマットする"""
    if result.error_message:
        return result.error_message
    d = result.details
    parts: list[str] = []
    if "rtt_ms" in d:
        parts.append(f"RTT: {d['rtt_ms']}ms")
    if "resolution_time_ms" in d:
        parts.append(f"解決時間: {d['resolution_time_ms']}ms")
    if "resolved_ips" in d:
        parts.append(f"IP: {', '.join(d['resolved_ips'])}")
    if "packet_loss_percent" in d:
        parts.append(f"ロス: {d['packet_loss_percent']}%")
    if "jitter_ms" in d:
        parts.append(f"ジッター: {d['jitter_ms']}ms")
    if "status_code" in d:
        parts.append(f"HTTP {d['status_code']}")
    if "response_time_ms" in d:
        parts.append(f"{d['response_time_ms']}ms")
    if "match" in d:
        parts.append(f"一致: {d['match']}")
    if "actual_shop_code" in d:
        parts.append(f"shopCode: {d['actual_shop_code']}")
    return ", ".join(parts) if parts else "-"


def build_airtable_record(suite_result: SuiteResult) -> dict:
    """SuiteResultからWebhook送信用の辞書を構築する

    個別テスト結果をフラットフィールド（{test_name}_status / {test_name}_detail）
    として展開する。results_jsonは送信しない。

    Args:
        suite_result: テストスイート結果

    Returns:
        WebhookにPOSTするJSON辞書
    """
    from ..models import TestResult  # 循環import回避

    summary = suite_result.summary

    record: dict = {
        "store_code": suite_result.store_code,
        "vlan_type": suite_result.vlan_type,
        "wan_path": suite_result.wan_path.value.upper(),
        "execution_time": suite_result.execution_timestamp.isoformat(),
        "profile": suite_result.profile_name,
        "overall_status": suite_result.overall_status.value,
        "passed_count": summary.get(TestStatus.PASS, 0),
        "failed_count": summary.get(TestStatus.FAIL, 0),
        "warning_count": summary.get(TestStatus.WARNING, 0),
        "local_ip": suite_result.local_ip,
    }

    # 各テスト結果をフラットフィールドとして展開
    for r in suite_result.results:
        record[f"{r.test_name}_status"] = r.status.value
        record[f"{r.test_name}_detail"] = _format_detail(r)

    return record


async def _submit_single(
    client: httpx.AsyncClient,
    config: WebhookConfig,
    record: dict,
) -> None:
    """単一レコードをWebhookに投入する

    Raises:
        httpx.HTTPStatusError: Webhook呼び出し失敗時
    """
    response = await client.post(
        config.webhook_url,
        json=record,
        headers={"Content-Type": "application/json"},
    )
    response.raise_for_status()


async def submit_results(
    config: WebhookConfig,
    suite_result: SuiteResult,
    fallback_dir: Path | None = None,
) -> int:
    """テスト結果をAirtable Webhookに投入する

    指数バックオフ付き最大3回リトライ。全リトライ失敗時はローカルJSONにフォールバック。

    Args:
        config: Webhook設定
        suite_result: テストスイート結果
        fallback_dir: フォールバック保存先ディレクトリ（省略時は./results）

    Returns:
        成功した投入数（0または1）
    """
    if fallback_dir is None:
        fallback_dir = Path("./results")

    record = build_airtable_record(suite_result)

    async with httpx.AsyncClient(timeout=30.0) as client:
        ok = await _submit_with_retry(client, config, record, suite_result, fallback_dir)

    return 1 if ok else 0


async def _submit_with_retry(
    client: httpx.AsyncClient,
    config: WebhookConfig,
    record: dict,
    suite_result: SuiteResult,
    fallback_dir: Path,
) -> bool:
    """指数バックオフ付きリトライでレコードを投入する

    全リトライ失敗時はローカルJSONにフォールバック保存する。

    Returns:
        成功時True、フォールバック時False
    """
    for attempt in range(MAX_RETRIES):
        try:
            await _submit_single(client, config, record)
            console.print(
                f"✅ Airtable投入成功: {suite_result.store_code} "
                f"({suite_result.wan_path.value.upper()})"
            )
            return True
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            if attempt < MAX_RETRIES - 1:
                delay = BASE_DELAY_SECONDS * (2 ** attempt)
                console.print(
                    f"⚠️ Airtable投入リトライ ({attempt + 1}/{MAX_RETRIES}): {e}"
                )
                await asyncio.sleep(delay)
            else:
                # 全リトライ失敗 → ローカルJSONフォールバック
                filepath = save_results_to_json(suite_result, fallback_dir)
                console.print(
                    f"❌ Airtableへの投入に失敗しました。ローカルに保存しました: {filepath}"
                )
                return False

    return False
