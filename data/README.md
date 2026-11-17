# 緑20枚の撮影・アノテーション

## 撮影フォルダ
高さ h01、撮影セッション s01 / s02 をそれぞれ別フォルダに保存します。

```text
data/raw/green20/top/
├── h01_s01/   # 1回目（既に撮影・リネーム済み）
└── h01_s02/   # 2回目（独立撮影した評価用画像）
```

将来は `h02_s01`, `h02_s02` などを作成できます。TeliViewerで保存する際、**各撮影回は D01～D20 の順**としてください。撮り直しや欠番で順序が変わった場合は、実行前に必ず対応を確認してください。

正しい札番号と順番は `data/metadata/green20_cards.csv` を参照してください。YOLOの緑20クラスはCSV行順の内部ID 0～19、百人一首札番号は 001～100 形式で保持します。

## リネーム

撮影済みの s01 は改名済みのため、再実行不要です。**s02 の20枚を撮影した後**、プロジェクト直下のPowerShellで実行します。

```powershell
uv run python scripts/rename_green20.py --session s02
```

20行の対応を目視確認した後に限り、変更を実行します。

```powershell
uv run python scripts/rename_green20.py --session s02 --apply
```

例: `card_008_top_h01_s02.png` 。デフォルトのリネーム対象フォルダは `top/h01_s02/` です。高さを変更する場合は `--height h02`、例外的なフォルダ配置は `--folder <path>` を指定します。

## 自動アノテーション

```powershell
uv run python scripts/auto_annotate.py --session s01
uv run python scripts/auto_annotate.py --session s02
```

それぞれ `data/annotations/green20_h01_s01/` と `data/annotations/green20_h01_s02/` に `labels/`・`previews/`・`report.csv` を出力します。**元画像は変更されません。**

以前の `data/annotations/green20_h01/` は旧版の出力です。新しいフォルダへ自動移動・上書きされません。新しいプレビューを確認してから扱ってください。

自動アノテーションは仮ラベルです。四隅とバウンディングボックスを各画像で目視確認し、必要な修正を終えてから学習に使ってください。

## 学習と評価

- s01: 学習用の元画像。回転拡張を行う場合は **s01 のみ**から生成
- s02: 独立撮影による評価用候補。回転生成した s01 と混在させない
- 回転拡張した同一元画像を train / val / test にまたがって分割しない
- 元画像・生成データセット・モデル重みは GitHub に含めない（コードとメタデータは管理）
- 今後、別の高さや照明条件、複数札画像も評価対象として増やす
