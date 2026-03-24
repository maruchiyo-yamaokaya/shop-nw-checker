"""ローカルJSONレポーター

SuiteResultをJSON直列化可能な辞書に変換し、ローカルファイルに保存する。
Airtable投入失敗時のフォールバックとしても使用される。
Requirements: 6.5
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from ..models import SuiteResult, TestResult, TestStatus


def _test_result_to_dict(result: TestResult) -> dict:
    """TestResultをJSON直列化可能な辞書に変換する"""
    return {
        "test_name": result.test_name,
        "wan_path": result.wan_path.value,
        "status": result.status.value,
        "timestamp": result.timestamp.isoformat(),
        "details": result.details,
        "error_message": result.error_message,
    }


def suite_result_to_dict(suite_result: SuiteResult) -> dict:
    """SuiteResultをJSON直列化可能な辞書に変換する

    Args:
        suite_result: テストスイート結果

    Returns:
        JSON直列化可能な辞書
    """
    return {
        "store_code": suite_result.store_code,
        "vlan_type": suite_result.vlan_type,
        "wan_path": suite_result.wan_path.value,
        "profile_name": suite_result.profile_name,
        "execution_timestamp": suite_result.execution_timestamp.isoformat(),
        "overall_status": suite_result.overall_status.value,
        "results": [_test_result_to_dict(r) for r in suite_result.results],
    }


def save_results_to_json(suite_result: SuiteResult, output_dir: Path) -> Path:
    """結果をローカルJSONファイルに保存する

    ファイル名は「{日付}_{店舗コード}_{WAN経路}.json」形式。

    Args:
        suite_result: テストスイート結果
        output_dir: 出力先ディレクトリ

    Returns:
        保存したファイルのパス
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp_str = suite_result.execution_timestamp.strftime("%Y-%m-%d_%H%M%S")
    filename = f"{timestamp_str}_{suite_result.store_code}_{suite_result.wan_path.value}.json"
    filepath = output_dir / filename

    data = suite_result_to_dict(suite_result)
    filepath.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    return filepath
