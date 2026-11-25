"""Create editable comparison PowerPoint from 16 YOLO images and two results CSVs.

Use (from repository root):
    uv run --no-sync --with python-pptx python scripts/presentation/create_yolo_results_comparison_slides.py --images-dir "C:/path/to/your/images"

Reads original runs/green20/trial_06 and trial_video_aug_01 files automatically,
or falls back to ChatGPT-exported filenames in reports/analysis_assets.
Presents new results first, followed by comparisons, recommendations and small appendix.
User-supplied images are NEVER altered.
"""
from __future__ import annotations
import argparse
import csv
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ROOT / "reports" / "YOLO_trial06_vs_video_aug_results_editable.pptx"
OLD = {
    "recall": "runs/green20/trial_06/BoxR_curve.png",
    "f1": "runs/green20/trial_06/BoxF1_curve.png",
    "precision": "runs/green20/trial_06/BoxP_curve.png",
    "pr": "runs/green20/trial_06/BoxPR_curve.png",
    "cm_norm": "runs/green20/trial_06/confusion_matrix_normalized.png",
    "cm": "runs/green20/trial_06/confusion_matrix.png",
    "learning": "runs/green20/trial_06/results.png",
    "test": "runs/green20_labeled/trial_06_competition/competition_001_pred.png",
}
NEW = {
    "recall": "runs/green20/trial_video_aug_01/BoxR_curve.png",
    "f1": "runs/green20/trial_video_aug_01/BoxF1_curve.png",
    "precision": "runs/green20/trial_video_aug_01/BoxP_curve.png",
    "pr": "runs/green20/trial_video_aug_01/BoxPR_curve.png",
    "cm_norm": "runs/green20/trial_video_aug_01/confusion_matrix_normalized.png",
    "cm": "runs/green20/trial_video_aug_01/confusion_matrix.png",
    "learning": "runs/green20/trial_video_aug_01/results.png",
    "test": "runs/green20_labeled/trial_video_aug_01/competition_001_pred.png",
}
CSV_OLD = "runs/green20/trial_06/results.csv"
CSV_NEW = "results.csv"
NAMES = {
    "recall":"Recall–Confidence", "f1":"F1–Confidence",
    "precision":"Precision–Confidence", "pr":"Precision–Recall",
    "cm_norm":"正規化混同行列", "cm":"混同行列（件数）",
    "learning":"学習曲線", "test":"複数札Test画像の推論",
}
EXPL = {
    "recall":"閾値を高くすると見逃しが増える。青太線は全クラス平均。",
    "f1":"PrecisionとRecallのバランス。ピークとそのConfidenceを読む。",
    "precision":"閾値を高くすると一般に誤検出が減るが、検出数も減る。",
    "pr":"曲線が右上寄りほど良い。凡例の各クラスAPと全クラスmAP50を読む。",
    "cm_norm":"横軸が正解、縦軸が予測。対角線が1に近いほど正しい。",
    "cm":"斜めが正解数。右端のbackground列は主に誤検出を示す。",
    "learning":"train/val lossは減少するか。Precision・Recall・mAPは安定するか。",
    "test":"同じ元画像・同じ推論設定でクラス正解数、未検出、誤分類、重複を比べる。",
}
NAVY=RGBColor(23,55,88)
BLUE=RGBColor(37,105,155)
PALE=RGBColor(235,244,250)
WHITE=RGBColor(255,255,255)
INK=RGBColor(34,47,63)
MUTED=RGBColor(102,119,134)
LINE=RGBColor(190,215,232)
GREEN=RGBColor(31,128,104)
prs=Presentation()
prs.slide_width=Inches(13.333)
prs.slide_height=Inches(7.5)

def box(sl,x,y,w,h,color=PALE,edge=None):
    sh=sl.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(x), Inches(y), Inches(w), Inches(h))
    sh.fill.solid()
    sh.fill.fore_color.rgb=color
    if edge is None: sh.line.fill.background()
    else: sh.line.color.rgb=edge; sh.line.width=Pt(1)
    return sh

def txt(sl,x,y,w,h,lines,size=18,color=INK,bold=False,center=False):
    sh=sl.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    f=sh.text_frame
    f.clear(); f.word_wrap=True
    f.margin_left=f.margin_right=Inches(.07)
    f.margin_top=f.margin_bottom=Inches(.015)
    f.vertical_anchor=MSO_ANCHOR.MIDDLE
    for i,v in enumerate(lines if isinstance(lines,(list,tuple)) else [lines]):
        p=f.paragraphs[0] if i==0 else f.add_paragraph()
        p.text=str(v); p.font.name="Yu Gothic"; p.font.size=Pt(size)
        p.font.bold=bold; p.font.color.rgb=color
        p.alignment=PP_ALIGN.CENTER if center else PP_ALIGN.LEFT
        p.space_after=Pt(6)
    return sh

