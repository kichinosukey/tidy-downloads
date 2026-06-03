# tidy-downloads

**`~/Downloads` を、いつも同じフォルダ構成に保つ macOS 用 CLI** です。

散らかった PDF・画像・インストーラなどを、拡張子とファイル名から分類して下のようなフォルダへ **移動だけ** します（削除はしません）。実行前にプランを確認でき、適用後は `undo_manifest.json` で戻せます。

```
~/Downloads/
├── documents/
│   ├── notes/          … PDF, メモ, 資料
│   ├── finance/        … 請求書, 領収書
│   └── spreadsheets/   … CSV, Excel
├── media/
│   ├── images/
│   ├── audio/
│   └── video/
├── projects/
│   └── code/           … スクリプト, 設定
├── archives/           … zip など
├── installers/         … dmg, pkg
└── misc/               … その他
```

`plan` で移動案を作り、`run` / `apply` で反映します。分類には Mac 内蔵の AI（[apfel](https://github.com/Arthur-Ficial/apfel)）を使い、ファイルの内容をクラウドに送りません（macOS 26+ / Apple Intelligence が必要）。

## インストール

```bash
curl -fsSL https://raw.githubusercontent.com/kichinosukey/tidy-downloads/v0.1.1/scripts/install.sh | bash
```

`install.sh` の中身は、実行前にブラウザで確認することを推奨します。

インストール後、CLI は `~/.local/bin` に入ります。見つからない場合:

```bash
export PATH="$HOME/.local/bin:$PATH"
tidy-downloads plan --help
```

## 使い方

初回はプランだけ生成（ファイルは動かしません）:

```bash
tidy-downloads plan --target-dir ~/Downloads --fast-lane
```

プランを確認してから適用する場合:

```bash
tidy-downloads run --target-dir ~/Downloads --fast-lane
# 対話プロンプトで apply を選ぶか、即適用なら --yes
```

保存済み manifest から再推論せず適用:

```bash
tidy-downloads apply --manifest ~/.tidy-downloads-runs/<run-id>/manifest.json
```

## 前提

- **macOS 26+**（Apple Intelligence）
- [Homebrew](https://brew.sh/)
- [uv](https://docs.astral.sh/uv/) と [apfel](https://github.com/Arthur-Ficial/apfel)（`install.sh` が未導入分を入れます）
- `apfel --model-info` で `available: yes`

## 開発用（リポジトリを clone した場合）

```bash
git clone https://github.com/kichinosukey/tidy-downloads.git
cd tidy-downloads
uv sync
cp .env.sample .env
./scripts/run_with_apfel.sh plan --target-dir ~/Downloads --fast-lane
```

`uv sync` で `.venv` が作られ、パッケージが editable インストールされます。グローバルに入れる場合は `uv tool install -e .` でも構いません。

## コマンド一覧

| コマンド | 説明 |
|----------|------|
| `plan` | プラン生成（`manifest.json` / `plan.md`） |
| `run` | プラン生成 + 確認後 apply（`--yes` で即 apply） |
| `apply` | 保存済み manifest のみ適用（再推論なし） |

## 定期実行（launchd）

clone 済みのリポジトリで:

```bash
cd /path/to/tidy-downloads
bash scripts/install.sh --with-launchd
```

手動で plist を入れる場合:

```bash
cd /path/to/tidy-downloads
sed -e "s|REPLACE_WITH_REPO_ROOT|$(pwd)|g" -e "s|/Users/REPLACE_ME|$HOME|g" \
  launchd/com.tidy-downloads.fastlane.plist > ~/Library/LaunchAgents/com.tidy-downloads.fastlane.plist
launchctl bootout "gui/$(id -u)/com.tidy-downloads.fastlane" 2>/dev/null || true
launchctl bootstrap "gui/$(id -u)" ~/Library/LaunchAgents/com.tidy-downloads.fastlane.plist
launchctl enable "gui/$(id -u)/com.tidy-downloads.fastlane"
```

ログ: `/tmp/tidy-downloads-fastlane.{out,err}`

## 制限

- **macOS のみ**（apfel / Apple Intelligence が必要）
- **オンデバイス推論のみ**（クラウド LLM API は未対応）
- preset は **`downloads-default` のみ**
- Fast Lane: 拡張子・サイズ・件数に上限あり（詳細は `src/tidy_downloads/presets.py`）

## ライセンス

TBD
