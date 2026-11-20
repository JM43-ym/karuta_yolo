# BU160MCF：五色百人一首の動画撮影・抽出・ラベル作成

## 決定した管理方式

- 撮影用のraw画像は五色ごと：`green20`, `blue20`, `pink20`（赤/B）, `yellow20`, `orange20`
- 単札の真上画像は `h01_s01` の1条件
- 斜め画像は「左右に往復する LR」と「手前・奥に往復する FB」の **2動画/札**
- 色内番号（例：A01）と競技かるたの札番号（例：003）は `data/metadata/<color>_cards.csv` で対応
- 連続動画から複数の見え方を抽出するが、**抽出フレームに正確な角度は付けない**
- 既存の緑20札30°/45°実写は、学習に使わない独立セットであれば評価に利用できる
- 現在の`green20_v2/v3/v4`と学習済みモデルは変更しない。新しい抽出画像を学習へ組み込むには、レビュー後に別のデータセットを生成する工程が必要

## フォルダ（すべての色で共通）

```text
data/raw/blue20/
  train/
    single/
      top/h01_s01/                              # karuta_1.png など単札実写
      oblique/
        videos/h01_s01/
          LR/                                    # karuta_01_LR.avi ...
          FB/                                    # karuta_01_FB.avi ...
        extracted/h01_s01/
          LR/                                    # card_003_LR_h01_s01_f000090.png ...
          FB/
    multi/{scattered,touching}/
    conditions/{lighting,background}/
  val/                                         # 独立撮影画像
  test/                                        # 最終評価用の未使用画像
  dev/competition/                             # 改善中に参照する画像
data/annotations/video_frames/blue20/h01_s01/
  LR/{labels,previews,annotation_report.csv}
  FB/{labels,previews,annotation_report.csv}
```

古い `L30/L45/R30/R45/F30/F45/B30/B45` は新規撮影には使用しない。既存の緑の角度固定実写はバックアップと評価方針を確認して別に保管すること。

## 事前準備（Windows）

1. 東芝テリー公式サイトから **TeliCamSDK** を導入、TeliViewerで BU160MCF が映ることを確認
2. 公式の **pytelicam** Windows / Python 3.11 用 wheel を入手。カメラの接続・ストリーミング確認は使用者のPCで実施
3. `uv sync` で既存の仮想環境を同期。公式wheelがローカルにある場合、例：

```powershell
uv pip install "C:\path\to\pytelicam-<version>-cp311-cp311-win_amd64.whl"
```

実際のwheelファイル名に置き換えること。pytelicamはメーカーSDKのため、通常の依存リストに勝手に追加していない。メーカーwheelを仮想環境へ直接追加した後は、`uv run --no-sync` を使う（通常の`uv run`は環境を再同期する場合がある）。**TeliViewerとPythonアプリが同時にカメラを開くと競合する場合があるので、撮影前にTeliViewerを閉じる。**

公式資料： https://www.toshiba-teli.co.jp/products/industrial-camera/software-telicamsdk.htm

## 1. 動画を撮影する

```powershell
uv run --no-sync python scripts/capture_karuta_video.py --color blue20 --direction LR
uv run python scripts/capture_karuta_video.py --color blue20 --direction FB
```

画面にはCSVの順番にA01/003などを表示する。20枚をA01→A20順に撮る。

操作：
- `R`：録画開始/停止（札を固定してカメラを左→右、または手前→奥へゆっくり動かす）
- `N`：次の札（録画停止後のみ）
- `P`：前の札
- `Q` / `Esc`：終了

1枚につきLR1本、FB1本。動画が存在する場合は上書きせず撮影を開始しない。
途中の札から始める例：

```powershell
uv run python scripts/capture_karuta_video.py --color blue20 --direction LR --start 6
```

動画はMJPG形式のAVIで保存し、フレーム数・日時・撮影秒数を `capture_index.csv` に記録する。
`--fps 15` は**動画ファイルの再生FPS**であり、実際の取得FPSの保証ではない。実取得の目安はCSVの `observed_fps` を確認。カメラの露光・ゲインはSDK側で設定したものを使用する。

