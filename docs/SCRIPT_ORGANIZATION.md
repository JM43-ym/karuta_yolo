# スクリプトの用途別整理（2026-11-24）

## 完了した整理

Pythonの実装本体21ファイルは用途別ディレクトリに移動済みです。**旧 `scripts/<ファイル名>.py` の互換ラッパーは削除済み**です。今後は新しいパスを使用してください。

```text
scripts/
├── annotation/    # 正面・動画・固定角度・複数札のアノテーション、四隅修正、レビュー
├── renaming/      # ファイル名と札番号を対応付ける
├── capture/       # 動画から5フレーム抽出
├── gui/           # pytelicam対応の撮影GUI
├── dataset/       # Train/Valの生成・画像/ラベル検査
├── training/      # YOLO学習
├── inference/     # 推論・フィルタ・履歴・札形状
├── presentation/  # PowerPoint作成
├── toolbox.py             # 用途別入口の共通処理（残す）
└── verify_script_layout.py # 静的検査（残す）
```

学習済みモデル `runs/`、撮影元画像 `data/raw/`、アノテーション `data/annotations/`、生成済データセット `data/datasets/`、研究日誌は移動・削除していません。

## import・パスの修正

- 各モジュール内の依存関係を `from annotation.auto_annotate import ...`、`from dataset.generate_rotations import ...`、`from inference.card_geometry import ...` のように用途別パッケージの参照に変更。
- 実装本体からプロジェクトルートを探すパスは `Path(__file__).resolve().parents[2]` を使用。
- 各フォルダに `__init__.py` を追加。
- `scripts/toolbox.py` および用途別 `main.py` は直接新パスを起動。
- 21個の旧互換ラッパーを削除し、互換ファイルに依存しないよう修正。

## Pull直後の安全確認

研究室PCのVSCodeで、ローカル未コミットの変更がないことを確かめ、GitHubからPullしてください。

```powershell
uv run --no-sync python scripts/verify_script_layout.py
uv run --no-sync python scripts/dataset/dataset_inventory.py --data data/datasets/green20_video_augmented/data.yaml
uv run --no-sync python scripts/inference/predict_green20.py --help
uv run --no-sync python scripts/training/train_green20.py --help
uv run --no-sync python scripts/annotation/annotate_karuta_frames.py --help
uv run --no-sync python scripts/gui/capture_karuta_video.py --help
```

検査・helpでは学習・撮影・データ書き換えを行いません。カメラドライバの接続を伴うGUI本体の撮影テストは別途実施してください。

## 主要コマンド

```powershell
# 札の撮影GUI
uv run --no-sync python scripts/gui/capture_karuta_video.py --color green20 --direction LR

# 動画から抽出
uv run --no-sync python scripts/capture/extract_karuta_frames.py --color green20 --direction LR --per-video 5

# アノテーション・確認
uv run --no-sync python scripts/annotation/annotate_karuta_frames.py --color green20 --direction LR
uv run --no-sync python scripts/annotation/review_karuta_annotations.py --color green20

# 画像リネーム：まずは確認のみ
uv run --no-sync python scripts/renaming/rename_green20_val_angles.py --angle F30 --folder "data/raw/green20/train/single/oblique/h01_s01/F30"

# 既存データセット検査
uv run --no-sync python scripts/dataset/dataset_inventory.py --data data/datasets/green20_video_augmented/data.yaml

# 学習（新規実験として実行するときのみ）
uv run --no-sync python scripts/training/train_green20.py --data data/datasets/green20_video_augmented/data.yaml --epochs 30 --batch 8 --imgsz 640 --name trial_video_aug_02

# 保存済みbest.ptで画像推論
uv run --no-sync python scripts/inference/predict_green20.py --model runs/green20/trial_video_aug_01/weights/best.pt --source data/raw/green20/dev/competition --imgsz 1280 --conf 0.25 --device 0
```

※ 使用しているメーカー専用の`pytelicam`等を保持するため、これまで通り `uv run --no-sync` を使用します。

## 旧コードの復元

変更はGitHubの履歴に残っています。過去の記録・手順に旧パスの記載がある場合は、上記の新パスへ置き換えてください。ローカルで旧互換ラッパーを独自に編集していた場合は、Pull前に差分を確認してください。
