"""レポーターモジュールのテスト

ローカルJSONレポーターとAirtableレポーターの動作を検証する。
Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6, 6.7
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from store_net_test.models import (
    SuiteResult,
    TestResult,
    TestStatus,
    WANPath,
)
from store_net_test.reporters.local import (
    save_results_to_json,
    suite_result_to_dict,
)
from store_net_test.reporters.airtable import (
    WebhookConfig,
    build_airtable_record,
    load_webhook_config,
    submit_results,
    _load_dotenv,
)


# --- テストデータヘルパー ---

def _make_test_result(**overrides) -> TestResult:
    """テスト用TestResultを生成する"""
    defaults = {
        "test_name": "ping_8.8.8.8",
        "wan_path": WANPath.FTTH,
        "status": TestStatus.PASS,
        "timestamp": datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
        "details": {"rtt_ms": 12.5, "threshold_ms": 1000},
        "error_message": None,
    }
    defaults.update(overrides)
    return TestResult(**defaults)


def _make_suite_result(**overrides) -> SuiteResult:
    """テスト用SuiteResultを生成する"""
    defaults = {
        "store_code": "0001",
        "vlan_type": "店舗",
        "wan_path": WANPath.FTTH,
        "profile_name": "standard",
        "results": [
            _make_test_result(),
            _make_test_result(test_name="dns_www.google.com", status=TestStatus.PASS),
        ],
        "execution_timestamp": datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
    }
    defaults.update(overrides)
    return SuiteResult(**defaults)


# --- ローカルJSONレポーター テスト ---

class TestSuiteResultToDict:
    """suite_result_to_dict: SuiteResultをJSON直列化可能な辞書に変換"""

    def test_全フィールドが辞書に含まれる(self):
        suite = _make_suite_result()
        result = suite_result_to_dict(suite)
        assert result["store_code"] == "0001"
        assert result["vlan_type"] == "店舗"
        assert result["wan_path"] == "ftth"
        assert result["profile_name"] == "standard"
        assert result["overall_status"] == "pass"
        assert len(result["results"]) == 2

    def test_テスト結果の詳細が正しく変換される(self):
        suite = _make_suite_result()
        result = suite_result_to_dict(suite)
        first = result["results"][0]
        assert first["test_name"] == "ping_8.8.8.8"
        assert first["wan_path"] == "ftth"
        assert first["status"] == "pass"
        assert first["details"]["rtt_ms"] == 12.5
        assert first["error_message"] is None

    def test_fail結果のoverall_statusがfail(self):
        suite = _make_suite_result(results=[
            _make_test_result(status=TestStatus.PASS),
            _make_test_result(test_name="dns_fail", status=TestStatus.FAIL),
        ])
        result = suite_result_to_dict(suite)
        assert result["overall_status"] == "fail"

    def test_warning結果のoverall_statusがwarning(self):
        suite = _make_suite_result(results=[
            _make_test_result(status=TestStatus.PASS),
            _make_test_result(test_name="stability", status=TestStatus.WARNING),
        ])
        result = suite_result_to_dict(suite)
        assert result["overall_status"] == "warning"

    def test_JSON直列化が可能(self):
        """辞書がjson.dumpsで直列化できることを確認"""
        suite = _make_suite_result()
        result = suite_result_to_dict(suite)
        json_str = json.dumps(result, ensure_ascii=False)
        assert isinstance(json_str, str)
        # デシリアライズして元の辞書と等価
        assert json.loads(json_str) == result

    def test_error_messageが含まれる場合(self):
        suite = _make_suite_result(results=[
            _make_test_result(
                status=TestStatus.FAIL,
                error_message="Connection timed out",
            ),
        ])
        result = suite_result_to_dict(suite)
        assert result["results"][0]["error_message"] == "Connection timed out"


class TestSaveResultsToJson:
    """save_results_to_json: 結果をローカルJSONファイルに保存"""

    def test_ファイルが正しく保存される(self, tmp_path: Path):
        suite = _make_suite_result()
        filepath = save_results_to_json(suite, tmp_path)
        assert filepath.exists()
        assert filepath.suffix == ".json"

    def test_保存内容がJSON読み込み可能(self, tmp_path: Path):
        suite = _make_suite_result()
        filepath = save_results_to_json(suite, tmp_path)
        data = json.loads(filepath.read_text(encoding="utf-8"))
        assert data["store_code"] == "0001"
        assert data["vlan_type"] == "店舗"
        assert len(data["results"]) == 2

    def test_ファイル名に店舗コードとVLAN種別とWAN経路が含まれる(self, tmp_path: Path):
        suite = _make_suite_result()
        filepath = save_results_to_json(suite, tmp_path)
        assert "0001" in filepath.name
        assert "店舗" in filepath.name
        assert "ftth" in filepath.name

    def test_出力ディレクトリが自動作成される(self, tmp_path: Path):
        output_dir = tmp_path / "nested" / "dir"
        suite = _make_suite_result()
        filepath = save_results_to_json(suite, output_dir)
        assert filepath.exists()
        assert output_dir.exists()

    def test_日本語が正しくエンコードされる(self, tmp_path: Path):
        suite = _make_suite_result()
        filepath = save_results_to_json(suite, tmp_path)
        content = filepath.read_text(encoding="utf-8")
        assert "0001" in content
        assert "店舗" in content


# --- Airtableレポーター テスト ---

class TestLoadDotenv:
    """_load_dotenv: .envファイルパーサー"""

    def test_有効なenvファイルを読み込める(self, tmp_path: Path):
        env_file = tmp_path / ".env"
        env_file.write_text("KEY1=value1\nKEY2=value2\n", encoding="utf-8")
        result = _load_dotenv(env_file)
        assert result == {"KEY1": "value1", "KEY2": "value2"}

    def test_コメント行をスキップ(self, tmp_path: Path):
        env_file = tmp_path / ".env"
        env_file.write_text("# コメント\nKEY=value\n", encoding="utf-8")
        result = _load_dotenv(env_file)
        assert result == {"KEY": "value"}

    def test_空行をスキップ(self, tmp_path: Path):
        env_file = tmp_path / ".env"
        env_file.write_text("\nKEY=value\n\n", encoding="utf-8")
        result = _load_dotenv(env_file)
        assert result == {"KEY": "value"}

    def test_存在しないファイルは空辞書(self, tmp_path: Path):
        result = _load_dotenv(tmp_path / "nonexistent")
        assert result == {}

    def test_等号なし行をスキップ(self, tmp_path: Path):
        env_file = tmp_path / ".env"
        env_file.write_text("NOEQUALS\nKEY=value\n", encoding="utf-8")
        result = _load_dotenv(env_file)
        assert result == {"KEY": "value"}


class TestLoadWebhookConfig:
    """load_webhook_config: Webhook設定の読み込み"""

    def test_環境変数から読み込める(self, monkeypatch):
        monkeypatch.setenv("AIRTABLE_WEBHOOK_URL", "https://hooks.airtable.com/test")
        config = load_webhook_config()
        assert config is not None
        assert config.webhook_url == "https://hooks.airtable.com/test"

    def test_envファイルから読み込める(self, tmp_path: Path, monkeypatch):
        monkeypatch.delenv("AIRTABLE_WEBHOOK_URL", raising=False)
        env_file = tmp_path / ".env"
        env_file.write_text("AIRTABLE_WEBHOOK_URL=https://hooks.airtable.com/file\n")
        config = load_webhook_config(env_path=env_file)
        assert config is not None
        assert config.webhook_url == "https://hooks.airtable.com/file"

    def test_環境変数がenvファイルより優先(self, tmp_path: Path, monkeypatch):
        monkeypatch.setenv("AIRTABLE_WEBHOOK_URL", "https://hooks.airtable.com/env")
        env_file = tmp_path / ".env"
        env_file.write_text("AIRTABLE_WEBHOOK_URL=https://hooks.airtable.com/file\n")
        config = load_webhook_config(env_path=env_file)
        assert config.webhook_url == "https://hooks.airtable.com/env"

    def test_未設定時はNone(self, tmp_path: Path, monkeypatch):
        monkeypatch.delenv("AIRTABLE_WEBHOOK_URL", raising=False)
        config = load_webhook_config(env_path=tmp_path / "empty.env")
        assert config is None


class TestBuildAirtableRecord:
    """build_airtable_record: Webhookレコード構築"""

    def test_全必須フィールドが含まれる(self):
        suite = _make_suite_result()
        record = build_airtable_record(suite)
        # Req 9.1, 9.2, 9.3: 全必須フィールドの存在確認
        assert "store_code" in record
        assert "vlan_type" in record
        assert "wan_path" in record
        assert "execution_time" in record
        assert "profile" in record
        assert "overall_status" in record
        assert "results_json" in record
        assert "passed_count" in record
        assert "failed_count" in record
        assert "warning_count" in record
        # 旧フィールドが含まれないこと
        assert "store_name" not in record
        assert "nw_area" not in record
        assert "vlan" not in record

    def test_フィールド値が正しい(self):
        suite = _make_suite_result()
        record = build_airtable_record(suite)
        assert record["store_code"] == "0001"
        assert record["vlan_type"] == "店舗"
        assert record["wan_path"] == "FTTH"
        assert record["profile"] == "standard"
        assert record["overall_status"] == "pass"
        assert record["passed_count"] == 2
        assert record["failed_count"] == 0
        assert record["warning_count"] == 0

    def test_fail結果のカウントが正しい(self):
        suite = _make_suite_result(results=[
            _make_test_result(status=TestStatus.PASS),
            _make_test_result(test_name="dns_fail", status=TestStatus.FAIL),
            _make_test_result(test_name="stability", status=TestStatus.WARNING),
        ])
        record = build_airtable_record(suite)
        assert record["passed_count"] == 1
        assert record["failed_count"] == 1
        assert record["warning_count"] == 1
        assert record["overall_status"] == "fail"

    def test_results_jsonがJSON文字列(self):
        suite = _make_suite_result()
        record = build_airtable_record(suite)
        # results_jsonがパース可能なJSON文字列であること
        parsed = json.loads(record["results_json"])
        assert isinstance(parsed, list)
        assert len(parsed) == 2

    def test_wan_pathが大文字(self):
        """WAN経路がAirtable用に大文字変換されること"""
        suite_ftth = _make_suite_result(wan_path=WANPath.FTTH)
        suite_lte = _make_suite_result(wan_path=WANPath.LTE)
        assert build_airtable_record(suite_ftth)["wan_path"] == "FTTH"
        assert build_airtable_record(suite_lte)["wan_path"] == "LTE"


class TestSubmitResults:
    """submit_results: Webhook投入とリトライ・フォールバック"""

    @pytest.mark.asyncio
    async def test_成功時にカウントが返る(self, tmp_path: Path):
        """成功時の投入"""
        config = WebhookConfig(webhook_url="https://hooks.airtable.com/test")
        suite = _make_suite_result()

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = lambda: None

        with patch("store_net_test.reporters.airtable.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.return_value = mock_response
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            count = await submit_results(config, suite, fallback_dir=tmp_path)
            assert count == 1
            mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_全リトライ失敗時にローカル保存(self, tmp_path: Path):
        """リトライ失敗時のフォールバック"""
        config = WebhookConfig(webhook_url="https://hooks.airtable.com/test")
        suite = _make_suite_result()

        with patch("store_net_test.reporters.airtable.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.side_effect = httpx.RequestError("Connection failed")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            # リトライ間のsleepをスキップ
            with patch("store_net_test.reporters.airtable.asyncio.sleep", new_callable=AsyncMock):
                count = await submit_results(config, suite, fallback_dir=tmp_path)

            assert count == 0
            # ローカルJSONが保存されていること
            json_files = list(tmp_path.glob("*.json"))
            assert len(json_files) == 1

    @pytest.mark.asyncio
    async def test_3回リトライされる(self, tmp_path: Path):
        """最大3回リトライ"""
        config = WebhookConfig(webhook_url="https://hooks.airtable.com/test")
        suite = _make_suite_result()

        with patch("store_net_test.reporters.airtable.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.post.side_effect = httpx.RequestError("Connection failed")
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with patch("store_net_test.reporters.airtable.asyncio.sleep", new_callable=AsyncMock):
                await submit_results(config, suite, fallback_dir=tmp_path)

            # 3回呼び出されること（初回 + リトライ2回）
            assert mock_client.post.call_count == 3

    @pytest.mark.asyncio
    async def test_リトライ後に成功(self, tmp_path: Path):
        """リトライで回復するケース"""
        config = WebhookConfig(webhook_url="https://hooks.airtable.com/test")
        suite = _make_suite_result()

        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = lambda: None

        with patch("store_net_test.reporters.airtable.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            # 1回目失敗、2回目成功
            mock_client.post.side_effect = [
                httpx.RequestError("Connection failed"),
                mock_response,
            ]
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            with patch("store_net_test.reporters.airtable.asyncio.sleep", new_callable=AsyncMock):
                count = await submit_results(config, suite, fallback_dir=tmp_path)

            assert count == 1
            # ローカルJSONは保存されない
            json_files = list(tmp_path.glob("*.json"))
            assert len(json_files) == 0


# --- local_ip直列化テスト ---


class TestSuiteResultToDictLocalIp:
    """suite_result_to_dict: local_ipフィールドの直列化 (Req 2.3)"""

    def test_local_ipが辞書に含まれる(self):
        """local_ipが設定されている場合、出力辞書にlocal_ipキーが含まれる"""
        suite = _make_suite_result(local_ip="192.168.1.100")
        result = suite_result_to_dict(suite)
        assert "local_ip" in result
        assert result["local_ip"] == "192.168.1.100"

    def test_local_ipがNoneの場合にnullとして出力される(self):
        """local_ip=Noneの場合、出力辞書にlocal_ip=Noneが含まれる"""
        suite = _make_suite_result(local_ip=None)
        result = suite_result_to_dict(suite)
        assert "local_ip" in result
        assert result["local_ip"] is None

    def test_local_ipがNoneの場合にJSON直列化でnullになる(self):
        """local_ip=Noneの場合、JSON直列化でnullとして出力される"""
        suite = _make_suite_result(local_ip=None)
        result = suite_result_to_dict(suite)
        json_str = json.dumps(result, ensure_ascii=False)
        parsed = json.loads(json_str)
        assert parsed["local_ip"] is None


class TestBuildAirtableRecordLocalIp:
    """build_airtable_record: local_ipフィールドの直列化 (Req 2.4)"""

    def test_local_ipがレコードに含まれる(self):
        """local_ipが設定されている場合、Webhookペイロードにlocal_ipキーが含まれる"""
        suite = _make_suite_result(local_ip="10.0.0.5")
        record = build_airtable_record(suite)
        assert "local_ip" in record
        assert record["local_ip"] == "10.0.0.5"

    def test_local_ipがNoneの場合にnullとして出力される(self):
        """local_ip=Noneの場合、Webhookペイロードにlocal_ip=Noneが含まれる"""
        suite = _make_suite_result(local_ip=None)
        record = build_airtable_record(suite)
        assert "local_ip" in record
        assert record["local_ip"] is None
