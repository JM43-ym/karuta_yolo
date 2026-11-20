# 五色百人一首：動画撮影・フレーム抽出・アノテーション

## 基本方針

- 100札を5色（`blue20`、`pink20`＝赤、`yellow20`、`green20`、`orange20`）で管理する。
- 各色の `data/metadata/<color>_cards.csv` は競技かるた番号 `card_id` 昇順。色内番号 `group_id` も01〜20の連番（青A、赤B、黄C、緑D、橙E）。
- 1札につきLR（左右）・FB（前後）を1本ずつ撮影。緑20枚の従来の札番号対応は変更していない。
- 抽出はカメラの移動速度を考慮して**画像の変化量・鮮明さ**から既定で5枚選択する（角度を厳密に推定するものではない）。
- **動画用アノテーションは`scripts/annotate_karuta_frames.py` の1種類に統一**。緑の縁を優先し、反射や台形を考慮した四隅推定を行う。失敗画像だけ手動修正する。
- 従来の緑20クラス用モデル、既存の学習データセット`green20_v2/v3/v4`は別物として保持。100クラスYOLOのクラスIDは`card_id - 1`（001→0、100→99）。

## 使用するスクリプト

| ファイル | 用途 |
|---|---|
| `scripts/capture_karuta_video.py` | カメラ映像をLR/FB録画（GUI操作可、ガイド比率初期値0.52） |
| `scripts/extract_karuta_frames.py` | 動画からフレーム抽出 |
| `scripts/annotate_karuta_frames.py` | 緑の外枠・台形を検出し、YOLOラベルと確認画像を出力 |
| `scripts/manual_fix_karuta_frames.py` | ラベル未作成の画像の四隅をクリックして補修 |
| `scripts/review_karuta_annotations.py` | 札番号順にLR/FBを一覧表示するHTML作成 |

※ `scripts/auto_annotate.py` は以前の**真上画像・緑20クラス**用に残す。動画用スクリプトとは別の目的なので削除しない。

## Windowsでの実行方法

はじめにVSCodeでPullして更新してください。メーカーの`pytelicam`ホイールを別途インストールしているため、以下は`uv run --no-sync`で統一します。

色の指定は`green20`を`blue20`、`pink20`、`yellow20`、`orange20`に置き換えて同様に実行できます。

### ① 動画撮影（撮影済みなら不要）

```powershell
uv run --no-sync python scripts/capture_karuta_video.py --color green20 --direction LR
uv run --no-sync python scripts/capture_karuta_video.py --color green20 --direction FB
```

録画ウィンドウのボタン：PREVIOUS / START REC（録画中STOP/SAVE）/ NEXT / QUIT。
従来のR・N・P・Q・Escキーでも操作可。ガイド・ボタンは元動画には入りません。

### ② 動画からフレーム抽出

```powershell
uv run --no-sync python scripts/extract_karuta_frames.py --color green20 --direction LR --per-video 5
uv run --no-sync python scripts/extract_karuta_frames.py --color green20 --direction FB --per-video 5
```

出力先：
`data/raw/<color>/train/single/oblique/extracted/h01_s01/LR/` と `FB/`。
元動画は`data/raw/<color>/train/single/oblique/videos/h01_s01/`に保持し、既存の抽出画像は通常上書きしません。

### ③ 自動アノテーション

```powershell
uv run --no-sync python scripts/annotate_karuta_frames.py --color green20 --direction LR
uv run --no-sync python scripts/annotate_karuta_frames.py --color green20 --direction FB
```

出力：
```text
data/annotations/video_frames/<color>/h01_s01/
  LR_annotated/
    labels/
    previews/
    rectified/
    annotation_report.csv
  FB_annotated/
    labels/
    previews/
    rectified/
    annotation_report.csv
```

