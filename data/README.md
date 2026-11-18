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

## h03単札＋2/3枚配置の検証（green20_v3）

- train: `green20_v2/images/train` の4,320枚を再利用し、複製しない
- val: `top/h03_s02` の単札20枚と `val/h03/two_cards` 20枚、
  `val/h03/three_cards` 20枚（計60画像・120札）
- 40枚の札番号は `data/metadata/green20_val_layouts.csv` に記録済み。
  撮影順のファイル名 `two_1.png`～`two_20.png` と
  `three_1.png`～`three_20.png` が必要。

```powershell
# h03単札（未リネームなら実行前に名前・順番を確認）
uv run python scripts/rename_green20.py --height h03 --session s02
uv run python scripts/rename_green20.py --height h03 --session s02 --apply
uv run python scripts/auto_annotate.py --height h03 --session s02

# 2枚/3枚配置（密着札の白面候補を左右に対応づけ）
uv run python scripts/annotate_multi_val.py
```

`data/annotations/green20_h03_multi_val/previews/` に40枚分の確認画像、
`report.csv` に検出状態を出力する。必ず各札の外枠と左→右の札番号を確認する。
**FAIL画像はラベルを生成しない。REVIEWも未承認の仮ラベルである。**
札が接している影響で自動検出できない場合は手動修正が必要。

目視確認後に次を実行する。

```powershell
uv run python scripts/build_green20_v3.py
```

生成物は `data/datasets/green20_v3/`（val画像60枚、ラベル60ファイル、
`data.yaml`）である。既存のv2訓練画像とラベルを参照するため、
trainのPNGは再作成しない。v2もv3も手元のPCに必要。
v3出力が既にある場合は、安全のため自動的な削除・上書きはしない。
v2のval20枚は比較用に残す。

## 決まり字付きの推論

`green20_cards.csv` の `decision_prefix` 列を読み、札番号・決まり字・信頼度を
推論結果のPNGおよびCSVに出力する。

```powershell
uv run python scripts/predict_green20.py --model runs/detect/runs/green20/trial_01/weights/best.pt --source data/raw/green20/test/competition --imgsz 1280 --conf 0.25
```

出力先は `runs/green20_labeled/`。札番号と決まり字は推論結果であり、正解の保証はない。
日本語を画像に描くにはPillowとCJKフォント（Windowsならメイリオ等）が必要。

## 競技配置 test の撮影

整列した競技配置と散らし配置はフォルダを分け、モデル設定を決めた後の未使用画像
のみを独立testとして使う。すでに推論に使用した `competition_001.png` は
開発用として扱う。評価には各画像内の全札の正解クラスとBBoxが別途必要。

## v4: 実運用の向きだけで学習する（反転なし）

旧v2/v3では元画像を0～355°まで回転させており、札が逆さまに写る
学習画像も含まれていた。さらに通常のYOLO学習設定では左右反転
`fliplr` が有効になり得る。v4では両方を修正し、
正立方向から-15°～+15°（5°刻み）のみを生成する。
**実際のカメラで180°向きの札も映る場合は、その向きも別途考慮すること。**

```powershell
uv run python scripts/build_green20_v4.py
uv run python scripts/train_green20.py --name trial_04 --epochs 30 --batch 8 --imgsz 640
```

- v4 train: 60元画像 × 7方向 = 420枚（全20クラス、21枚/クラス）
- v4 val: v3の独立撮影60画像、計120札を複製
- `v4/data.yaml` のクラス名は `017（ちは）` など日本語の決まり字付き
- `fliplr=0.0, flipud=0.0, degrees=0.0, shear=0.0, perspective=0.0,
  mosaic=0.0, mixup=0.0, copy_paste=0.0` を学習に明示
- 旧データ・旧モデルを削除・上書きしない

v4は学習画像枚数がv3より大幅に少ないため、学習条件を完全に揃えた
性能比較にはならない。回転方向を適切に制限した影響を観察する
探索実験として扱う。今後は元画像の追加などを検討する。

### 保存される学習記録

通常のYOLOはrunフォルダに `args.yaml`（epochs/batch/imgsz/学習設定）、
`results.csv`（各epochのPrecision、Recall、mAP、損失等）、
`weights/best.pt` と `last.pt`、各種画像を保存する。

新しい `scripts/train_green20.py` ではさらに
`runs/experiment_logs/trial_04_YYYYMMDD_HHMMSS.json` に以下を保存する。
開始日時、終了日時（タイムゾーン付き）、経過秒数、
学習条件、ライブラリバージョン、GPU/CUDA情報の一部、
終了状態、最終epochの評価値、および学習結果metrics。
実行が中断・失敗した場合もログを可能な範囲で残す。

### 決まり字付きの検証画像

v4のvalの正解（GT）とモデルの予測を別々の画像に描く。

```powershell
uv run python scripts/predict_green20.py --model runs/green20/trial_04/weights/best.pt --source data/datasets/green20_v4/images/val --labels-dir data/datasets/green20_v4/labels/val --imgsz 1280 --conf 0.18 --output runs/green20_labeled/trial_04_val
```

`*_pred.png`（オレンジ枠、予測クラスと決まり字・信頼度）、
`*_gt.png`（緑枠、正解クラスと決まり字）、
`predictions.csv` を生成する。
標準のYOLO `val_batch*_pred.jpg` と別の出力であり、標準画像を置き換えない。
Windows環境のメイリオ等、日本語フォントが必要。
