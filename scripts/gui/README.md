# 撮影GUI

実装本体: `scripts/gui/capture_karuta_video.py`（旧 `scripts/capture_karuta_video.py` は互換ラッパー）

```powershell
uv run --no-sync python scripts/gui/capture_karuta_video.py --color green20 --direction LR
uv run --no-sync python scripts/gui/main.py camera --color blue20 --direction FB
```

BU160MCF系カメラと `pytelicam` が必要です。メーカー専用パッケージは再同期で失われる可能性があるため、既存環境では `--no-sync` を使用します。撮影前に接続状態と保存先、同名ファイルの扱いを確認してください。
