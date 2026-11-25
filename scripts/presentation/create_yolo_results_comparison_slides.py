"""Create editable comparison PowerPoint from 16 YOLO images and two results CSVs.

Use (from repository root):
    uv run --no-sync --with python-pptx python scripts/presentation/create_yolo_results_comparison_slides.py --images-dir "C:/path/to/your/images"

Put the images supplied in ChatGPT in one folder, preserving their filenames.
All 16 images are included, each once at full-size in appendix, plus comparisons
in the main section. User-supplied images are NEVER altered.
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
    "recall": "BoxR_curve(2).png",
    "f1": "BoxF1_curve(2).png",
    "precision": "BoxP_curve(2).png",
    "pr": "BoxPR_curve(1).png",
    "cm_norm": "confusion_matrix_normalized(1).png",
    "cm": "confusion_matrix(3).png",
    "learning": "results(6).png",
    "test": "competition_001_pred(1).png",
}
NEW = {
    "recall": "BoxR_curve(3).png",
    "f1": "BoxF1_curve(3).png",
    "precision": "BoxP_curve(3).png",
    "pr": "BoxPR_curve(2).png",
    "cm_norm": "confusion_matrix_normalized(2).png",
    "cm": "confusion_matrix(4).png",
    "learning": "results(7).png",
    "test": "competition_001_pred(2).png",
}
CSV_OLD = "results(1).csv"
CSV_NEW = "results(2).csv"
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

def directory(p:Path):
    if p and p.is_dir(): return p
    for candidate in (ROOT/"reports"/"analysis_assets", ROOT/"reports"/"source_images", ROOT):
        if (candidate/OLD["pr"]).is_file(): return candidate
    raise FileNotFoundError("画像フォルダが見つかりません。--images-dir で16画像とCSVのあるフォルダを指定してください。")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--images-dir",type=Path,default=None,help="Directory containing all 16 PNGs and 2 CSVs")
    ap.add_argument("--output",type=Path,default=DEFAULT_OUT)
    a=ap.parse_args()
    basedir=directory(a.images_dir)
    required=list(OLD.values())+list(NEW.values())+[CSV_OLD,CSV_NEW]
    absent=[f for f in required if not (basedir/f).is_file()]
    if absent: raise FileNotFoundError("以下のファイルがありません:\n"+"\n".join(absent))
    o=metrics(basedir/CSV_OLD);n=metrics(basedir/CSV_NEW)

    # 1 overview
    sl=slide("YOLO11n 学習結果：改善前後の比較",
             "前回 trial_06 と今回 trial_video_aug_01（どちらも30 Epoch）")
    box(sl,.89,1.55,11.55,1.22,PALE)
    txt(sl,1.16,1.67,10.92,.86,
        "緑札20クラス：Train 4,320 → 8,520枚／Val 120札 → 180札",22,NAVY,True,True)
    oldmax=max(num(r,"metrics/mAP50(B)") for r in o)
    newmax=max(num(r,"metrics/mAP50(B)") for r in n)
    box(sl,.96,3.07,5.47,1.85,PALE)
    box(sl,6.78,3.07,5.47,1.85,PALE)
    txt(sl,1.20,3.36,4.98,1.25,["前回：mAP50 最大",f"{oldmax:.3f}"],27,BLUE,True,True)
    txt(sl,7.06,3.36,4.90,1.25,["今回：mAP50 最大",f"{newmax:.3f}"],27,GREEN,True,True)
    txt(sl,1.05,5.23,11.38,.80,[
       "注意：Validation構成が異なるため、mAP差だけでは厳密なモデル比較にならない。",
       "改善効果の判定は、同一の独立Test画像・同一推論条件で行う。"],18,NAVY)

    # 2 csv
    sl=slide("学習指標：CSVに基づく数値比較",
             "Epoch 30 の値と、学習中の最大値を分けて表示")
    metric_table(sl,o,n)
    notes(sl,"※ mAP50最大値とEpoch 30の数値は一致しない場合があります。")

    # 3 what charts mean
    sl=slide("グラフの読み方：どこを見る？")
    infos=[
        ("mAP50 / PR曲線","総合性能とクラスごとのAPを見る。右上ほどよい。"),
        ("F1–Confidence","PrecisionとRecallのバランス。ピークと閾値を見る。"),
        ("Recall–Confidence","閾値を上げた際に見逃しが増えていないか。"),
        ("Precision–Confidence","閾値を上げるときの誤検出との兼ね合い。"),
        ("混同行列","対角線＝正解、非対角＝誤分類、background＝誤検出・未検出。"),
        ("学習曲線 / Loss","trainとvalの推移。学習不足や過学習の兆候を見る。"),
    ]
    for i,(head,body) in enumerate(infos):
        x=.80+(i%2)*6.13;yy=1.49+(i//2)*1.70
        box(sl,x,yy,5.84,1.46,PALE,LINE)
        txt(sl,x+.18,yy+.12,5.48,.36,head,21,BLUE,True)
        txt(sl,x+.18,yy+.52,5.48,.75,body,17,NAVY)

    # 4 5 6 7 paired graphics
    for kind,title,subtitle,foot in [
        ("pr","mAP50：Precision–Recall曲線","各クラスのAPと青太線のmAP50に注目",
           "旧0.759 → 新0.980。ただし異なるValでの結果。"),
        ("f1","F1曲線とConfidence閾値","最大F1と、そのときのConfidenceを比較",
           "旧F1 0.59 @0.405 ／ 新F1 0.98 @0.886。"),
        ("cm_norm","正規化混同行列の比較","横軸＝正解、縦軸＝予測。対角線を確認",
           "右端のbackground列は真の札とは別の誤検出を含む。"),
        ("test","同一Test画像の推論結果","実際の競技に近い複数札配置で比較",
           "正解数・誤分類・未検出・重複検出は正解ラベルと照合して集計。"),
    ]:
        sl=slide(title,subtitle)
        image_pair(sl,basedir/OLD[kind],basedir/NEW[kind])
        notes(sl,foot)

    # 8 comparison limitations
    sl=slide("比較上の注意点と次の評価")
    sections=[
      ("Valが異なる","前回は120札、今回は180札。mAPは参考比較として扱う。"),
      ("推論は同条件で","同じ元画像、画像サイズ、Confidence、NMSなど後処理を統一。"),
      ("数を集計する","正解札数／未検出／誤分類／重複／誤検出を算出。"),
      ("苦手な札を分析","今回のValでは023や020のAPが他クラスより低め。"),
    ]
    for i,(head,body) in enumerate(sections):
        y=1.48+i*1.23
        box(sl,.98,y,11.27,1.01,PALE)
        txt(sl,1.21,y+.11,3.12,.78,head,21,BLUE,True)
        txt(sl,4.30,y+.10,7.68,.79,body,19,NAVY)

    # 9 next work
    sl=slide("現状の課題と認識率向上の方針")
    goals=[
     "① 未検出・誤分類・重複・枠ずれをTest画像ごとに分類",
     "② 苦手な札・角度・照明条件の撮影データを追加",
     "③ 単札だけでなく、密集配置・異なる背景の複数札を追加",
     "④ アノテーションを再点検し、独立したTestセットで評価",
     "⑤ データ拡張や閾値調整は条件を一つずつ変えて検証",
    ]
    for i,t in enumerate(goals):
        yy=1.55+i*.98
        box(sl,1.02,yy,11.26,.72,PALE)
        txt(sl,1.26,yy+.08,10.85,.55,t,20,NAVY,True)

    # 10 diary
    sl=slide("研究日誌・実験履歴の管理",
             "再現性の確保と、前回実験との比較を容易にするための記録")
    for i,(head,body) in enumerate([
        ("研究日誌CSV","作業日時、研究内容、実験条件、関連コミットを記録"),
        ("学習履歴","学習条件、モデル、実行日時、指標を記録"),
        ("推論履歴","使用モデル、対象画像、推論設定、結果を追跡"),
        ("次の改善","Testの正解数・誤分類・未検出を実験ごとに追記"),
    ]):
        yy=1.52+i*1.20
        box(sl,.96,yy,11.42,1.01,PALE)
        txt(sl,1.21,yy+.11,2.51,.76,head,21,BLUE,True)
        txt(sl,3.71,yy+.11,8.21,.78,body,19,NAVY)

    # all 16 source plots as readable full-size appendix, original files unmodified
    for kind in ("learning","pr","f1","precision","recall","cm","cm_norm","test"):
        for name,mp,source in (("前回 trial_06",OLD,CSV_OLD),
                               ("今回 trial_video_aug_01",NEW,CSV_NEW)):
            sl=slide(f"補足：{NAMES[kind]}｜{name}")
            contain(sl,basedir/mp[kind],.65,1.30,12.03,5.18)
            notes(sl,EXPL[kind])
    # Append CSVs as a simple final verification guide
    sl=slide("出典と数値の取り扱い（補足）")
    for i,(head,body) in enumerate([
        ("CSV：旧","results(1).csv／trial_06 に対応"),
        ("CSV：新","results(2).csv／trial_video_aug_01 に対応"),
        ("指標の取得","Epoch 30値・全エポック最大値はCSVから計算"),
        ("評価注意","Val条件が違うため厳密な改善量は同じTestで測定"),
    ]):
        yy=1.52+i*1.18
        box(sl,.96,yy,11.31,.95,PALE)
        txt(sl,1.20,yy+.13,2.44,.67,head,20,BLUE,True)
        txt(sl,3.75,yy+.13,8.15,.67,body,19,NAVY)

    a.output.parent.mkdir(parents=True,exist_ok=True)
    prs.save(str(a.output))
    print(f"PowerPoint created: {a.output} ({len(prs.slides)} slides)")
    print("16 attached images included in appendix; all slide text and boxes are editable.")

if __name__=="__main__":
    main()