撮影動画が録画途中で中断された場合は、不完全ファイルの可能性があるため再生してから採用する。

## 2. 動画から数フレームを抽出する

```powershell
uv run --no-sync python scripts/extract_karuta_frames.py --color blue20 --direction LR --per-video 5
uv run python scripts/extract_karuta_frames.py --color blue20 --direction FB --per-video 5
```

各動画の中央付近の**映像変化量を累積**し、変化が均等に分布する位置からピントの合ったフレームを優先する（Laplacian分散）。これにより、撮影速度が異なる場合も「撮影時間が長い箇所だけに抽出画像が偏る」問題を軽減する。真の撮影角度を測定するわけではない。\n\n初期値は動画1本あたり5枚、解析間引きは1フレーム（`--sample-every 1`）。素早いスイープでも取りこぼしにくい設定。
輪郭候補が写っている画像を優先するが**札が正しく撮れている保証はない**。抽出後は手・文字のブレ・札の欠け・過剰な類似を目視確認する。

抽出画像は `card_003_LR_h01_s01_f000090.png` のように保存される。
CSV `extraction_report.csv` に札番号、元動画、抽出フレーム番号、鮮明さ等を保存。元動画は変更しない。既存の抽出ファイルは上書きしない。抽出し直したい場合は`--replace`を指定できるが、**旧ラベルが残って不一致になる可能性がある**ため、既存のアノテーションを退避し、再アノテーション・再確認してから使用する。

## 3. 仮アノテーション

```powershell
uv run --no-sync python scripts/annotate_karuta_frames.py --color blue20 --direction LR
uv run python scripts/annotate_karuta_frames.py --color blue20 --direction FB
```

既存の `scripts/auto_annotate.py` の輪郭検出処理を再利用する。
`data/annotations/video_frames/<color>/h01_s01/<direction>/` に
- `labels/`：YOLO Detectラベル（暫定）
- `previews/`：枠確認用の画像
- `annotation_report.csv`：状態 `REVIEW` / `FAIL` / `SKIPPED_EXISTING_LABEL`

を保存する。既存ラベルを**自動で上書きしない**。

統合100クラスの暫定クラスIDは `card_id-1`（001→0、100→99）。
現在の緑20専用クラスIDとは異なるため、既存 `green20_v3` などに混ぜないこと。

`REVIEW` は**自動生成したままで未承認**。全フレームについて枠、札番号を目視確認し、誤検出は手動修正してから学習に使用する。

## 撮影・評価の注意点

- trainの動画から抽出した別フレームをval/testへ混ぜない
- 緑の既存角度固定の実写をval/testとして使うときは、同じ元画像・同じセッション由来の動画をtrainに入れない
- 動画のフレームごとの見え方は角度センサーなしでは正確な度数を決められない
- 真上h01画像を縮小してh02/h03を模擬する工程は**今回の撮影プログラムにはまだ実装していない**
- BU160MCF実機がこの実行環境にないため、pytelicam接続・実際の録画FPS・露光の適正値はPCで確認する必要がある

### 初期位置ガイド枠（2026-11-20追加）

プレビューの中央に、競技かるた札の寸法比 **52 mm : 73 mm** の緑色ガイド枠と中心十字を描画する。
- `--direction LR`：札を**縦長**に置くガイド
- `--direction FB`：札を**横長**に置くガイド
- ガイド枠は**表示専用**で、録画ファイルには書き込まれない
- 枠の長辺はプレビュー高さの50%（初期値）。サイズ調整例：
  `uv run --no-sync python scripts/capture_karuta_video.py --color green20 --direction LR --guide-scale 0.60`
- `--guide-scale` の範囲は `0.10` ～ `0.85`。枠は札の**初期配置の目安**で、札の位置や角度を自動的に認識して追跡するものではない

### GUI操作ボタン

