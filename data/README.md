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


## s01 回転拡張 + s02 検証用データセット

s01・s02の画像がリネーム済みで、各セッションの `report.csv` と `labels/` があり、
**全画像の輪郭とクラスを目視確認した後**に実行します。

```powershell
uv run python scripts/generate_rotations.py
```

標準設定でs01の20枚を0～355°（5°刻み、72方向）に回転し、train 1440枚を作成します。
s02の20枚は画像を回転させず、val 20枚としてコピーします。
出力先は `data/datasets/green20_v1/` です。元画像と元アノテーションは変更しません。
空でない出力先がすでに存在する場合は停止します。生成データを作り直す場合に限り、
`uv run python scripts/generate_rotations.py --overwrite` を使ってください
（デフォルト出力フォルダ内の既存生成データは削除されます）。

出力構成：

```text
data/datasets/green20_v1/
├── images/train/   # 1440枚
├── images/val/     # 20枚
├── labels/train/   # 1440件のYOLO Detectラベル
├── labels/val/     # 20件のYOLO Detectラベル
└── data.yaml
```

回転では札が欠けないようにキャンバスを拡張し、四隅座標も同じアフィン変換で回し、
その外接長方形をYOLO Detectの `class x_center y_center width height` に変換します。
元写真・レポート・生成データで札番号が一致するか確認してください。
1440枚のPNG画像には数GB程度の保存容量が必要になる可能性があります。

`data.yaml` 内の `path` は実行したPCの絶対パスです。別PCへ移した場合は更新してください。

**testはこのスクリプトでは作りません。** 自陣・敵陣に複数札を並べ、
札の配置を変えた独立撮影画像に全札の正解BBoxを付けて最終評価します。
testはモデル選択や閾値調整に使わず、最終段階で使用してください。

## 3高さでの学習データセット（green20_v2）

緑の外枠まで統一したアノテーションが次の4セットに揃ったら実行します。
- train: `h01_s01`, `h02_s01`, `h03_s01`（それぞれ20枚）
- val: `h01_s02`（20枚、回転せず保持）
- test: 競技配置の独立写真（学習データセットには組み込まない）

```powershell
uv run python scripts/generate_rotations.py
```

初期設定の5°刻みでは train 4320枚、val 20枚の計4340枚を
`data/datasets/green20_v2/` に新規作成します。
前回の `green20_v1/` は変更しません。
検出した四隅を画像と一緒に回転し、YOLO Detectの外接長方形をラベル化します。
`data.yaml` は新しい出力先の絶対パスを記載します。

すでに `green20_v2` に生成物があるときは実行を停止します。
再生成が必要で、既存のv2を破棄してよい場合だけ `--overwrite` を指定してください。
PNG 4320枚のため、空き容量を十分確保してください。

**元画像・元ラベルが変わった場合、学習用データセットは自動更新されません。**
必ず再生成し、目視確認を行ってから学習してください。
