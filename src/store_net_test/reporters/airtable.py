"""Airtableレポーター（Webhook方式）

テスト結果をAirtable Automations Webhookに投入する。
APIキー不要。WebhookのURLだけで動作する。
指数バックオフ付きリトライ、失敗時のローカルJSONフォールバックを提供する。
Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path

import httpx
from rich.console import Console

from ..models import SuiteResult, TestStatus
from .local import save_results_to_json, suite_result_to_dict

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


def load_webhook_config(env_path: Path | None = None) -> WebhookConfig | None:
    """環境変数または.envファイルからWebhook URLを読み込む

    優先順位: 環境変数 > .envファイル
    未設定の場合はNoneを返す（Airtable投入をスキップする判断に使う）。

    Args:
        env_path: .envファイルのパス（省略時はプロジェクトルートの.env）

    Returns:
        WebhookConfig、または未設定時はNone
    """
    webhook_url = os.environ.get("AIRTABLE_WEBHOOK_URL")

    # 環境変数になければ.envファイルから読み込む
    if not webhook_url:
        if env_path is None:
            env_path = Path(".env")
        dotenv = _load_dotenv(env_path)
        webhook_url = dotenv.get("AIRTABLE_WEBHOOK_URL")

    if not webhook_url:
        return None

    return WebhookConfig(webhook_url=webhook_url)


def build_airtable_record(suite_result: SuiteResult) -> dict:
    """SuiteResultからWebhook送信用の辞書を構築する

    Args:
        suite_result: テストスイート結果

    Returns:
        WebhookにPOSTするJSON辞書
    """
    summary = suite_result.summary
    results_dict = suite_result_to_dict(suite_result)

    return {
        "store_code": suite_result.store_code,
        "vlan_type": suite_result.vlan_type,
        "wan_path": suite_result.wan_path.value.upper(),
        "execution_time": suite_result.execution_timestamp.isoformat(),
        "profile": suite_result.profile_name,
        "overall_status": suite_result.overall_status.value,
        "results_json": json.dumps(results_dict["results"], ensure_ascii=False),
        "passed_count": summary.get(TestStatus.PASS, 0),
        "failed_count": summary.get(TestStatus.FAIL, 0),
        "warning_count": summary.get(TestStatus.WARNING, 0),
    }


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
