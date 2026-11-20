# karuta_yolo

競技かるた取り札のYOLO画像識別研究。最初は五色百人一首の緑20枚を用い、その後100クラスに拡張します。

## 環境

Python 3.11 / uv / Ultralytics / CUDA対応PyTorch。

```powershell
uv sync
uv run yolo checks
```

## 撮影データ構成

```text
data/raw/green20/top/
├── h01_s01/   # 撮影1回目（学習用）
└── h01_s02/   # 撮影2回目（評価用候補）
```

**s01 の撮影・リネームは完了済み。** s02 撮影後の手順は以下です。

```powershell
# リネームの確認（変更なし）
uv run python scripts/rename_green20.py --session s02
# 内容を確認してから実行
uv run python scripts/rename_green20.py --session s02 --apply

# セッションごとにアノテーション
uv run python scripts/auto_annotate.py --session s01
uv run python scripts/auto_annotate.py --session s02
```

アノテーションはそれぞれ `data/annotations/green20_h01_s01/` と `green20_h01_s02/` に別保存されます。生成ラベルは学習前に必ず目視確認してください。

詳しくは [data/README.md](data/README.md) を参照してください。同一写真を回転生成して学習・評価の両方へ混ぜないようにしてください。

## 研究日記と実行時刻ログ

- `research_diary.csv` は研究日記用の一覧です（Excelで開けるUTF-8 CSV）。列は「日付、開始時刻、終了時刻、作業内容、詳細、情報源、関連ファイル・コミット」。作業内容と時刻を確認してから追記してください。ChatGPTに要約を依頼した場合も、会話やGitHubから確認できない時刻は推測しないでください。
- 日記のCSVはGitHubで管理できます。別PCで作業するときは先にPullし、編集後にCommit/Pushしてください。
- YOLO学習は `uv run python scripts/train_green20.py --name trial_04 --epochs 30 --batch 8 --imgsz 640` で開始・終了時刻などを `runs/experiment_logs/` に保存します。
- 決まり字付きの推論は従来どおり `uv run python scripts/predict_green20.py --model <best.ptへのパス> --source <画像またはフォルダ>` で実行でき、`runs/experiment_logs/predict_YYYYMMDD_HHMMSS_ffffff.csv` に開始・終了日時、経過時間、状態、実行コマンドを追加保存します。推論失敗・中断時も可能な範囲で記録します。
- `runs/` はGit管理対象外です。実行ログはローカルPCに残るため、必要なものは別途バックアップしてください。研究日記のCSVとは自動同期されません。

## 動画撮影した100札のアノテーション

動画アノテーションの旧試作版は整理し、緑縁・台形検出の方式に一本化しました。以下の3スクリプトが標準の流れです。

```powershell
uv run --no-sync python scripts/annotate_karuta_frames.py --color green20 --direction LR
uv run --no-sync python scripts/annotate_karuta_frames.py --color green20 --direction FB
uv run --no-sync python scripts/manual_fix_karuta_frames.py --color green20 --direction FB
uv run --no-sync python scripts/review_karuta_annotations.py --color green20
```

5色とも`--color`を置き換えて使用できます。詳細は [動画撮影・アノテーション手順](docs/VIDEO_CAPTURE.md) を参照してください。撮影動画や学習済みの既存緑20クラス用モデルはそのまま保持します。