撮影ウィンドウの映像の下に、**PREVIOUS / START REC（録画中は STOP / SAVE）/ NEXT / QUIT** の4ボタンを表示する。マウスクリックで操作でき、従来の `P/R/N/Q/Esc` キーも使用可能。

- **PREVIOUS**：前の札へ（録画中は無効）
- **START REC**：現在の札の動画撮影開始
- **STOP / SAVE**：録画停止、AVIファイル保存およびCSVへの撮影記録
- **NEXT**：次の札へ（録画中は無効）
- **QUIT**：終了。録画中は先に STOP / SAVE を押すこと
- 表示ボタン・ガイド枠・テキストは**プレビュー専用**。録画ファイルに含まれない
- 札ガイド枠のデフォルトは実測に合わせて `--guide-scale 0.52`

Windowsの画面サイズによって下部ボタンが画面外に隠れるときは、起動時に `--preview-width 800` などを指定する。元動画の解像度には影響しない。

## 緑20枚：動画の抽出とアノテーション確認

次の操作は**カメラを接続せずに**行える（事前にLR/FB録画済みのAVIが必要）。

```powershell
# ① 動画の撮影速度の違いを考慮して、見え方と鮮明さで抽出
uv run --no-sync python scripts/extract_karuta_frames.py --color green20 --direction LR --per-video 5
uv run --no-sync python scripts/extract_karuta_frames.py --color green20 --direction FB --per-video 5

# ② 全フレームを仮アノテーション（100クラス番号、card_id - 1）
uv run --no-sync python scripts/annotate_karuta_frames.py --color green20 --direction LR
uv run --no-sync python scripts/annotate_karuta_frames.py --color green20 --direction FB

# ③ LR/FBを札ごとに一覧表示するHTMLを生成
uv run --no-sync python scripts/review_karuta_annotations.py --color green20

# ④ ブラウザで確認画面を開く（Windows）
start data/annotations/video_frames/green20/review_gallery.html
```

確認ページは札番号（D01→D20）の順にLR・FBプレビューを並べ、YOLO矩形・四隅・対象札の有無を一覧確認できる。プレビューがない画像、ラベルがない画像、FAILは分かるように表示する。**HTMLは閲覧専用であり、修正・承認操作は行わない**。

レポート：
- `data/raw/green20/train/single/oblique/extracted/h01_s01/{LR,FB}/extraction_report.csv`
- `data/annotations/video_frames/green20/h01_s01/{LR,FB}/annotation_report.csv`

注意：古い手動修正済みラベルを上書きしない仕組み。抽出条件変更によってPNGだけ差し替わった場合は、ラベルとプレビューが一致しなくなるため再処理・全件再確認が必要。最新コードで撮影した元動画はそのまま保持する。少数の札でプレビューと元動画を見比べて、スイープ両端が撮れているか確かめる。

**品質基準**：札全体が映っている・文字がブレていない・フレーム間で異なる見え方・枠が緑の外縁を適切に囲う・色内番号と札番号が一致。未確認ラベルは学習に投入しない。

## CSVの並び順・撮影順（2026-11-20更新）

5色すべての `data/metadata/<color>_cards.csv` は**競技かるた札番号 `card_id` の昇順**。また、`group_id` も同じ順番で01〜20の連番になるよう再設定した。青=A、赤（pink20）=B、黄=C、緑=D、オレンジ=E。

**緑20枚は撮影済みのため、従来の `D01〜D20` と競技かるた番号の対応を一切変更していない。**

- 青：`A01=003`, `A02=005`, `A03=006` … `A20=100`
- 赤：`B01=001`, `B02=004`, `B03=013` … `B20=097`
- 黄：`C01=002`, `C02=007`, `C03=010` … `C20=096`
- オレンジ：`E01=019`, `E02=021`, `E03=025` … `E20=099`

動画のファイル名 `karuta_01_LR.avi` は、この**新しい色内番号01**の札を意味する。撮影GUI・フレーム抽出プログラムはCSVを`group_id`順に扱い、番号01〜20と札番号を正しく対応づける。

