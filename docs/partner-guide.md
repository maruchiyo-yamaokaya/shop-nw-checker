# 店舗ネットワークテストツール 外部パートナー向けガイド

このドキュメントは、店舗ネットワークテストツール（shop-nw-checker）の通信・前提ツール・ふるまいをまとめたものです。

- 想定読者は 2 者です。店舗でツールを実行する作業者と、FW（＝ファイアウォールのこと）やプロキシの許可設定をするネットワーク担当者です。
- 記述は main ブランチ（2026-10-07 のコミット 0cac0a2 時点）の実装に基づきます。ツールは起動のたびに main の最新コードを取り込むため、今後の更新で内容が変わる場合があります。
- 「要確認」と書いた項目は、実装や公式資料で確定できなかった点です。一覧は「7. 要確認事項」にあります。

## 1. 概要

本ツールは、店舗のネットワーク構築・変更後に、名前解決・到達性・安定性を自動でテストする CLI ツール（＝コマンドラインで操作するツールのこと）です。作業者は端末を店舗・POS・公共の 3 つの VLAN（＝1 つの物理ネットワークを論理的に分割したネットワークのこと）に順に接続します。ツールは VLAN ごとにテストを実行し、結果を画面に表示します。結果は Airtable（＝クラウド型のデータベースサービスのこと）にも送信します。

## 2. 前提ツール・動作環境

### 2-1. 動作環境と必要なツール

Python 本体は利用者がインストールする必要はありません。uv（＝Python の実行環境と依存パッケージを管理するツールのこと）が用意します。git（＝ソースコードの取得・更新に使うバージョン管理ツールのこと）と uv は必須です。初回セットアップには bootstrap（＝初回セットアップを自動で行うスクリプトのこと）を使います。

| 項目 | 内容 |
|---|---|
| 対応 OS | Windows、macOS、Linux。それ以外の OS では起動時にエラーで終了します |
| Python | 3.11 以上。端末に条件を満たす Python が無い場合は uv が自動で取得します |
| git | 必須 |
| uv | 必須 |
| curl | macOS / Linux の初回セットアップコマンドで使います |
| bash | macOS / Linux の bootstrap.sh の実行に使います |
| PowerShell | Windows のセットアップと起動に使います |
| 端末の操作 | 対話入力（文字入力・選択・Enter）ができるターミナルが必要です |
| ネットワーク | 実行中に、店舗・POS・公共の各 VLAN へ接続を切り替えられる必要があります |

### 2-2. bootstrap が自動で行うこと

bootstrap は OS ごとに 2 種類あります。macOS / Linux は bootstrap.sh、Windows は bootstrap.ps1 です。手順とコマンドは [README.md](../README.md) の「クイックスタート」を参照してください。

下の表には次の用語が出てきます。ICMP（＝ping が使う制御用プロトコルのこと）は、接続確認とテストに使います。sudo（＝Linux / macOS で管理者権限でコマンドを実行する仕組みのこと）は、Linux で git を導入するときに使います。PATH（＝コマンドを探すディレクトリの一覧のこと）は、uv を導入したときに追加します。

| 処理 | macOS / Linux（bootstrap.sh） | Windows（bootstrap.ps1） |
|---|---|---|
| インターネット接続確認 | curl または wget で `https://www.google.com` に接続します（タイムアウト 5 秒）。失敗した場合は `8.8.8.8` の TCP 53 番への接続を試します | `8.8.8.8` に ICMP Echo を 1 回送ります |
| git が無い場合 | macOS: `xcode-select --install` を起動し、完了後の再実行を求めて終了します。Linux: `sudo apt-get`、`sudo yum`、`sudo dnf` のいずれかで導入します | 導入コマンドを表示して終了します。自動では導入しません |
| uv が無い場合 | `https://astral.sh/uv/install.sh` のインストーラーで導入します。PATH に `~/.local/bin` と `~/.cargo/bin` を追加します（スクリプトの実行中のみ） | 導入コマンドを表示して終了します。自動では導入しません |
| リポジトリの取得・更新 | `shop-nw-checker/` が無ければ `git clone` します。あれば `git pull --ff-only` します。pull に失敗しても既存のコードで続行します | macOS / Linux と同じです |
| 依存パッケージの導入 | `uv sync` を実行します | `uv sync` を実行します |
| ツールの起動 | 起動しません。起動コマンドを表示して終了します | `uv run` でツールを起動します |

2 回目以降の実行方法は OS で異なります。macOS / Linux は README の「ツール起動」コマンドを実行します。このコマンドは `git pull` → `uv sync` → 起動の順に進み、`git pull` が失敗すると起動しません。Windows は bootstrap.ps1 を毎回実行します。

### 2-3. 管理者権限

sudo が必要になるのは、Linux で git を自動導入する場合だけです。ツール本体のコードには、権限を昇格する処理はありません。