def slide(title,subtitle=None):
    sl=prs.slides.add_slide(prs.slide_layouts[6])
    txt(sl,.61,.12,12.1,.63,title,29,INK,True,True)
    sh=sl.shapes.add_shape(MSO_SHAPE.RECTANGLE,Inches(.48),Inches(.85),Inches(12.38),Inches(.035))
    sh.fill.solid();sh.fill.fore_color.rgb=BLUE;sh.line.fill.background()
    if subtitle: txt(sl,.82,.97,11.7,.38,subtitle,15,MUTED,False,True)
    txt(sl,.69,7.11,5.8,.20,"競技かるた YOLO11n｜比較・評価",10,MUTED)
    txt(sl,12.1,7.11,.4,.20,str(len(prs.slides)),11,MUTED,False,True)
    return sl

def contain(sl,path,x,y,w,h):
    with Image.open(path) as im:
        iw,ih=im.size
    ratio=min(w/iw,h/ih)
    ww,hh=iw*ratio,ih*ratio
    sl.shapes.add_picture(str(path), Inches(x+(w-ww)/2), Inches(y+(h-hh)/2),
                          width=Inches(ww),height=Inches(hh))

def image_pair(sl,old,new,labels=("前回：trial_06","今回：trial_video_aug_01"),y=1.78,h=4.65):
    for i,(p,name) in enumerate(zip((old,new),labels)):
        x=.64+i*6.17
        box(sl,x,1.43,5.99,.42,BLUE)
        txt(sl,x+.04,1.45,5.91,.36,name,17,WHITE,True,True)
        box(sl,x,y,5.99,h,WHITE,LINE)
        contain(sl,p,x+.09,y+.08,5.81,h-.16)

def notes(sl,textline):
    box(sl,.89,6.53,11.55,.39,PALE)
    txt(sl,1.08,6.55,11.2,.35,textline,15,NAVY)

def metrics(path):
    with path.open(encoding="utf-8-sig",newline="") as fp: rows=list(csv.DictReader(fp))
    return rows

def num(row,key):
    return float(row[key])

def metric_table(sl, old_rows, new_rows, y=2.07):
    data=[
        ("Epoch 30 Precision","metrics/precision(B)",3),
        ("Epoch 30 Recall","metrics/recall(B)",3),
        ("Epoch 30 mAP50","metrics/mAP50(B)",3),
        ("Epoch 30 mAP50-95","metrics/mAP50-95(B)",3),
        ("最大 mAP50（全Epoch）","metrics/mAP50(B)",4),
        ("最大 mAP50-95（全Epoch）","metrics/mAP50-95(B)",4),
    ]
    for i,(name,key,kind) in enumerate(data):
        yy=y+i*.62
        box(sl,.90,yy,11.48,.55,WHITE if i%2 else PALE)
        if kind==3: a=num(old_rows[-1],key); b=num(new_rows[-1],key)
        else: a=max(num(r,key) for r in old_rows); b=max(num(r,key) for r in new_rows)
        txt(sl,1.11,yy+.05,5.24,.44,name,18,NAVY,True)
        txt(sl,6.55,yy+.05,2.16,.44,f"{a:.3f}",19,INK,False,True)
        txt(sl,9.52,yy+.05,2.24,.44,f"{b:.3f}",19,GREEN,True,True)
    txt(sl,6.54,1.74,2.17,.34,"前回",19,BLUE,True,True)
    txt(sl,9.57,1.74,2.20,.34,"今回",19,BLUE,True,True)

def resolve_asset(basedir, experiment, kind):
    """Prefer original runs folders; fall back to ChatGPT-exported filenames."""
    names = OLD if experiment == "old" else NEW
    trial = "trial_06" if experiment == "old" else "trial_video_aug_01"
    original = {
        "recall":"BoxR_curve.png", "f1":"BoxF1_curve.png",
        "precision":"BoxP_curve.png", "pr":"BoxPR_curve.png",
        "cm_norm":"confusion_matrix_normalized.png",
        "cm":"confusion_matrix.png", "learning":"results.png",
        "test":"competition_001_pred.png", "csv":"results.csv",
    }
    selected = CSV_OLD if experiment == "old" and kind == "csv" else (
        CSV_NEW if kind == "csv" else names[kind]
    )
    # Selected can be a Path, an absolute path, a path relative to ROOT,
    # or one of the suffixed uploaded filenames.
    candidates = []
    p = Path(selected)
    if p.is_absolute():
        candidates.append(p)
    else:
        candidates.extend([ROOT/p, basedir/p])
    candidates.append(ROOT/"runs"/"green20"/trial/original[kind])
    candidates.append(basedir/Path(selected).name)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        f"必要なファイルがありません ({experiment}/{kind}). 確認した保存先: "
        + " / ".join(str(p) for p in candidates)
    )

