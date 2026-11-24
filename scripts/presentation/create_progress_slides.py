"""Create a fully editable blue-themed YOLO progress PowerPoint.

Run from repo root:
  uv run --no-sync --with python-pptx python scripts/presentation/create_progress_slides.py

Text, headers, backgrounds, tables and diagrams are editable PowerPoint shapes.
Training plots and actual inference photos, when found, are embedded as images.
"""
from __future__ import annotations

from pathlib import Path
import argparse

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "reports" / "YOLO_green20_progress_editable_20261124.pptx"
NAVY = RGBColor(26, 56, 82)
BLUE = RGBColor(36, 107, 150)
TURQ = RGBColor(42, 142, 139)
PALE = RGBColor(237, 244, 248)
WHITE = RGBColor(255, 255, 255)
GRAY = RGBColor(102, 118, 130)
BLACK = RGBColor(20, 26, 31)

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)

def textbox(slide, x, y, w, h, lines, *, size=22, bold=False, color=BLACK,
            align=None, margin=0.08):
    shape = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = shape.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(margin)
    tf.margin_top = tf.margin_bottom = Inches(0.02)
    if isinstance(lines, str):
        lines = [lines]
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = str(line)
        p.font.name = "Yu Gothic"
        p.font.size = Pt(size)
        p.font.bold = bold
        p.font.color.rgb = color
        p.space_after = Pt(12)
        if align is not None:
            p.alignment = align
    return shape

def rect(slide, x, y, w, h, fill=PALE, *, rounding=True, line=None):
    shp = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if rounding else MSO_SHAPE.RECTANGLE,
                                 Inches(x), Inches(y), Inches(w), Inches(h))
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill
    shp.line.fill.background() if line is None else None
    if line is not None:
        shp.line.color.rgb = line
    return shp

def slide(title, page):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    rect(s, 0.36, 0.82, 12.62, 0.022, BLUE, rounding=False)
    textbox(s, .75, .17, 11.95, .62, title, size=32, bold=True, color=BLACK,
            align=PP_ALIGN.CENTER)
    textbox(s, .68, 7.12, 2.3, .2, "2026/11/24", size=10, color=GRAY)
    textbox(s, 5.2, 7.10, 4.5, .25, "小谷・渡辺研究室　進捗報告", size=10,
            color=GRAY, align=PP_ALIGN.CENTER)
    textbox(s, 12.15, 7.10, .45, .25, str(page), size=10, color=GRAY,
            align=PP_ALIGN.RIGHT)
    return s

def panel(s, x, y, w, h, head, body, *, font=19):
    rect(s, x, y, w, h)
    textbox(s, x+.18, y+.14, w-.36, .42, head, size=23, bold=True, color=NAVY)
    textbox(s, x+.18, y+.78, w-.36, h-.88, body, size=font, color=NAVY)

def bullets(s, x, y, w, lines, *, font=21, step=.67, color=BLACK):
    for i, line in enumerate(lines):
        textbox(s, x, y+i*step, w, step+.09, "● " + line, size=font, color=color)

def tag(s, x, y, w, title):
    rect(s, x, y, w, .55, BLUE)
    textbox(s, x+.13, y+.05, w-.26, .4, title, size=22, bold=True, color=WHITE)

def image_placeholder(s, x, y, w, h, text):
    rect(s,x,y,w,h,PALE,line=RGBColor(185,205,218))
    textbox(s,x+.15,y+h*.35,w-.3,h*.3,text,size=17,color=GRAY,align=PP_ALIGN.CENTER)

def find_img(*patterns):
    for pattern in patterns:
        hits = sorted(ROOT.glob(pattern))
        if hits:
            return hits[0]
    return None

def picture_or_placeholder(s, x, y, w, h, img, label):
    if img is None:
        image_placeholder(s,x,y,w,h,label+"\\n（後から挿入）")
        return
    # Image stays independent; can be moved, cropped or replaced in PPT.
    from PIL import Image
    try:
        with Image.open(img) as im:
            iw,ih=im.size
        width,height=w,h
        if iw/ih>w/h:
            height=w*ih/iw
        else:
            width=h*iw/ih
        s.shapes.add_picture(str(img), Inches(x+(w-width)/2), Inches(y+(h-height)/2),
                             width=Inches(width), height=Inches(height))
    except Exception:
        image_placeholder(s,x,y,w,h,label+"\\n（画像読み込み失敗）")

def add_table(s, data, x, y, widths, row_h=.59, font=17):
    rows=len(data)
    table=s.shapes.add_table(rows,len(widths), Inches(x), Inches(y),
                             Inches(sum(widths)), Inches(row_h*rows)).table
    for j,width in enumerate(widths):
        table.columns[j].width=Inches(width)
    for i,row in enumerate(data):
        for j,value in enumerate(row):
            cell=table.cell(i,j)
            cell.text=str(value)
            cell.fill.solid()
            cell.fill.fore_color.rgb=BLUE if i==0 else (PALE if i%2 else WHITE)
            cell.vertical_anchor=MSO_ANCHOR.MIDDLE
            for p in cell.text_frame.paragraphs:
                p.font.name="Yu Gothic"
                p.font.size=Pt(font)
                p.font.bold=(i==0)
                p.font.color.rgb=WHITE if i==0 else NAVY
    return table

