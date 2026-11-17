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
