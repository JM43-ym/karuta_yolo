# scripts 用途別整理（安全な第一段階）

## 方針

既存コードは相互に `from auto_annotate import ...` 等で参照し合っています。学習結果や注釈を壊さないため、**既存のスクリプトを移動せず**、まず用途別フォルダに実行用の入口（`main.py`）を作成しました。既存のコマンド・ファイル名はそのまま使用できます。

```text
scripts/
├── annotation/main.py    # 正面・動画・固定角度アノテーション、四隅修正、確認
├── renaming/main.py      # 札番号リネーム・固定角度画像リネーム
├── capture/main.py       # 動画から5フレーム抽出
├── dataset/main.py       # 学習データセット生成・枚数検査
├── training/main.py      # YOLOの学習
├── inference/main.py     # YOLOの静止画像推論
├── gui/README.md         # 撮影GUIの将来的な移行場所
├── toolbox.py            # 上記入口の共通呼び出し処理
└── （従来の実装.py）      # 互換性のため現状維持
```

## 用途別の新しいコマンド例

いずれも `uv run --no-sync` を使用し、環境の再同期を避けます。

### アノテーション
```powershell
uv run --no-sync python scripts/annotation/main.py top --height h01 --session s01
uv run --no-sync python scripts/annotation/main.py video --color green20 --direction LR
uv run --no-sync python scripts/annotation/main.py fixed --review
uv run --no-sync python scripts/annotation/main.py manual --color green20 --direction FB
uv run --no-sync python scripts/annotation/main.py review --color green20
```

### 札番号リネーム
```powershell
uv run --no-sync python scripts/renaming/main.py top --session s02
uv run --no-sync python scripts/renaming/main.py fixed --angle F30 --folder "data/raw/green20/train/single/oblique/h01_s01/F30"
```

### 動画抽出
```powershell
uv run --no-sync python scripts/capture/main.py frames --color green20 --direction LR
```

### データセット
```powershell
uv run --no-sync python scripts/dataset/main.py inspect --data data/datasets/green20_video_augmented/data.yaml
```

### 学習
```powershell
uv run --no-sync python scripts/training/main.py train --data data/datasets/green20_video_augmented/data.yaml --epochs 30 --batch 8 --imgsz 640 --name trial_video_aug_02
```
既存の `trial_video_aug_01` の結果を上書きしないよう、新しい実験名を指定してください。実際に追加学習するときのみ実行します。

### 推論
```powershell
uv run --no-sync python scripts/inference/main.py predict --model runs/green20/trial_video_aug_01/weights/best.pt --source data/raw/green20/dev/competition --imgsz 1280 --conf 0.25 --device 0 --output runs/green20_labeled/trial_video_aug_01
```

## 次の段階（既存コードを実際に移動する場合）

本体の移動はまだ行っていません。GUI・他のスクリプトも含めて全ファイル一覧を確認してから、相互 import と ROOT の親階層、READMEのコマンド、GitHub上の既存履歴などを同時に整える必要があります。段階的な移行完了までは、古い実行コマンドも使える設計を維持します。