# 1 Purpose
s=slide("YOLO：目的と使用モデル",1)
panel(s,.7,1.13,5.85,3.89,"研究目的",[
    "競技かるたの札をカメラ画像から検出し、札の種類を識別",
    "まず五色百人一首の緑札20枚に対象を限定し、20クラスで学習",
],font=22)
panel(s,6.74,1.13,5.9,3.89,"使用モデル",[
    "YOLO11n（軽量な物体検出モデル）",
    "札の位置を矩形で検出するとともに、20クラスのいずれかに分類",
],font=22)
tag(s,.9,5.3,3.0,"今回の進捗")
bullets(s,4.2,5.42,8.4,["データセットの作成・改善","画像のアノテーション","緑札20クラスの学習・推論"],font=19,step=.43)

# 2 workflow
s=slide("研究の全体像",2)
steps=["撮影","フレーム抽出","アノテーション","データ拡張","学習・推論"]
for i,step in enumerate(steps):
    xx=.55+i*2.57
    rect(s,xx,2.1,2.14,1.24,PALE)
    textbox(s,xx+.08,2.44,1.98,.5,step,size=19,bold=True,color=NAVY,align=PP_ALIGN.CENTER)
    if i<4:
        textbox(s,xx+2.17,2.43,.33,.35,"→",size=22,bold=True,color=BLUE)
panel(s,.95,4.12,5.48,1.85,"現在","静止画像を用いて複数札の識別結果を確認",font=19)
panel(s,6.75,4.12,5.48,1.85,"将来","100札に展開し、カメラ映像でリアルタイム推論",font=19)

# 3 acquisition
s=slide("データセットの撮影方法",3)
panel(s,.75,1.18,5.85,3.57,"正面画像",[
    "撮影高さ h01・h02・h03 の3条件で札の大きさを計測",
    "今後は h01 を基準に縮小変換して高さ差を模擬",
],font=20)
panel(s,6.75,1.18,5.85,3.57,"斜め画像",[
    "左右（LR）・前後（FB）の2方向から動画撮影",
    "100札 × 2方向 ＝ 200本の動画を取得",
    "各動画から5フレームを抽出（全色で計1,000枚）",
],font=19)
tag(s,.82,5.08,3.15,"画像・動画の例")
image_placeholder(s,4.15,5.01,3.87,1.3,"撮影GUIの画像")
image_placeholder(s,8.2,5.01,3.85,1.3,"動画フレームの例")

# 4 annotation
s=slide("画像のアノテーション",4)
items=[
"CSVに札番号・決まり字などを登録",
"札番号順に撮影して画像とクラスを対応付け",
"正面画像は札面から枠を自動推定",
"動画画像は緑枠を検出し四隅を推定",
"5フレーム抽出：画像変化量と鮮明さを考慮",
"検出失敗時は四隅4点を手動指定して修正",
]
for i,t in enumerate(items):
    yy=1.22+i*.82
    rect(s,.8,yy,.56,.53,BLUE)
    textbox(s,.87,yy+.045,.38,.37,str(i+1),size=19,bold=True,color=WHITE,align=PP_ALIGN.CENTER)
    rect(s,1.55,yy,10.95,.58,PALE)
    textbox(s,1.76,yy+.07,10.6,.48,t,size=20,color=NAVY)
textbox(s,.92,6.45,11.4,.43,"確認：プレビュー一覧で枠位置を目視確認し、必要な画像のみ補正",size=17,color=GRAY)

# 5 data augmentation
s=slide("学習データの拡張方法",5)
add_table(s,[
["画像","元画像","変換","生成後"],
["正面 h01_s01","20枚","3倍率 × 72回転（5°刻み）","4,320枚"],
["左右 LR","100枚","3倍率 × 7回転（−15°〜15°）","2,100枚"],
["前後 FB","100枚","3倍率 × 7回転（−15°〜15°）","2,100枚"],
["合計","220枚","左右・上下反転なし","8,520枚"],
],.8,1.35,[2.25,1.65,5.7,2.1],row_h=.70,font=17)
panel(s,.85,5.15,11.7,1.27,"札の見かけの大きさ","h01：1.00000　／　h02：0.56481　／　h03：0.37612",font=20)