旧`LR_v3`または`FB_v3`フォルダが存在し、正式版フォルダがまだ存在しない場合は、**実行時にフォルダ名を自動移行**します。すでに作成・修正済みのラベルを無断で上書きしません。正式版と旧版の両方が存在する場合は旧版を自動削除しません（内容確認が必要）。旧`LR`/`FB`のアノテーションは初期版なので正式版とは別です。

### ④ 失敗した画像だけ手動補修

```powershell
uv run --no-sync python scripts/manual_fix_karuta_frames.py --color green20 --direction LR
uv run --no-sync python scripts/manual_fix_karuta_frames.py --color green20 --direction FB
```

四隅をクリックした後、`S`で保存、`R`でやり直し、`N`でスキップ、`Q`またはEscで終了。すでにラベルがある画像は対象外です。自動検出結果がずれている場合は、学習前に個別に確認・修正が必要です。

### ⑤ 確認用HTMLを作成

```powershell
uv run --no-sync python scripts/review_karuta_annotations.py --color green20
start data/annotations/video_frames/green20/review_gallery.html
```

`REVIEW`は未承認、`FAIL`は検出不能。射影補正プレビューの比率は**52:73を指定して変換したもの**なので、正しい検出の証拠にはなりません。外枠・文字のゆがみ・札番号を必ず目視確認してください。

## 注意事項

- **撮影済みAVI、元画像、既存の緑20クラス学習データは削除しない。**
- 過去のアノテーション版（v1/v2/v4）のスクリプトはGitHubから削除したが、ローカルの`data/annotations/video_frames/`内に残る旧フォルダは、内容確認・バックアップ後に整理すること。誤って新しい`LR_annotated`/`FB_annotated`を消さないこと。
- 既存の抽出PNGを変更すると、付随するアノテーションがずれるため、抽出やり直し前に別途バックアップする。
- 1本の動画から得た画像をtrainとval/testに分けない。最終学習用の100クラスデータセットへの組み込みは**全件レビュー後**に行う。

## 次の緑20クラス学習：Val固定角度画像のリネーム

学習セット目標：Train 8,520枚（LR 100、FB 100、s01正面20を3倍率で拡張。LR/FBは−15～+15°を5°刻み、正面は0～355°を5°刻み）。Val 180枚（以前のL/R/F/B 30°・45°を各20枚、別撮影s02正面20枚）。**Valに回転・拡縮は適用しない。** 現時点では予定枚数であり、元画像・アノテーション・倍率実測値の確認前に自動生成したものではない。

各固定角度の画像がまだリネームされていない場合は `scripts/rename_green20_val_angles.py` を使用。フォルダは**ローカルの実際の保存先**を `--folder` に指定する。

```powershell
# F30の例。実際のフォルダパスに置き換える
uv run --no-sync python scripts/rename_green20_val_angles.py --angle F30 --folder "data/raw/green20/val/single/oblique/F30"
# 20枚の並びが緑D01～D20で正しいことを画像で確認した後のみ
uv run --no-sync python scripts/rename_green20_val_angles.py --angle F30 --folder "data/raw/green20/val/single/oblique/F30" --apply --confirm-order
```

角度は `L30 L45 R30 R45 F30 F45 B30 B45` の8種類。同一スクリプトで任意の1角度を扱う。**ファイル名の自然順がD01～D20と一致するという仮定**で名称案を出すだけで、画像内容から札番号を識別するわけではない。順序が違う場合は `--apply` しない。既存ファイルへの上書きは禁止している。リネームが終わったら各角度に対応するYOLOラベルを目視確認のうえで用意する。

**s02正面画像について**：以前の`generate_rotations.py`は `h01_s02` があればそれを、なければ `h03_s02` を参照する。正面写真の保存場所と既存アノテーションを確認したうえで採用する。

**倍率について**：h01/h02/h03の札の画像内の見かけの寸法から倍率を求める。値が確認できないうちは仮の倍率でデータセットを生成しない。元のTrain/Valを分離してからTrainのみ拡張し、Testは学習に使用しない。
