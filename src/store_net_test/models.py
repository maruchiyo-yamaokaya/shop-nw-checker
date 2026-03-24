"""コアデータモデル定義

Enum・dataclassによるデータ構造を提供する。
Requirements: 3.3, 3.6, 7.1
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class WANPath(Enum):
    """WAN接続経路"""
    FTTH = "ftth"
    LTE = "lte"


class TestStatus(Enum):
    """テスト結果ステータス"""
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"
    ERROR = "error"


@dataclass
class WizardInput:
    """Setup Wizardの入力結果"""
    store_name: str
    nw_area: str
    vlan: str
    wan_paths: list[WANPath]
    test_profile: str


@dataclass
class PingTarget:
    """Pingテスト対象ホスト"""
    host: str
    timeout_ms: int


@dataclass
class StabilityConfig:
    """安定性テスト設定"""
    target_host: str
    duration_seconds: int
    max_packet_loss_percent: float
    max_jitter_ms: float


@dataclass
class TestProfile:
    """テストプロファイル定義"""
    name: str
    description: str
    ping_targets: list[PingTarget]
    dns_targets: list[str]
    stability: StabilityConfig


@dataclass
class TestResult:
    """個別テスト結果"""
    test_name: str
    wan_path: WANPath
    status: TestStatus
    timestamp: datetime
    details: dict = field(default_factory=dict)
    error_message: str | None = None


@dataclass
class SuiteResult:
    """テストスイート全体の結果"""
    store_name: str
    nw_area: str
    vlan: str
    wan_path: WANPath
    profile_name: str
    results: list[TestResult]
    execution_timestamp: datetime

    @property
    def overall_status(self) -> TestStatus:
        """全テスト結果から総合ステータスを算出

        - 1つでもFAILがあればFAIL
        - FAILがなくWARNINGがあればWARNING
        - それ以外はPASS
        """
        statuses = {r.status for r in self.results}
        if TestStatus.FAIL in statuses:
            return TestStatus.FAIL
        if TestStatus.WARNING in statuses:
            return TestStatus.WARNING
        return TestStatus.PASS

    @property
    def summary(self) -> dict[TestStatus, int]:
        """ステータス別のカウントを返す"""
        counts: dict[TestStatus, int] = {}
        for result in self.results:
            counts[result.status] = counts.get(result.status, 0) + 1
        return counts