# 6 train val test
s=slide("Train・Validation・Testの構成",6)
add_table(s,[
["用途","画像の内訳","枚数","データ拡張"],
["Train","正面20枚＋LR/FB動画200枚から生成","8,520","あり"],
["Validation","固定角度160枚＋正面s02 20枚","180","なし"],
["Test","別撮影の複数札配置画像","別途","なし"],
],.79,1.35,[2.1,6.25,1.35,1.85],row_h=.76,font=17)
panel(s,.9,4.8,11.6,1.5,"評価上の注意",[
    "Train・Val・Testに同一画像は使用していないが、撮影環境は類似",
    "異なる照明・背景・カメラ条件での汎化性能は今後検証",
],font=17)

# 7 training setup
s=slide("YOLO11n：学習条件",7)
add_table(s,[
["項目","設定"],
["対象クラス","緑札20クラス"],
["学習画像・検証画像","Train 8,520枚 ／ Validation 180枚"],
["エポック数","30"],
["バッチサイズ","8"],
["入力画像サイズ","640 × 640"],
["画像拡張","準備済みデータのみ使用（追加ランダム変換なし）"],
["実験名","trial_video_aug_01"],
],1.3,1.27,[4,6.7],row_h=.61,font=18)

# 8 results
s=slide("学習結果：検証データ",8)
res=find_img("runs/green20/trial_video_aug_01/results.png","runs/**/trial_video_aug_01/results.png")
f1=find_img("runs/green20/trial_video_aug_01/BoxF1_curve.png","runs/**/trial_video_aug_01/BoxF1_curve.png")
picture_or_placeholder(s,.68,1.23,7.15,4.3,res,"results.png")
picture_or_placeholder(s,7.97,1.3,4.65,3.25,f1,"BoxF1_curve.png")
panel(s,8.0,4.75,4.55,1.45,"F1曲線","最良F1 ≈ 0.98（信頼度 ≈ 0.886）",font=17)
textbox(s,.9,5.8,6.9,.69,"損失の減少と高いValidation精度を確認",size=19,color=NAVY)
textbox(s,.9,6.5,11.5,.3,"※ Precision・Recall・mAPの確定値はresults.csvから追記できます。",size=12,color=GRAY)

# 9 confusion
s=slide("検証結果：混同行列",9)
matrix=find_img("runs/green20/trial_video_aug_01/confusion_matrix.png",
                "runs/**/trial_video_aug_01/confusion_matrix.png")
picture_or_placeholder(s,.8,1.2,7.1,5.6,matrix,"confusion_matrix.png")
panel(s,8.13,1.48,4.26,3.7,"確認できる傾向",[
    "ほとんどの札が対角成分に集中",
    "一部の札では誤分類・重複検出が残存",
    "同一環境下の単札Validationでは高精度",
],font=18)

# 10 test result
s=slide("複数札画像による推論結果",10)
pred=find_img("runs/**/competition_001_pred.png","runs/**/competition*pred*.png")
picture_or_placeholder(s,5.83,1.25,6.65,5.67,pred,"competition_001_pred.png")
panel(s,.67,1.25,4.9,4.92,"静止画像Testでの確認",[
    "20枚を並べた画像に対して推論",
    "良好な例では14／20枚を正しく認識",
    "未検出や他札への誤分類は残る",
    "やや暗い画像でも一定の検出性能を確認",
],font=18)
textbox(s,.84,6.43,4.6,.35,"※ 14/20は一例であり全Testの平均値ではない。",size=12,color=GRAY)

# 11 comparison
s=slide("改善前後の比較（追加予定）",11)
image_placeholder(s,.72,1.65,5.62,3.55,"改善前：trial_06の推論画像")
image_placeholder(s,6.89,1.65,5.62,3.55,"改善後：trial_video_aug_01の推論画像")
textbox(s,.92,5.47,11.8,.56,"同じTest画像・同じ推論条件で、正解数・未検出・誤分類を比較する",size=18,color=NAVY)
textbox(s,.95,6.15,11.55,.44,"注意：学習データや拡張条件も変わるため、改善を斜め画像の追加だけに帰することはできない。",size=14,color=GRAY)

# 12 conclusion
s=slide("まとめと今後の予定",12)
panel(s,.77,1.35,5.8,4.65,"今回の成果",[
    "緑20クラス用データセットを構築",
    "動画抽出と自動アノテーションを整備",
    "学習後、複数札画像でも認識性能の改善を確認",
],font=20)
panel(s,6.76,1.35,5.8,4.65,"今後の予定",[
    "同一Test画像で改善前後を比較",
    "照明・背景・配置を変えた評価",
    "残り4色を加えて100クラス化",
    "カメラ映像からのリアルタイム推論",
],font=19)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output",type=Path,default=OUT)
    args=ap.parse_args()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    prs.save(str(args.output))
    print(f"Created {len(prs.slides)} editable slides: {args.output}")
    print("Text, shapes, tables are editable. Photos/plots are separate images.")
    print("If plots are missing, use PowerPoint to replace the placeholders.")

if __name__=="__main__":
    main()
