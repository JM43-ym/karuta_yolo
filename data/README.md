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

## 共通の学習記録一覧CSV（追加）

`scripts/train_green20.py` の学習が終了すると
`runs/experiment_logs/training_history.csv` に1実験1行で追記する。
Excelで開けるUTF-8 BOM付き。個別JSONと個別CSVも残す。

一覧に保存する項目：学習名、開始・終了時刻、総経過時間、epochs、batch、
imgsz、Precision、Recall、mAP、データセットパス、および
**train/val/test 各splitの画像総数・元画像数・オフライン拡張画像数・札ラベル数**。
trainはh01/h02/h03の画像総数と元画像・拡張画像内訳、
valは単札・2枚・3枚配置の画像数も記録する。

元画像=画像ファイル名に回転接尾辞がないか、回転角度0°の画像。
拡張画像=ファイル名の回転接尾辞が0°以外のもの。
これは保存済みのオフライン拡張画像の内訳であり、学習中にランダムに
行われるaugmentationの発生回数ではない。
現在の専用学習コマンドでは学習時の反転等を無効にしている。

`data.yaml` にtestの指定がないときは、test枚数は**空欄（未設定）**。
競技配置画像で独立に実行した推論枚数と混同しない。
旧実験のログは自動的に一覧へ遡及追記されない。

## 2026-11 更新：個別フォルダを日時付きに統一

`scripts/train_green20.py --name train_05` は実行ごとに
`runs/green20/train_05_YYYYMMDD_HHMMSS/` を作成し、
`weights/best.pt`・`weights/last.pt`・`args.yaml`・`results.csv`・`results.png`
などYOLO標準の生成物と `experiment.json` を同一フォルダ内に保存する。

**全実験の比較は `runs/experiment_logs/training_history.csv`（1回1行）を主とし、個別のサマリーCSVは作成しない。**
学習条件・train/val/test画像数・元画像数・オフライン拡張画像数・ラベル数・時刻・経過時間・精度指標を記録する。
`experiment.json` は中断時の詳細調査用の小さなテキストファイルである。
過去に作成された個別CSVや学習フォルダは自動削除しない。

## 最終保存形式：モデル結果は簡潔なフォルダ名

`uv run python scripts/train_green20.py --name trial_05 ...` で学習すると、
モデル・YOLO標準の結果は **`runs/green20/trial_05/`** に保存する。
日時はこのフォルダ名には付けない。

個別ログだけを **`runs/experiment_logs/trial_05_YYYYMMDD_HHMMSS/experiment.json`**
に保存し、全実験比較の **`runs/experiment_logs/training_history.csv`**
にも1行追加する。個別概要CSVは作らない。
既に同名のモデル結果フォルダがある場合は、モデルを誤って上書きしないよう
学習を停止する。別の実験名を指定すること。

## 360°回転拡張（5°刻み）・鏡面反転なし

最新の標準学習は **`green20_v3/data.yaml`** を使用する。
v3のtrainはv2の画像を参照しており、元写真60枚（h01/h02/h03×20枚）
それぞれを 0°, 5°, 10°, ..., 355° の72方向に回転した**4320枚**が対象。
0°は元画像相当の1枚で、残り71枚は回転拡張画像：
元画像相当60枚＋回転拡張4260枚。
v3のvalは60画像（単札20、2札20、3札20）で変更しない。
これらの回転は**幾何学的回転**であり、鏡面反転（左右反転・上下反転）は含まない。

`scripts/train_green20.py` は学習時の `fliplr=0` と `flipud=0`
を明示するため、YOLO側でも鏡面反転を行わない。
学習中の追加ランダム回転は `degrees=0` とし、
保存済み5°刻み回転のみ利用する。学習時のmosaic等も無効化。

```powershell
uv run python scripts/train_green20.py --name trial_06 --epochs 30 --batch 8 --imgsz 640
```

**既存のv4（±15°・420枚）は削除せず比較用に保持する。**
既存のtrial_05などの学習結果も保持する。
新規実験は未使用の名前を指定する。

## 札の実寸52×73mmを利用した四隅・縦横比の診断

競技かるた札の実寸を短辺52mm、長辺73mmとして
短辺÷長辺 = **0.712329** を期待値とする。
YOLO Detectの矩形は画像の水平・垂直方向に沿っており、札の回転で
見かけの比率が変わるため、YOLOの矩形比を直接この値に一致させない。

推論時に `--check-geometry` を付けると、
元画像の白い札面候補から回転矩形（4頂点）を推定し、
緑の外周を概算する拡張を加えてから、各YOLO枠と重なり具合を比較する。
以下の3状態を保存する。

- `OK`：四隅候補がYOLO枠と重なり、比率誤差が既定の15%以内
- `RATIO_CHECK`：重なる四隅候補はあるが、比率の誤差が大きい
- `NOT_FOUND`：対応する四隅候補を十分な重なりで確認できなかった

```powershell
uv run python scripts/predict_green20.py --model runs/green20/trial_06/weights/best.pt --source data/raw/green20/test/competition --imgsz 1280 --conf 0.10 --check-geometry --output runs/green20_labeled/trial_06_geometry
```

追加出力：
- `competition_001_geometry.png` など：推定四隅と診断結果を描画
- `geometry_report.csv`：予測札番号、信頼度、測定比率、期待比率、誤差、重なり、推定四隅

既存の `*_pred.png` および `predictions.csv` も保存する。
四隅の推定は白面抽出に依存し、密着・暗部・反射・透視変形などで
`NOT_FOUND` や不正確な結果が生じる場合がある。
この診断はあくまで追加の幾何的な指標であり、
YOLOの予測クラスを訂正したり、元のBBoxや学習データを改変しない。