**注意**：色内番号変更前に撮影した青・赤・黄・オレンジの動画がもしあれば、その動画の札番号が新対応表と一致するか確認し、必要なら整理してから抽出すること。緑動画は影響なし。

緑20クラスの既存モデルは`D01〜D20`順のクラスID 0〜19を維持し、新しい100クラス用`class_id = card_id - 1`と混同しない。

## 反射・台形対応の仮アノテーション改善版（v2）

蛍光灯などの白い反射を札と誤検出したり、斜め映像で台形の札を取り損なう問題への対応として、独立した `scripts/annotate_karuta_frames_v2.py` を追加。**既存v1のラベルやプレビューは変更しない。** v2は撮影時の中央配置を前提としてROIを中央寄りに絞り、HSVの**緑の縁**を優先して札を探索する。凸四角形を推定できれば四隅を保持し、四点射影変換した診断画像も出力する。四角形推定が不安定な場合は回転矩形を暫定使用し、その旨をプレビューとレポートの `method` に残す。候補がない画像には**推測のYOLOラベルを付けず**、FAILとして確認待ちとする。

緑20札の抽出PNGがある状態で以下を実行：

```powershell
uv run --no-sync python scripts/annotate_karuta_frames_v2.py --color green20 --direction LR
uv run --no-sync python scripts/annotate_karuta_frames_v2.py --color green20 --direction FB
uv run --no-sync python scripts/review_karuta_annotations.py --color green20 --variant v2
start data/annotations/video_frames/green20/review_gallery_v2.html
```

v2の出力先：
- `data/annotations/video_frames/green20/h01_s01/LR_v2/{labels,previews,rectified,annotation_report.csv}`
- `data/annotations/video_frames/green20/h01_s01/FB_v2/{labels,previews,rectified,annotation_report.csv}`
- `data/annotations/video_frames/green20/review_gallery_v2.html`

一覧の「射影補正」リンクから四隅を長方形へ補正した画像を見られる。補正後の縦横比52:73は**出力先で設定した比率**であって検出の正しさの証明ではない。札の外枠・白色面・文字が不自然に歪むときは誤検出の可能性がある。

**再実行時は既存ラベルを上書きしない。** `SKIPPED_EXISTING_LABEL` は検出結果が最新になったという意味ではない。v2をやり直すときは該当札のv2ファイルを退避・見直すこと。緑の既存20クラスモデルとv1ラベルには影響しない。

これは**まだ実機画像に対して検証済みではない**仮アノテーション支援ツール。YOLOで先に札の位置を検出する方式ではなく、画像の中心付近に札がある条件に基づく。緑の境界が白飛び・影・モーションブラーで失われた場合は失敗し得る。出力は全て目視確認が必要。

## 緑縁が途切れる動画への追加対応（v3）

v2で緑縁を検出できなかったフレーム向けに、`scripts/annotate_karuta_frames_v3.py` を追加した。v3はv2の検出を優先し、失敗時のみ色相・彩度の閾値を緩和し、途切れた緑縁を小さなモルフォロジー閉処理で繋げて候補を生成する。候補内の**黒い文字＋明るい札面**と中央付近の配置を確認するので、単なる白い蛍光灯反射は札として選びにくい。4点推定できたときは凸四角形、できなければ回転矩形近似となる。

```powershell
uv run --no-sync python scripts/annotate_karuta_frames_v3.py --color green20 --direction LR
uv run --no-sync python scripts/annotate_karuta_frames_v3.py --color green20 --direction FB
uv run --no-sync python scripts/review_karuta_annotations.py --color green20 --variant v3
start data/annotations/video_frames/green20/review_gallery_v3.html
```

- 出力先：`data/annotations/video_frames/green20/h01_s01/LR_v3/` と `FB_v3/`
- 比較：v1/v2のラベルとプレビューを保存したまま、v3の結果を別のHTMLで確認できる
- 注意：自動判定で検出できない場合はFAILを残す。無理にラベルを付けない。全件目視で確認すること
- v3は一部の途切れた緑縁に対応する**暫定実装**であり、撮影済み全フレームでの検証はまだ実施していない
