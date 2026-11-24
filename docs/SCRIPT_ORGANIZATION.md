# Pythonスクリプトの用途別フォルダ整理（2026-11-24）

## 概要

**Pythonの実装本体を用途別フォルダへ移動済みです。** 旧 `scripts/*.py` は小さな互換ラッパーに置き換えてあります。以前のコマンドも当面そのまま使用できます。データ・学習済みモデル・実験ログは移動していません。

```text
scripts/
├── annotation/
│   ├── auto_annotate.py               # 正面単札の自動アノテーション
│   ├── annotate_karuta_frames.py      # 動画抽出画像
│   ├── annotate_green20_val_angles.py # 固定角度Val
│   ├── annotate_multi_val.py          # 複数札Val
│   ├── manual_fix_karuta_frames.py    # 4点手動補正
│   └── review_karuta_annotations.py   # レビュー画面
├── renaming/
│   ├── rename_green20.py
│   └── rename_green20_val_angles.py
├── capture/
│   └── extract_karuta_frames.py       # 動画から5フレーム抽出
├── gui/
│   └── capture_karuta_video.py        # pytelicam撮影GUI
├── dataset/
│   ├── build_green20_video_augmented.py
│   ├── build_green20_v3.py
│   ├── build_green20_v4.py
│   ├── generate_rotations.py
│   ├── dataset_inventory.py
│   └── check_green20_paths.py
├── training/
│   └── train_green20.py
├── inference/
│   ├── predict_green20.py
│   ├── card_geometry.py
│   ├── prediction_filter.py
│   └── prediction_history.py
├── toolbox.py                        # 用途別メニューの共通呼び出し
├── verify_script_layout.py          # フォルダ移動の簡易検証
└── （旧ファイル名.py）                # 互換性用の軽量ラッパー
```

## 移動に伴う修正

- 本体にある `Path(__file__).resolve().parents[1]` によるプロジェクト基準パスを、1階層深い移動先に合わせて `parents[2]` へ修正しました。
- 異なる用途のモジュールを読み込めるよう、各本体は従来 `scripts/` 内の互換モジュールを参照できるようにしています。
- `toolbox.py` と用途別 `main.py` は**移動後の実ファイル**を起動します。
- `data/raw/`, `data/datasets/`, `data/annotations/`, `runs/`, `research_diary.csv` は移動・削除していません。
- 既存の各スクリプト内にある旧実行例のパスも、互換ラッパーによって引き続き有効です。

## Windows / PowerShell での操作

まずVSCodeの `karuta_yolo` でGitHubからPullしてください。既存の `.venv` と pytelicamを維持するため、従来どおり `uv run --no-sync` を使用します。

### 1. 移動後の簡易検査（ファイルを変更しません）

```powershell
uv run --no-sync python scripts/verify_script_layout.py
uv run --no-sync python scripts/dataset/main.py inspect --data data/datasets/green20_video_augmented/data.yaml
```

検査で失敗した場合は、学習・推論前にエラー出力を確認してください。

### 2. 推論（新しいパス）

```powershell
uv run --no-sync python scripts/inference/predict_green20.py --model runs/green20/trial_video_aug_01/weights/best.pt --source data/raw/green20/dev/competition --imgsz 1280 --conf 0.25 --device 0 --output runs/green20_labeled/trial_video_aug_01
```

同じ内容を `scripts/inference/main.py predict` からも実行できます。画像フォルダが異なるときは `--source` を変更してください。

### 3. 撮影GUI

```powershell
uv run --no-sync python scripts/gui/capture_karuta_video.py --color blue20 --direction LR
```

または `uv run --no-sync python scripts/gui/main.py camera --color blue20 --direction LR`。

### 4. 画像のリネーム

```powershell
uv run --no-sync python scripts/renaming/rename_green20_val_angles.py --angle F30 --folder "data/raw/green20/train/single/oblique/h01_s01/F30"
```

`--apply --confirm-order` を付ける前に、対応順序を目視確認してください。

### 5. 動画抽出とアノテーション

```powershell
uv run --no-sync python scripts/capture/extract_karuta_frames.py --color green20 --direction LR
uv run --no-sync python scripts/annotation/annotate_karuta_frames.py --color green20 --direction LR
uv run --no-sync python scripts/annotation/manual_fix_karuta_frames.py --color green20 --direction LR
uv run --no-sync python scripts/annotation/review_karuta_annotations.py --color green20
```

### 6. データセット生成・学習

```powershell
uv run --no-sync python scripts/dataset/build_green20_video_augmented.py
uv run --no-sync python scripts/training/train_green20.py --data data/datasets/green20_video_augmented/data.yaml --epochs 30 --batch 8 --imgsz 640 --name trial_video_aug_02
```

データセット生成のコマンドは**確認のみ**です。既存の8,520枚を上書きしません。追加学習を行わない場合、学習コマンドは実行しないでください。

## 注意

旧ファイルが互換ラッパーなので、旧ファイルを削除すると既存のimportや過去の実行手順が壊れる可能性があります。将来の完全なパッケージ化でimportを整理するまでは保持してください。今回GitHub上で静的な移動・パス修正を行いましたが、実際のWindows機・カメラ・GPU環境での動作確認はこれからです。
