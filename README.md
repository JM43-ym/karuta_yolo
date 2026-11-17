# karuta_yolo

競技かるたの取り札識別研究。まず五色百人一首の緑20枚を用いて、単札画像でYOLO物体検出モデルを学習し、単札・複数札画像で推論と評価を行います。後に同じ方式で100クラスへ拡張します。

## 環境

Python 3.11 / uv / Ultralytics / CUDA対応PyTorch（GPU環境に応じて設定）。

```powershell
uv sync
uv run yolo checks
```

## 最初に行うこと

1. 緑20枚を D01～D20 の順に、真上から同じ高さで20枚撮影
2. 写真を `data/raw/green20/top/h01/` にコピー（現時点で画像は未登録）
3. `uv run python scripts/rename_green20.py` で**変更予定を確認**
4. 正しく対応していると確認できたときだけ `uv run python scripts/rename_green20.py --apply` を実行

詳しい撮影手順・命名規則・アノテーション計画は [data/README.md](data/README.md) を参照してください。

学習前に独立撮影の検証・テスト画像を追加します。元の写真から増やした回転画像を訓練とテストにまたがって混在させないでください。