ツールは icmplib（＝ツールが ping に使う Python ライブラリのこと）で ICMP を送ります。Windows では icmplib が常に raw ソケット（＝ICMP パケットをアプリケーション側で組み立てて送る方式のこと）を使います（[icmplib のソース](https://github.com/ValentinBELYN/icmplib/blob/main/icmplib/sockets.py)）。git の導入には、macOS では Xcode Command Line Tools（＝macOS で git などの開発ツールを提供する Apple 製パッケージのこと）を、Windows では winget（＝Windows 標準のパッケージ管理ツールのこと）を使います。winget で Git を導入する場合、UAC（＝Windows のユーザーアカウント制御のこと）の確認が出る可能性があります。

| 場面 | 管理者権限 |
|---|---|
| ツール本体の実行（macOS / Linux） | 不要です。ICMP は root 権限が不要な方式で送ります。一部の Linux では `net.ipv4.ping_group_range` の設定が必要な場合があります（[icmplib の公式ドキュメント](https://github.com/ValentinBELYN/icmplib/blob/main/docs/6-use-icmplib-without-privileges.md)では Ubuntu 20.04 LTS 以降は不要とされています） |
| ツール本体の実行（Windows） | ツールに昇格処理はありません。ICMP は raw ソケットで送ります。管理者でない PowerShell で ICMP 系のテストが動くかは要確認です |
| git の自動導入（Linux） | 必要です（`sudo apt-get` / `sudo yum` / `sudo dnf`） |
| git の導入（macOS） | Xcode Command Line Tools のインストーラーが起動します。管理者パスワードの要否は要確認です |
| git の導入（Windows、winget） | [winget のマニフェスト](https://github.com/microsoft/winget-pkgs/tree/master/manifests/g/Git/Git)では、Git のインストーラー自身が昇格を求める設定（`ElevationRequirement: elevatesSelf`）です（2026-10 時点の 2.55.0.5 で確認）。UAC の確認画面が出るかは要確認です |
| uv の導入 | 2026-10 時点の uv インストーラー（[install.sh](https://astral.sh/uv/install.sh) / [install.ps1](https://astral.sh/uv/install.ps1)）には、権限を昇格する処理がありません。uv はユーザーのホームディレクトリ配下に置かれます |
| PowerShell の実行ポリシー | 変更しません。`-ExecutionPolicy ByPass` はその PowerShell プロセスにのみ効きます |

## 3. 通信一覧

表の読み方は次のとおりです。

- 「方向」の「外部」は、端末以外のすべて（店舗 LAN 内の機器を含む）を指します。「端末→外部」は端末から出ていく通信で、応答はその戻り通信です。
- 「必須」は、許可しないとツールが動かない、またはテストが FAIL になる通信です。「条件付き」は、表に書いた条件のときだけ発生する通信です。
- ICMP にはポート番号が無いため、ポート列は「—」とします。ICMP は Echo Request を送り、Echo Reply を受け取ります。
- ホスト名の名前解決は、特に書いていない限り OS のリゾルバ（＝OS に組み込まれた名前解決の仕組みのこと）経由で行います。つまり OS に設定された DNS（＝ホスト名を IP アドレスに変換する仕組みのこと）サーバーへの UDP / TCP 53 番の通信が別に発生します。
- ツールはどのポートでも待ち受けません（サーバー機能はありません）。

### 3-1. 初回セットアップ・更新時

PyPI（＝Python パッケージの公開リポジトリのこと）からの取得は、uv が行います。

| 宛先（ホスト名/IP） | プロトコル | ポート | 方向 | 目的 | 必須/任意 |
|---|---|---|---|---|---|
| `raw.githubusercontent.com` | HTTPS | TCP 443 | 端末→外部 | bootstrap.sh / bootstrap.ps1 の取得（main ブランチ） | 必須。macOS / Linux は初回のみ、Windows は起動のたび |
| `github.com` | HTTPS | TCP 443 | 端末→外部 | リポジトリの取得（`git clone`）と更新（`git pull`） | 必須（起動のたび） |
| `www.google.com` | HTTPS | TCP 443 | 端末→外部 | bootstrap.sh のインターネット接続確認 | macOS / Linux の初回。次の行とどちらか一方に到達できればよい |
| `8.8.8.8` | TCP | 53 | 端末→外部 | bootstrap.sh の接続確認の代替。`www.google.com` で確認できない場合、または curl と wget が両方無い場合に使う | 条件付き |
| `8.8.8.8` | ICMP Echo（1 回） | — | 端末→外部 | bootstrap.ps1 のインターネット接続確認 | Windows では必須（起動のたび） |
| `astral.sh` | HTTPS | TCP 443 | 端末→外部 | uv インストーラー（install.sh / install.ps1）の取得 | uv が未導入の場合のみ |
| `releases.astral.sh`、`github.com`、`release-assets.githubusercontent.com` | HTTPS | TCP 443 | 端末→外部 | uv 本体の取得 | uv が未導入の場合のみ |
| `pypi.org`、`files.pythonhosted.org` | HTTPS | TCP 443 | 端末→外部 | 依存パッケージの取得（`uv sync` / `uv run`） | 初回は必須。2 回目以降は、ロックの再解決や未取得パッケージの取得が必要な場合に発生 |
| `releases.astral.sh` | HTTPS | TCP 443 | 端末→外部 | Python 本体の取得 | 端末に Python 3.11 以上が無い場合のみ |
| `cdn.winget.microsoft.com` | HTTPS | TCP 443 | 端末→外部 | winget のパッケージ情報の取得（README の Git 導入手順） | Windows で git が未導入の場合のみ |
| `github.com`、`release-assets.githubusercontent.com` | HTTPS | TCP 443 | 端末→外部 | Git for Windows のインストーラーの取得（winget 経由） | Windows で git が未導入の場合のみ |
| Apple のソフトウェア配布サーバー（ホスト名は要確認） | HTTPS（要確認） | TCP 443（要確認） | 端末→外部 | Xcode Command Line Tools の導入 | macOS で git が未導入の場合のみ |
| 各 Linux ディストリビューションのパッケージミラー（環境依存） | HTTP / HTTPS | TCP 80 / 443 | 端末→外部 | git の導入（apt-get / yum / dnf） | Linux で git が未導入の場合のみ |

補足は次のとおりです。

- uv のインストーラー（2026-10 時点の [install.sh](https://astral.sh/uv/install.sh) / [install.ps1](https://astral.sh/uv/install.ps1)）は、先に `releases.astral.sh` から uv 本体を取得します。失敗すると `github.com` を試します。
- `github.com` のリリースの配布ファイルは、`release-assets.githubusercontent.com` にリダイレクトされます。これは 2026-10 時点の実測です。GitHub の公式資料での記載は要確認です。
- Python 本体の取得元 `releases.astral.sh` は、uv 0.12.18（macOS）で確認した値です。uv のバージョンや OS による違いは要確認です。
- winget の既定ソースは `https://cdn.winget.microsoft.com/cache` です（[Microsoft Learn の winget source コマンドの説明](https://learn.microsoft.com/en-us/windows/package-manager/winget/source)）。
- Git for Windows のインストーラーの URL は、`github.com` 上にあります（[winget-pkgs の Git.Git マニフェスト](https://github.com/microsoft/winget-pkgs/tree/master/manifests/g/Git/Git)）。この URL も `release-assets.githubusercontent.com` にリダイレクトされます（2026-10 時点の実測）。
- Xcode Command Line Tools の取得元ホストは確定できませんでした。Apple の「[Use Apple products on enterprise networks](https://support.apple.com/en-us/101555)」の Software updates の節が参考になります。

### 3-2. テスト実行時

テストは店舗・POS・公共の各 VLAN で順に実行します。「全 VLAN」と書いた通信は、3 つの VLAN それぞれから発生します。WhereAmI テスト（＝社内 API が返す店舗コードと、入力した店舗コードを照合するテストのこと）は、店舗 VLAN でのみ実行します。逆方向チェック（＝AWS 側から逆方向に到達性を確認する仕組みのこと。SSM probe とも呼びます）は 3-4 で説明します。

下の表には次の用語が出てきます。デフォルトゲートウェイ（＝端末が自分のネットワークの外へ通信するときに、最初にパケットを渡すルーターのこと）は、DNS 解決テストで DNS サーバーとして使います。A レコード（＝ホスト名に対応する IPv4 アドレスを示す DNS の情報のこと）は、DNS 解決テストで取得する情報です。

| 宛先（ホスト名/IP） | プロトコル | ポート | 方向 | 目的 | 必須/任意 |
|---|---|---|---|---|---|
| `8.8.8.8` | TCP（接続のみ） | 53 | 端末→外部 | 起動時のインターネット接続確認（1 回、タイムアウト 5 秒） | 必須。失敗するとツールは終了する |
| デフォルトゲートウェイの IP アドレス（取得できない場合は `8.8.8.8`、`1.1.1.1`） | DNS（UDP。切り詰め時は TCP） | 53 | 端末→外部 | DNS 解決テスト（`www.google.com`、`dns.google` の A レコード） | 必須（全 VLAN） |
| `8.8.8.8`、`1.1.1.1` | ICMP Echo（各 1 回） | — | 端末→外部 | Ping 到達性テスト | 必須（全 VLAN） |
| `8.8.8.8` | ICMP Echo（0.2 秒間隔で 25 回） | — | 端末→外部 | 安定性テスト | 必須（全 VLAN） |
| `www.google.com`、`www.cloudflare.com`、`www.amazon.co.jp`（リダイレクト先を含む） | HTTPS（GET） | TCP 443 | 端末→外部 | HTTPS 疎通テスト | 必須（全 VLAN） |
| OS に設定された DNS サーバー | DNS（UDP。切り詰め時は TCP） | 53 | 端末→外部 | 店舗 DNS 解決テスト（4 件のホスト名） | 必須（店舗 VLAN のみ） |
| `prn.myshop.yamaokaya.net` | ICMP Echo（1 回） | — | 端末→外部 | 複合機の Ping テスト | 必須（店舗 VLAN のみ） |
| `api.yamaokaya.net` | HTTPS（GET） | TCP 443 | 端末→外部 | WhereAmI テスト（`https://api.yamaokaya.net/wb/whereami`） | 必須（店舗 VLAN のみ） |
| `192.168.1.81`、`192.168.1.82`、`192.168.1.110` | ICMP Echo（各 1 回） | — | 端末→外部 | POS 機器の Ping テスト | 必須（POS VLAN のみ） |
| 逆方向チェックの宛先（3-4 を参照） | 3-4 を参照 | 3-4 を参照 | 3-4 を参照 | 逆方向チェック | 既定では実行しない |

補足は次のとおりです。

- DNS 解決テストは、OS の DNS 設定ではなく、デフォルトゲートウェイの IP アドレスに直接問い合わせます。各 VLAN で、デフォルトゲートウェイが DNS 問い合わせに応答する必要があります。
- 応答が切り詰められた場合（＝DNS 応答の TC ビットが立った場合のこと）は、TCP 53 番で問い合わせ直します。これは dnspython（＝ツールが DNS 問い合わせに使う Python ライブラリのこと）の既定動作です。
- ICMP Echo のペイロードは 56 バイトです（icmplib の既定値）。
- 端末の IP アドレスを調べるとき、`8.8.8.8` の UDP 80 番宛てにソケットを作ります。ただしパケットは送りません。
- 複合機の Ping テスト、HTTPS 疎通テスト、WhereAmI テスト、結果送信のホスト名は、OS のリゾルバで名前解決します。
- 公共 VLAN 固有のテスト（内部ドメインが解決できないことの確認）は、現在の main では実行しません。プロファイル（＝テストの宛先と閾値を定義したファイルのこと）で、対象が空になっているためです。プロファイルの形式は JSON（＝項目名と値の組でデータを表すテキスト形式のこと）です。

### 3-3. 結果送信時（Airtable）

結果は Airtable の webhook（＝URL に HTTP でデータを送ると処理が動く受け口のこと）に送ります。

| 宛先（ホスト名/IP） | プロトコル | ポート | 方向 | 目的 | 必須/任意 |
|---|---|---|---|---|---|
| `hooks.airtable.com` | HTTPS（POST、JSON） | TCP 443 | 端末→外部 | 各 VLAN のテスト完了直後に結果を 1 件送る（3 VLAN で計 3 件） | 常に送信を試みる。失敗してもテストは続行する |

補足は次のとおりです。

- 送信先 URL は、環境変数 `AIRTABLE_WEBHOOK_URL`、カレントディレクトリの `.env` ファイルの `AIRTABLE_WEBHOOK_URL`、コード内の既定値の順に決まります。
- コード内に既定値があるため、何も設定しなくても送信します。送信を止める設定はありません。
- README には「未設定の場合、Airtable投入はスキップされます」とあります。これは現在の実装と異なります。本書は実装に合わせて記載しています。
- 送信には httpx（＝ツールが HTTP 通信に使う Python ライブラリのこと）を使います。タイムアウトは各段階 30 秒です。段階とは、接続・送信・受信・接続プールの待ちのことです（[HTTPX: Timeouts](https://www.python-httpx.org/advanced/timeouts/)）。
- 最大 3 回試し、間隔は 1 秒、2 秒です。
- 3 回とも失敗した場合は、結果をローカルの JSON ファイルに保存します（4-5 を参照）。
- 送信先が応答せずにパケットを破棄する場合、VLAN ごとに最大で約 93 秒（30 秒 × 3 回 ＋ 待ち 3 秒）待ちます。

### 3-4. 逆方向チェック（SSM probe）

逆方向チェックでは、AWS 上のプローブ（＝ping を実行する確認用サーバーのこと）が、端末と店舗機器に ping を送ります。プローブへの指示には AWS Systems Manager（＝AWS のサーバー管理サービスのこと。略称 SSM）を使います。

現在の main の既定プロファイルでは、逆方向チェックは実行しません。対象（`reverse_check_targets`）が定義されていないためです。この場合、AWS への通信は発生しません。

有効化された場合は、次の条件をすべて満たす VLAN でのみ実行します。

- プロファイルに `ssm_probe` と `reverse_check_targets` がある。
- 端末の IP アドレスが店舗 LAN の範囲（192.168.2.0/23 〜 192.168.128.0/17）にある。POS と公共の範囲はこれに含まれないため、実行されうるのは店舗 VLAN のみです。
- boto3（＝AWS SDK for Python のこと）を読み込める。
- 端末の AWS 認証情報が有効である。無効または無い場合は、メッセージを表示してスキップします。

有効時の通信は 2 種類です。1 つ目は、端末から AWS の各サービスへの HTTPS です。宛先は STS（＝AWS の認証サービスのこと）、SSM、CloudWatch Logs（＝AWS のログ保管サービスのこと）のエンドポイントです。2 つ目は、プローブから端末と店舗機器への ICMP です。この ICMP は、社内 WAN（＝離れた拠点どうしを結ぶ広域ネットワークのこと）を経由します。このほか、boto3 は認証情報が見つからない場合に、既定動作で EC2（＝AWS の仮想サーバーサービスのこと）のメタデータを探します。宛先の `169.254.169.254` はリンクローカルアドレス（＝同じネットワーク内だけで使う特別なアドレスのこと）です。これはツールのコードではなく、boto3 の既定動作です。

| 送信元（誰が・どこから） | 宛先（ホスト名/IP） | プロトコル | ポート | 方向 | 目的 | 必須/任意 |
|---|---|---|---|---|---|---|
| ツール（boto3）、端末から | `sts.ap-northeast-1.amazonaws.com` | HTTPS | TCP 443 | 端末→外部 | AWS 認証情報の確認（1 回） | 有効時のみ |
| ツール（boto3）、端末から | `ssm.ap-northeast-1.amazonaws.com` | HTTPS | TCP 443 | 端末→外部 | プローブへの ping 実行の依頼と、結果の取得（2 秒間隔で最大 60 秒） | 有効時のみ |
| ツール（boto3）、端末から | `logs.ap-northeast-1.amazonaws.com` | HTTPS | TCP 443 | 端末→外部 | 実行結果が 24,000 文字以上の場合のみ、CloudWatch Logs から結果を取得する | 有効時のみ。ping 5 回の結果では通常発生しない |
| boto3、端末から | `169.254.169.254` | HTTP | TCP 80 | 端末→外部 | AWS 認証情報が見つからない場合に、boto3 が既定動作で EC2 のメタデータを探す（タイムアウト 1 秒） | 有効時のみ。発生の有無は要確認 |
| AWS 上のプローブ、社内 WAN 経由 | 端末の IP アドレス | ICMP Echo（5 回） | — | 外部→端末（受信） | 店舗 LAN 側から端末に到達できるかの確認 | 有効時のみ |
| AWS 上のプローブ、社内 WAN 経由 | `rt.s<店舗コード>.yamaokaya.net`、`sw.s<店舗コード>.yamaokaya.net`、`prn.s<店舗コード>.yamaokaya.net` | ICMP Echo（各 5 回） | — | 外部→店舗機器 | 店舗機器への到達確認。名前解決はプローブ側で行う | 有効時のみ |

FW 担当者向けの要点は次のとおりです。

- 逆方向チェックで端末から出る通信は、HTTPS（TCP 443）と、条件付きの `169.254.169.254` への HTTP（TCP 80）だけです。端末は AWS からの TCP / UDP 接続を受け付けません。
- 端末に入ってくる通信は ICMP Echo Request だけです。端末の OS のファイアウォールが受信 ICMP Echo Request を遮断していると、このチェックは FAIL になります。たとえば Windows Defender ファイアウォールは、既定の設定では受信 Echo Request を許可していない場合があります。ツールはファイアウォールの設定を変更しません。
- プローブへの指示の配信は AWS 内で行われます。端末はこの配信に関与しません。
- プローブの送信元 IP アドレスは、本書には記載していません（要確認）。
- 判定は、パケットロス率（＝送ったパケットのうち応答が無かった割合のこと）が 20 % 以下で PASS です。プローブ側がタイムアウトした場合などは ERROR になります。

### 3-5. ネットワーク担当者向けの注意点

- 次の通信は、プロキシを通りません。直接通信の許可が必要です。
  - ICMP
  - DNS 解決テストと店舗 DNS 解決テストの DNS 通信
  - ツール起動時の接続確認（`8.8.8.8` の TCP 53 番）。ツールは TCP ソケットで直接接続し、プロキシの設定を参照しません。失敗すると、ツール全体が終了します。
  - bootstrap.sh の接続確認の代替（`/dev/tcp/8.8.8.8/53` への TCP 接続）。curl / wget で `www.google.com` に接続できない場合、または curl と wget が両方無い場合に使います。
- HTTPS の通信（HTTPS 疎通テスト、WhereAmI テスト、結果送信）は httpx を使います。httpx は環境変数 `HTTPS_PROXY`、`HTTP_PROXY`、`ALL_PROXY`、`NO_PROXY` に従います（[HTTPX: Environment Variables](https://www.python-httpx.org/environment_variables/)）。
- 環境変数が無い場合、Windows ではレジストリのプロキシ設定（`ProxyEnable`、`ProxyServer`）を、macOS ではシステムのプロキシ設定を参照します。これは Python 標準ライブラリの `urllib.request.getproxies()` の動作です（[Python ドキュメント](https://docs.python.org/3/library/urllib.request.html#urllib.request.getproxies)、[CPython のソース](https://github.com/python/cpython/blob/main/Lib/urllib/request.py)、[httpx のソース](https://github.com/encode/httpx/blob/master/httpx/_utils.py)）。
- Windows では PAC（＝プロキシの設定を自動で配る構成ファイルのこと）を使いません。macOS での PAC の扱いは要確認です。
- TLS（＝HTTPS の通信を暗号化し、証明書で接続先を確かめる仕組みのこと）の検証には、CA（＝証明書を発行する認証局のこと）の証明書を使います。httpx は certifi（＝Mozilla 由来の CA 証明書の一覧を収録した Python パッケージのこと）の CA 証明書で TLS を検証します。OS の証明書ストアは使いません。環境変数 `SSL_CERT_FILE` または `SSL_CERT_DIR` がある場合は、そちらを使います（httpx 0.28.1 で確認。[HTTPX: SSL](https://www.python-httpx.org/advanced/ssl/)）。
- そのため、独自の CA で TLS 検査（＝プロキシが HTTPS 通信を復号して中身を検査すること）を行う環境では、HTTPS の通信が証明書エラーで失敗する可能性があります。
- uv は環境変数 `HTTPS_PROXY`、`HTTP_PROXY` に従います（[uv の公式ドキュメント](https://docs.astral.sh/uv/reference/environment/)）。git は環境変数と git の `http.proxy` 設定に従います。
- 逆方向チェックを有効にする場合は、3-4 の受信 ICMP も確認してください。

## 4. ふるまい

### 4-1. 実行の流れ

1. OS を判定します。Windows、macOS、Linux 以外なら終了します。
2. インターネット接続を確認します。`8.8.8.8` の TCP 53 番に接続します（タイムアウト 5 秒）。失敗すると終了します。
3. プロファイルを読み込みます。`profiles/` 内の `*.json` を名前順に読み、先頭のファイルを使います。リポジトリに含まれるのは `profiles/default.json` です。
4. ウィザードで入力します。店舗コード（4 桁の数字）を入力し、WAN 経路（FTTH / LTE）を選びます。確認画面で承認しないと、入力をやり直します。
5. VLAN を「店舗 → POS → 公共」の順にテストします。各 VLAN の前に、接続の切り替えを求める表示が出ます。
6. Enter を押すと、端末の IP アドレスが期待範囲にあるかを確認します。範囲外なら、もう一度切り替えを求めます。IP アドレスを取得できない場合は、確認を省略して進みます。
7. 各 VLAN のテスト（4-2）を順に実行します。
8. 各 VLAN の完了直後に、その VLAN の結果を Airtable に送ります（3-3）。
9. 全 VLAN の終了後、結果のサマリーを画面に表示します。

補足は次のとおりです。

- WAN 経路の選択は、結果に記録するだけです。ツールは WAN 経路を切り替えません。
- Ctrl+C で中断できます。中断前に完了した VLAN の結果は、すでに送信されています。
- テストの処理自体が例外で止まった場合は、画面にエラーを表示して次のテストへ進みます。このとき、そのテストの結果は記録されません。

各 VLAN の期待範囲は次のとおりです。

| VLAN | 端末の IP アドレスの期待範囲 |
|---|---|
| 店舗 | 192.168.2.0/23、192.168.4.0/22、192.168.8.0/21、192.168.16.0/20、192.168.32.0/19、192.168.64.0/18、192.168.128.0/17（192.168.2.0 〜 192.168.255.255） |
| POS | 192.168.1.0/24 |
| 公共 | 172.16.0.0/24 |

### 4-2. テストの内容と合否の判定

判定に使う用語は次のとおりです。RTT（＝パケットを送ってから応答が届くまでの往復時間のこと）は、ping の応答時間です。パケットロス率と、ジッター（＝連続する RTT の差の絶対値の平均のこと）は、安定性テストで使います。

| 順番 | テスト | 対象 VLAN | 内容 | PASS の条件 |
|---|---|---|---|---|
| 1 | DNS 解決 | 全 VLAN | `www.google.com`、`dns.google` の A レコードを問い合わせます。1 件あたり全体で 5.0 秒、1 回の問い合わせは 2.0 秒（dnspython の既定値）で打ち切ります | A レコードを取得できる |
| 2 | Ping 到達性 | 全 VLAN | `8.8.8.8`、`1.1.1.1` に各 1 回送ります。応答待ちは 1000 ms です | 応答があり、RTT が 1000 ms 以下 |
| 3 | 安定性 | 全 VLAN | `8.8.8.8` に 0.2 秒間隔で 25 回送ります（5 秒 ÷ 0.2 秒）。1 回の応答待ちは 2.0 秒です | パケットロス率が 5.0 % 以下、かつジッターが 100 ms 以下 |
| 4 | HTTPS 疎通 | 全 VLAN | 3 つの URL に GET を送ります。リダイレクトに従います。タイムアウトは各段階 10 秒です | 最終応答の HTTP ステータスが 200 |
| 5 | 店舗 DNS 解決 | 店舗 | OS に設定された DNS サーバーに 4 件を問い合わせます。1 件あたり全体で 10.0 秒で打ち切ります | 下の表のとおり |
| 6 | 複合機 Ping | 店舗 | `prn.myshop.yamaokaya.net` に 1 回送ります。応答待ちは 1000 ms です | 応答があり、RTT が 1000 ms 以下 |
| 7 | WhereAmI | 店舗 | `https://api.yamaokaya.net/wb/whereami` に GET を送ります。リダイレクトには従いません。タイムアウトは各段階 10 秒です | 応答 JSON の `shopCode` が、入力した店舗コードと数値として一致する |
| 8 | POS 機器 Ping | POS | `192.168.1.81`、`192.168.1.82`、`192.168.1.110` に各 1 回送ります。応答待ちは 1000 ms です | 応答があり、RTT が 1000 ms 以下 |
| 9 | 逆方向チェック | 条件を満たす VLAN（実際は店舗のみ） | 既定では実行しません（3-4） | パケットロス率が 20 % 以下 |

店舗 DNS 解決テストの判定は次のとおりです。プライベート IP アドレスは RFC 1918（＝プライベート IP アドレスの範囲を定めた規格のこと）の 10.0.0.0/8、172.16.0.0/12、192.168.0.0/16 を指します。NXDOMAIN（＝「その名前は存在しない」という DNS 応答のこと）などの応答は、遮断されたものとして扱います。

| ホスト名 | 期待する結果 | PASS の条件 |
|---|---|---|
| `api.yamaokaya.net` | `private_ip` | 解決でき、プライベート IP アドレスを含む |
| `nx.yamaokaya.net` | `private_ip` | 解決でき、プライベート IP アドレスを含む |
| `pornhub.com` | `nxdomain` | NXDOMAIN、NoAnswer、NoNameservers のいずれか。または応答がすべて `0.0.0.0` |
| `yamaokaya.lightning.force.com` | `resolve_success` | 解決できる |

OS に設定された DNS サーバーを取得できない場合、店舗 DNS 解決テストは 4 件とも FAIL になります。

### 4-3. VLAN ごとの総合判定

- テストの結果は PASS、FAIL、WARNING、ERROR のいずれかです。
- FAIL が 1 件でもあれば、その VLAN の総合判定は FAIL です。
- FAIL が無く WARNING があれば WARNING です。それ以外は PASS です。
- ERROR は総合判定を FAIL にしません。ERROR は逆方向チェックでのみ使います。
- 現在の実装には、WARNING を返すテストはありません。

### 4-4. 所要時間の目安

次の表は、コード上のタイムアウトから求めた上限の目安です。正常時の実測値は要確認です。VLAN の切り替え作業の時間は含みません。

| 処理 | 上限の目安 |
|---|---|
| 起動時の接続確認 | 5 秒 |
| DNS 解決 | 5 秒 × 2 件 |
| Ping 到達性 | 1 秒 × 2 件 |
| 安定性 | 応答が正常なら約 5 秒。応答が無い場合は最大約 55 秒（2.0 秒 × 25 回 ＋ 0.2 秒 × 24 回） |
| HTTPS 疎通 | 各段階 10 秒 × 3 URL |
| 店舗 DNS 解決（店舗 VLAN） | 10 秒 × 4 件 |
| 複合機 Ping（店舗 VLAN） | 1 秒（名前解決の時間を除く） |
| WhereAmI（店舗 VLAN） | 各段階 10 秒 |
| POS 機器 Ping（POS VLAN） | 1 秒 × 3 件 |
| 結果送信（VLAN ごと） | 各段階 30 秒 × 最大 3 回 ＋ 待ち 3 秒 |
| 逆方向チェック（有効時のみ） | 結果の待ち受けが最大 60 秒（対象ごとに並列で実行） |

表の上限には、OS 情報を取得するコマンドの待ち時間を含みません。補足は次のとおりです。

- OS 情報を取得するコマンドは、1 つあたり最大 10 秒で打ち切ります。
- DNS 解決テストでは、デフォルトゲートウェイを調べるために、Windows は `ipconfig` を、macOS / Linux は `ip route show default` を実行します。macOS / Linux で `ip route show default` から取得できない場合は、続けて `netstat -rn` を実行します。
- 店舗 DNS 解決テストでは、DNS サーバーを調べるために、Windows は `ipconfig /all` を、macOS は `scutil --dns` を実行します。Linux は `/etc/resolv.conf` を読むだけで、コマンドは実行しません。
- そのため、DNS 解決テストと店舗 DNS 解決テストのたびに、表とは別にコマンド 1 つあたり最大 10 秒かかる場合があります。

### 4-5. 端末に残るもの

仮想環境（＝このツール専用の Python 実行環境のこと）と uv.lock（＝依存パッケージの版・取得元・ハッシュを記録するファイルのこと）は、リポジトリの中に作られます。uv のキャッシュや Python 本体は、ユーザーのホームディレクトリ配下に置かれます。環境変数 `XDG_CACHE_HOME`、`XDG_DATA_HOME` などを設定している場合は、その場所になります（[uv の公式ドキュメント: Storage](https://docs.astral.sh/uv/reference/storage/)）。Windows では、uv が管理する Python を PEP 514（＝Windows レジストリに Python の導入情報を登録する方式を定めた仕様のこと）に従ってレジストリに登録します（[uv の公式ドキュメント: Python versions](https://docs.astral.sh/uv/concepts/python-versions/)）。

| もの | 場所 | 作られる条件 |
|---|---|---|
| リポジトリ一式（実行時の Python キャッシュ `__pycache__/` を含む） | コマンドを実行したディレクトリの下の `shop-nw-checker/` | 常に |
| 仮想環境 | `shop-nw-checker/.venv/` | 常に |
| ロックファイル | `shop-nw-checker/uv.lock` | 初回の `uv sync` |
| uv 本体 | macOS / Linux: `~/.local/bin/`。Windows: `%USERPROFILE%\.local\bin\` | インストーラーで uv を導入した場合 |
| uv のインストール記録（`uv-receipt.json`） | macOS / Linux: `~/.config/uv/`。Windows: `%LOCALAPPDATA%\uv\` | インストーラーで uv を導入した場合 |
| PATH の設定 | macOS / Linux: `~/.profile`、`~/.bashrc`、`~/.zshrc` などのシェル設定ファイルに追記。Windows: ユーザー環境変数 `Path` に追加 | インストーラーで uv を導入した場合 |
| uv が管理する Python 本体 | macOS / Linux: `~/.local/share/uv/python/`。Windows: `%APPDATA%\uv\data\python\` と、Windows レジストリへの登録（PEP 514） | 端末に Python 3.11 以上が無い場合 |
| uv のキャッシュ | macOS / Linux: `~/.cache/uv/`。Windows: `%LOCALAPPDATA%\uv\cache\` | 常に |
| bootstrap.ps1 の一時ファイル | `%TEMP%\bs.ps1`（実行後に削除） | Windows で実行するたび |
| 結果の JSON ファイル | コマンドを実行したディレクトリの `results/` | Airtable への送信に 3 回とも失敗した場合のみ |
| ログファイル | 作りません。エラーは画面（標準出力・標準エラー出力）に出るだけです | — |

補足は次のとおりです。

- uv 本体、uv が管理する Python 本体、uv のキャッシュの場所は、[uv の公式ドキュメント: Storage](https://docs.astral.sh/uv/reference/storage/) に基づきます。
- インストール記録と PATH の追記先は、2026-10 時点の uv インストーラー（[install.sh](https://astral.sh/uv/install.sh) / [install.ps1](https://astral.sh/uv/install.ps1)）の内容に基づきます。
- 結果の JSON ファイル名は `<日時>_<店舗コード>_<VLAN種別>_<WAN経路>.json` です。日時は UTC（＝協定世界時のこと。日本時間より 9 時間遅れた時刻）の `YYYY-MM-DD_HHMMSS`、VLAN 種別は `店舗` / `POS` / `公共`、WAN 経路は `ftth` / `lte` です。
- 「コマンドを実行したディレクトリ」は、README の手順どおりなら `shop-nw-checker/` の 1 つ上のディレクトリです。

### 4-6. 端末の設定変更

- ツール本体は、OS のネットワーク設定、ファイアウォール、DNS 設定、プロキシ設定を変更しません。
- ツールは OS の情報を読み取るために、次のコマンドを実行します。いずれも読み取りのみです。
  - Windows: `ipconfig`、`ipconfig /all`
  - macOS / Linux: `ip route show default`（無い場合は `netstat -rn`）
  - macOS: `scutil --dns`
  - Linux: `/etc/resolv.conf` の読み取り
- 端末の設定が変わるのは、セットアップ時だけです。対象は git の導入、uv の導入と PATH の追記、Python 本体の導入（Windows ではレジストリ登録を含む）です。

### 4-7. 管理者権限と外部に送るデータ

- 管理者権限の要否は 2-3 を参照してください。
- 外部に送るデータは 5 を参照してください。

## 5. 外部に送信するデータ・送信しないデータ

送信先は `hooks.airtable.com` です（3-3）。逆方向チェックが有効な場合に限り、AWS（3-4）にも送ります。

### 5-1. Airtable に送るデータ

VLAN ごとに 1 件、次の項目を JSON で送ります。

| 項目 | 内容 |
|---|---|
| `store_code` | 入力した店舗コード |
| `vlan_type` | VLAN 種別（店舗 / POS / 公共） |
| `wan_path` | 選択した WAN 経路（FTTH / LTE） |
| `execution_time` | 実行日時（UTC） |
| `profile` | プロファイル名 |
| `overall_status` | 総合判定 |
| `passed_count`、`failed_count`、`warning_count` | PASS / FAIL / WARNING の件数 |
| `local_ip` | 端末のローカル IP アドレス |
| `<テスト名>_status` | テストごとの判定 |
| `<テスト名>_detail` | テストごとの詳細 |

補足は次のとおりです。

- テスト名には宛先のホスト名や IP アドレスが入ります（例: `ping_8.8.8.8`、`dns_www.google.com`）。
- 詳細には次の値が入りえます。RTT、解決時間、解決した IP アドレス（社内ドメインのプライベート IP アドレスを含む）、パケットロス率、ジッター、HTTP ステータス、応答時間、店舗コードの一致の可否、WhereAmI が返した `shopCode`、エラーメッセージです。
- エラーメッセージには、接続先のホスト名や IP アドレスが含まれる場合があります。
- 逆方向チェックが有効な場合は、テスト名にプローブの識別子が含まれます。

### 5-2. AWS に送るデータ（逆方向チェックが有効な場合のみ）

- プローブに実行させる ping コマンドの文字列です。形式は `ping -c 5 <端末の IP アドレス>` または `ping -c 5 <店舗機器のホスト名>` です。
- AWS の API 呼び出しに必要な情報（認証情報による署名など）です。

### 5-3. 送信しないデータ

次のデータは、ツールのコードに収集・送信の処理がありません。

- ユーザー名、PC 名（ホスト名）、MAC アドレス
- OS の種類・バージョン
- ファイルの中身、`.env` ファイルの中身、パスワード類

通信の性質上、送信先のサーバーには、端末（または店舗回線）のグローバル IP アドレスが見えます。

### 5-4. ローカルに保存するデータ

Airtable への送信に 3 回とも失敗した場合は、結果を `results/` に JSON で保存します（4-5）。このファイルは外部に送りません。内容は 5-1 の項目に加えて、テストごとの詳細の元データ（問い合わせた DNS サーバーの IP アドレス、URL など）を含みます。

## 6. パッケージのサプライチェーンの安全性

この章は、サプライチェーン（＝依存パッケージやツールの入手経路のこと）の仕組みと事実だけを記載します。安全性の評価は含みません。

### 6-1. uv.lock の状態

uv.lock は、リポジトリに含まれていません。`.gitignore` で除外しています。

- 端末では、初回の `uv sync` で uv.lock が新しく作られます。
- その時点で、`pyproject.toml` の条件（`>=` の下限のみ）を満たす版が PyPI から選ばれます。開発者の手元と同じ版になるとは限りません。
- 作られる uv.lock には、各パッケージの版、取得元、sha256 ハッシュ（＝ファイルの内容から計算する識別値のこと）が記録されます。
- uv がインストール時にこのハッシュと照合することの公式ドキュメント上の記載は、要確認です。

参考として、開発者の手元の uv.lock（配布物ではありません）で確認した事実を記載します。

- パッケージは 33 件です（ツール本体 1 件、外部 32 件）。
- 外部 32 件の取得元は、すべて `https://pypi.org/simple` です。git・URL・ローカルパスを取得元とする外部パッケージはありません。
- 全件の版が固定されています。sdist（＝ソースコードの配布物のこと）32 件と wheel（＝ビルド済みの配布物のこと）32 件のすべてに sha256 ハッシュがあります。

### 6-2. 直接依存と推移的依存

推移的依存（＝依存パッケージがさらに依存するパッケージのこと）は、uv が自動で解決します。

- 実行時の直接依存（`pyproject.toml` の `dependencies`）は次の 6 件です。上限の指定はありません。
  - `icmplib>=3.0`、`dnspython>=2.6`、`httpx>=0.27`、`rich>=13.0`、`questionary>=2.0`、`boto3>=1.34`
- 開発用グループ `dev` は次の 4 件です。uv は既定で `dev` グループも同期するため、`uv sync` でこれらも導入されます。
  - `hypothesis>=6.100`、`pytest>=8.0`、`pytest-mock>=3.14`、`pytest-asyncio>=0.23`
- 開発者の手元の uv.lock では、実行時の依存が 23 件（直接 6 件、推移的 17 件）、`dev` 関連が 9 件、外部の合計が 32 件です。
- ビルドバックエンド `hatchling`（＝ツール本体をパッケージとして導入するときに使うビルドツールのこと）は、uv.lock に記録されません。ツール本体の導入時に PyPI から取得します。取得する版の決まり方は要確認です。

### 6-3. インストールコマンドの実態

- README の起動コマンド（macOS / Linux）は、`uv sync` と `uv run` を実行します。
- bootstrap.sh は、`uv sync` を実行します。起動コマンドは表示するだけで、`uv run` は実行しません。
- bootstrap.ps1 は、`uv sync` と `uv run` を実行します。
- いずれも `--locked` / `--frozen` を付けていません。
- `uv run` は、既定でコマンドの実行前にロックと環境の同期を行います（[uv の公式ドキュメント](https://docs.astral.sh/uv/concepts/projects/sync/)）。
- uv.lock が `pyproject.toml` と合わない場合は、ロックを再解決します。たとえば `git pull` で依存が追加・変更された場合です。
- 新しい版が PyPI に公開されただけでは、再解決しません。

### 6-4. Python 本体

- uv は、導入済みの Python（uv が管理するもの、または OS 側のもの）で条件を満たすものがあれば、それを使います。無い場合に限り取得します。
- 取得するのは python-build-standalone（＝Astral 社のプロジェクトが配布するビルド済み Python のこと）です。
- 取得元は、uv 0.12.18 で `releases.astral.sh` を確認しました。uv のバージョンによる違いは要確認です。
- 取得時のチェックサム検証の有無は要確認です。

### 6-5. uv 本体とツール本体の入手経路

- uv のインストーラーは `astral.sh` から取得し、そのままシェルで実行します（macOS / Linux は `curl ... | sh`、Windows は `irm ... | iex`）。
- 2026-10 時点の [install.sh](https://astral.sh/uv/install.sh) には、uv の版と配布物ごとの sha256 ハッシュが埋め込まれています。`sha256sum` コマンドがある場合に照合し、無い場合は照合を省略します。
- 2026-10 時点の [install.ps1](https://astral.sh/uv/install.ps1) には、ハッシュを照合する処理が見当たりません。
- bootstrap は、`raw.githubusercontent.com` の main ブランチから取得します。
- 起動のたびに `git pull` で main の最新を取り込みます。bootstrap では、pull に失敗しても既存のコードで続行します。
- 実行するコードは、実行時点の main の内容になります。

### 6-6. パートナー側でできる確認

- 初回の `uv sync` の後、`shop-nw-checker/uv.lock` を開くと、パッケージ名・版・取得元・ハッシュを確認できます。
- `uv tree --project shop-nw-checker` で、依存の一覧を表示できます。なお `uv tree` も、実行前に uv.lock を更新する場合があります。
- uv.lock はリポジトリに無いため、確認できるのは端末で uv.lock が作られた後です。

## 7. 要確認事項

次の項目は、実装や公式資料で確定できていません。

1. Windows で管理者でない場合に、ICMP 系のテスト（Ping 到達性、安定性、複合機 Ping、POS 機器 Ping）が動くか。
2. winget で Git を導入するときに、UAC の確認画面が出るか。
3. Xcode Command Line Tools の取得元ホスト名と、導入時の管理者パスワードの要否。
4. `github.com` のリリースの配布ファイルが `release-assets.githubusercontent.com` にリダイレクトされることの、GitHub の公式資料での記載。
5. uv のバージョンや OS ごとの Python 本体の取得元と、取得時のチェックサム検証の有無。
6. uv がインストール時に uv.lock のハッシュと照合することの公式記載と、hatchling の取得版の決まり方。
7. macOS でプロキシ自動構成ファイル（PAC）を設定している場合の httpx の動作。
8. 正常時の所要時間の実測値。
9. 逆方向チェックのプローブの送信元 IP アドレス。
10. 逆方向チェックを利用するか（端末に AWS 認証情報を用意するか）。
11. 逆方向チェックの有効時に、boto3 が `169.254.169.254` へ接続を試みるか。