def single_figure(title, path, lines, footer=None):
    """Large figure next to statements: observation then interpretation."""
    sl=slide(title)
    box(sl,.67,1.23,8.15,5.60,WHITE,LINE)
    contain(sl,path,.80,1.36,7.89,5.34)
    box(sl,9.01,1.25,3.52,5.54,PALE,LINE)
    txt(sl,9.20,1.44,3.13,.47,"グラフから分かること",19,BLUE,True)
    for i,line in enumerate(lines):
        yy=2.00+i*.98
        txt(sl,9.20,yy,3.09,.89,"● "+line,17,NAVY)
    if footer:
        notes(sl,footer)
    return sl

def comparison_figure(title, old, new, observation, warning=None):
    sl=slide(title,"左：前回 trial_06 ／ 右：今回 trial_video_aug_01")
    image_pair(sl,old,new,y=1.88,h=4.42)
    notes(sl,observation)
    if warning:
        txt(sl,.88,6.09,11.7,.35,warning,13,MUTED,False,True)
    return sl

def main():
    ap=argparse.ArgumentParser(description="Generate results-first editable YOLO presentation")
    ap.add_argument("--images-dir",type=Path,default=ROOT/"reports"/"analysis_assets")
    ap.add_argument("--output",type=Path,default=DEFAULT_OUT)
    a=ap.parse_args()
    # The old script required a separate images folder. This version also
    # reads the original YOLO run folders without copying any PNG/CSV.
    basedir=a.images_dir
    old={k:resolve_asset(basedir,"old",k) for k in OLD}
    new={k:resolve_asset(basedir,"new",k) for k in NEW}
    oc=resolve_asset(basedir,"old","csv")
    nc=resolve_asset(basedir,"new","csv")
    o=metrics(oc)
    n=metrics(nc)

    # 1. Purpose and evaluation conditions (before comparisons)
    sl=slide("YOLO11n：今回の学習と評価","まず今回の学習結果を示し、その後で前回と比較する")
    box(sl,.91,1.55,11.49,1.00,PALE)
    txt(sl,1.12,1.74,11.09,.63,
        "緑札20クラス／Train 8,520枚／Validation 180枚／30 Epoch",23,NAVY,True,True)
    items=[
        ("学習データ","正面20枚＋LR・FB動画200枚から拡張"),
        ("新しく増やした特徴","斜め視点と遠近変形を含む画像"),
        ("今回の発表","結果の読み取り → 旧モデル比較 → 課題・改善策"),
    ]
    for i,(head,body) in enumerate(items):
        yy=2.93+i*1.05
        box(sl,1.04,yy,11.18,.83,PALE)
        txt(sl,1.27,yy+.10,3.14,.61,head,20,BLUE,True)
        txt(sl,4.40,yy+.11,7.44,.59,body,19,NAVY)
    txt(sl,1.07,6.46,11.1,.36,
        "※ Validationは単札主体の180枚。複数札Testの性能とは区別する。",16,MUTED,False,True)

    # 2. New model quantitative result, upfront
    sl=slide("今回の学習結果：数値で確認する","trial_video_aug_01 の results.csv ／ 最終30 Epoch と全Epoch最大値")
    rows=[
        ("Precision (30 Epoch)","metrics/precision(B)"),
        ("Recall (30 Epoch)","metrics/recall(B)"),
        ("mAP50 (30 Epoch)","metrics/mAP50(B)"),
        ("mAP50-95 (30 Epoch)","metrics/mAP50-95(B)"),
    ]
    for i,(name,key) in enumerate(rows):
        yy=1.48+i*.88
        box(sl,1.08,yy,11.05,.70,PALE)
        txt(sl,1.33,yy+.09,7.3,.51,name,22,NAVY,True)
        txt(sl,9.01,yy+.09,2.40,.51,f"{num(n[-1],key):.3f}",24,GREEN,True,True)
    best_m50=max(num(r,"metrics/mAP50(B)") for r in n)
    best_m5095=max(num(r,"metrics/mAP50-95(B)") for r in n)
    box(sl,1.13,5.22,10.96,.90,PALE,LINE)
    txt(sl,1.35,5.31,10.56,.73,
        f"全Epoch最大：mAP50 {best_m50:.3f} ／ mAP50-95 {best_m5095:.3f}",
        22,BLUE,True,True)
    txt(sl,1.19,6.31,10.9,.35,
        "Precisionは誤検出の少なさ、Recallは見逃しの少なさを示す。",17,MUTED,False,True)

    # 3-10: actual new result images plus interpretations, before old-vs-new
    single_figure("今回の結果①：学習曲線",new["learning"],[
        "Trainの位置・分類損失が減少した。",
        "Validation損失も概ね減少したが変動がある。",
        "mAP・Precision・Recallは高水準で推移した。",
    ])
    single_figure("今回の結果②：PR曲線とmAP50",new["pr"],[
        "全クラスのmAP50は約0.980。",
        "右上に近い曲線ほど見逃し・誤検出が少ない。",
        "札020・023は他の多くの札よりAPが低い。",
    ])
    single_figure("今回の結果③：F1と信頼度閾値",new["f1"],[
        "最大F1は約0.98。",
        "最大点のConfidenceは約0.886。",
        "閾値は独立したTest画像でも検証する。",
    ])
    single_figure("今回の結果④：混同行列（件数）",new["cm"],[
        "対角線上に正しい分類が集中する。",
        "020・023・071などに一部の誤分類が残る。",
        "右端の背景列に誤検出が見られる。",
    ])
    single_figure("今回の結果⑤：正規化混同行列",new["cm_norm"],[
        "横軸＝正解、縦軸＝予測。",
        "対角線1.00の札が多い。",
        "背景列は札ごとの正解率ではない。",
    ])
    single_figure("今回の結果⑥：複数札のTest推論",new["test"],[
        "競技配置の画像でも複数札を検出できる。",
        "枠がない札や誤分類が残っている。",
        "正解札番号と照合し、正解数を数える必要がある。",
    ])
    single_figure("今回の結果⑦：Precision–Confidence",new["precision"],[
        "Confidenceを高くするとPrecisionは高くなりやすい。",
        "ただし検出件数は減少し得る。",
        "高信頼度＝必ず正解、ではない。",
    ])
    single_figure("今回の結果⑧：Recall–Confidence",new["recall"],[
        "低～中Confidence域でRecallは高い。",
        "閾値を上げ過ぎると見逃しが急増する。",
        "F1・Precisionと合わせて閾値を選ぶ。",
    ])

    # Comparisons, after the result analysis
    sl=slide("前回学習との比較：まず条件を確認")
    for i,(name,left,right) in enumerate([
        ("学習画像枚数","4,320","8,520"),
        ("斜め画像の学習","なし","LR・FB動画200枚を拡張"),
        ("Validation対象","60画像・120札","180画像・180札"),
        ("最終Epoch","30","30"),
    ]):
        y=1.55+i*.88
        box(sl,.99,y,11.38,.68,PALE)
        txt(sl,1.17,y+.08,4.10,.52,name,19,BLUE,True)
        txt(sl,5.30,y+.08,2.69,.52,left,18,NAVY,False,True)
        txt(sl,8.29,y+.08,3.79,.52,right,18,NAVY,True,True)
    txt(sl,5.28,1.23,2.70,.30,"前回 trial_06",17,BLUE,True,True)
    txt(sl,8.35,1.23,3.70,.30,"今回 trial_video_aug_01",17,BLUE,True,True)
    box(sl,1.09,5.55,11.10,.89,PALE,LINE)
    txt(sl,1.39,5.67,10.56,.67,
        "重要：Valの構成が異なるので、指標の差だけで厳密な性能向上とは断定しない。",
        20,NAVY,True,True)

    sl=slide("前回との比較：30 Epoch時点の評価値")
    metric_table(sl,o,n)
    notes(sl,"各モデルの異なるValidation結果。厳密比較は共通Test画像で行う。")

    comparison_figure("比較①：学習曲線",old["learning"],new["learning"],
        "今回のVal側でmAP・Recallが高く、損失の減少も確認できる。",
        "※ 異なるValを用いた学習曲線の比較")
    comparison_figure("比較②：PR曲線（mAP50）",old["pr"],new["pr"],
        "旧：0.759 → 新：0.980。今回のVal上では高い検出性能。",
        "※ Valが異なるため、差分をそのまま汎化性能の改善率とはしない")
    comparison_figure("比較③：F1–Confidence",old["f1"],new["f1"],
        "旧：最大F1 0.59 @0.405 → 新：0.98 @0.886。",
        "※ 各モデル自身のValに対する最適点であり、Test閾値の確定値ではない")
    comparison_figure("比較④：正規化混同行列",old["cm_norm"],new["cm_norm"],
        "今回は正解の対角線が明瞭。混同する札と背景への誤検出にも注目。",
        "※ 行列の母数は異なるため、件数ではなく傾向を説明する")
    comparison_figure("比較⑤：複数札Test画像",old["test"],new["test"],
        "旧モデルは特定の札への予測の偏りが目立つ。新モデルでも未検出は残る。",
        "※ 必ず正解ラベルと照合して正解・誤分類・未検出・重複を数える")

    # Evaluation recommendations & future work
    sl=slide("比較から言えること・言えないこと")
    for i,(head,body) in enumerate([
        ("確認できたこと","今回のValidationで高いmAP・F1を達成。札別の性能差も確認。"),
        ("推論画像から見えること","特定クラスへの予測偏りが減る一方、未検出・誤分類が残る。"),
        ("まだ断定できないこと","異なるVal間の数値差がそのまま一般化性能差とは限らない。"),
        ("次に必要なこと","同じ独立Test画像・推論設定で正解数を定量比較する。"),
    ]):
        yy=1.47+i*1.22
        box(sl,.89,yy,11.52,1.02,PALE)
        txt(sl,1.14,yy+.11,3.45,.79,head,21,BLUE,True)
        txt(sl,4.49,yy+.10,7.58,.81,body,18,NAVY)

    sl=slide("今後の課題と認識精度の改善策")
    for i,(head,body) in enumerate([
        ("① 未検出を減らす","暗さ・反射・小さい札・密集配置の失敗例を集める。"),
        ("② 誤分類を減らす","APの低い札020・023などを優先して撮影・確認する。"),
        ("③ 誤検出を減らす","背景や複数札の配置画像を増やし、閾値・重複抑制も見直す。"),
        ("④ 比較を公平に","同じTestと同じ後処理を用い、変更は一条件ずつ行う。"),
    ]):
        yy=1.52+i*1.20
        box(sl,1.00,yy,11.27,1.02,PALE)
        txt(sl,1.23,yy+.10,3.65,.81,head,20,BLUE,True)
        txt(sl,4.79,yy+.10,7.25,.81,body,18,NAVY)

    sl=slide("研究日誌・実験履歴の管理",
        "実験条件や作業時間を記録し、比較の根拠を残す")
    for i,(head,body) in enumerate([
        ("研究日誌","作業日時・内容・関連ファイル・GitHubコミットをCSV保存"),
        ("学習履歴","使用データセット・モデル・学習条件・評価値を記録"),
        ("推論履歴","モデル・対象画像・実行日時を後から確認できる"),
        ("次回の記録","Testの正解・誤分類・未検出数を同じ形式で追加"),
    ]):
        yy=1.51+i*1.17
        box(sl,1.01,yy,11.25,.96,PALE)
        txt(sl,1.25,yy+.09,2.84,.77,head,21,BLUE,True)
        txt(sl,4.06,yy+.10,7.84,.73,body,18,NAVY)

    # Only secondary/nonessential old figures are in appendix.
    for kind in ("precision","recall","cm"):
        sl=slide(f"補足：前回の{NAMES[kind]}",
                 "必要に応じて質問対応に使用")
        contain(sl,old[kind],.77,1.39,11.74,4.98)
        notes(sl,EXPL[kind])

    sl=slide("補足：数値の出典と評価上の注意")
    for i,(head,body) in enumerate([
        ("前回CSV",str(oc)),
        ("今回CSV",str(nc)),
        ("計算方法","最終Epoch値と各Epoch中の最大値を区別して表示"),
        ("比較条件","Valが異なるため、共通の独立Testで差を再評価"),
    ]):
        yy=1.51+i*1.16
        box(sl,.92,yy,11.45,.96,PALE)
        txt(sl,1.14,yy+.12,2.14,.70,head,19,BLUE,True)
        txt(sl,3.19,yy+.12,8.85,.70,body,16,NAVY)

    a.output.parent.mkdir(parents=True,exist_ok=True)
    prs.save(str(a.output))
    print(f"Created {len(prs.slides)} slides: {a.output}")
    print("Results first, then old-vs-new comparison, improvements, diary, brief appendix.")
    print("Original images are unchanged; explanatory boxes and text remain editable.")

if __name__=="__main__":
    main()
