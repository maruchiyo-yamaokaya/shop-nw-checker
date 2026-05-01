"""コアデータモデル定義

Enum・dataclassによるデータ構造を提供する。
Requirements: 3.3, 3.6, 7.1, 7.2, 7.3, 7.4, 7.5, 7.6
Requirements (SSMプローブ逆方向チェック): 1.1, 1.2, 1.3, 1.4, 1.5, 1.8, 1.9, 2.9, 5.1
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
    store_code: str
    wan_path: WANPath


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
    ping_interval: float = 0.2  # ping送信間隔（秒）。後方互換性のためデフォルト0.2


@dataclass
class GatewayDnsTarget:
    """ゲートウェイDNSテスト対象"""
    hostname: str
    expect: str  # "private_ip" | "nxdomain" | "resolve_success"


@dataclass
class PosDevice:
    """POS VLANローカル機材"""
    name: str
    ip: str


@dataclass
class ReverseCheckTarget:
    """逆方向チェック対象定義

    プローブから店舗側へICMP pingチェックする対象を定義する。
    named_terminalの場合、terminal_prefixesで指定したプレフィックスから
    <prefix>.s<store_code>.<domain> 形式でホスト名を直接構築する（Route 53不要）。
    """
    target_kind: str   # "local_pc" | "named_terminal"
    count: int = 5     # ping回数
    loss_threshold_percent: float = 20.0  # 許容パケットロス率（%）
    terminal_prefixes: list[str] | None = None  # named_terminal時のプレフィックスリスト（デフォルト: ["rt", "sw", "prn"]）


@dataclass
class VlanTestConfig:
    """VLAN種別固有テスト設定"""
    https_urls: list[str]
    store_gateway_dns_targets: list[GatewayDnsTarget]
    store_printer_host: str
    store_whereami_url: str
    pos_devices: list[PosDevice]
    public_dns_negative_targets: list[str]
    reverse_check_targets: list[ReverseCheckTarget] | None = None  # 逆方向チェック対象。後方互換性のためOptional


@dataclass
class SSMProbeConfig:
    """SSMプローブ設定

    AWS VPC内のEC2プローブインスタンスからSSM Run Commandで
    店舗側へICMP pingを実行するための設定。

    local_network_rangesのデフォルト値について:
    192.168.0.0/24 および 192.168.1.0/24 を意図的に除外している。
    除外理由: 家庭用ルーターのデフォルトIP範囲（192.168.0.x / 192.168.1.x）との
    衝突を避け、店舗LAN環境でのみ逆方向チェックを動作させるため。
    """
    region: str                          # AWSリージョン（例: "ap-northeast-1"）
    timeout_seconds: int                 # コマンド実行タイムアウト（キュー待ち含む）
    hosted_zone_domain: str              # Route 53ドメイン名（例: "yamaokaya.net"）
    local_network_ranges: list[str]      # 逆方向チェック実行条件のアドレス範囲リスト（CIDR表記）
    document_name: str = "AWS-RunShellScript"  # SSMドキュメント名
    target_tag_key: str = "NetCheckProbe"      # プローブ特定タグキー
    target_tag_value: str = "true"             # プローブ特定タグ値
    hosted_zone_id: str | None = None          # Hosted Zone ID直接指定（オプション）


@dataclass
class TestProfile:
    """テストプロファイル定義"""
    name: str
    description: str
    ping_targets: list[PingTarget]
    dns_targets: list[str]
    stability: StabilityConfig
    vlan_tests: VlanTestConfig | None = None  # 後方互換性のためOptional
    ssm_probe: SSMProbeConfig | None = None   # SSMプローブ設定。後方互換性のためOptional


@dataclass
class PingResult:
    """pingコマンド出力の構造化データ

    プローブ上のpingコマンド出力をパースした結果を保持する。
    全パケットロス時はRTT統計がNoneとなる（pingコマンドがRTT行を出力しないため）。
    """
    packets_transmitted: int
    packets_received: int
    packet_loss_percent: float
    rtt_min_ms: float | None    # 全パケットロス時はNone
    rtt_avg_ms: float | None    # 全パケットロス時はNone
    rtt_max_ms: float | None    # 全パケットロス時はNone
    rtt_mdev_ms: float | None   # 全パケットロス時はNone


@dataclass
class SSMCommandResult:
    """SSMコマンド実行結果（Transport層の出力）"""
    instance_id: str
    status: str       # "Success" | "Failed" | "TimedOut" | "Cancelled" | ...
    response_code: int
    stdout: str
    stderr: str


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
    store_code: str
    vlan_type: str
    wan_path: WANPath
    profile_name: str
    results: list[TestResult]
    execution_timestamp: datetime
    local_ip: str | None = None  # VLAN NICのローカルIPアドレス。後方互換性のためデフォルトNone

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
