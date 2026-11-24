"""Create editable blue-themed annotation flowchart slides.

Run:
    uv run --no-sync --with python-pptx python scripts/presentation/create_annotation_flow_slides.py

All flowchart boxes, arrows and text are editable PowerPoint objects.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "reports" / "YOLO_annotation_flow_editable_20261124.pptx"

NAVY = RGBColor(24, 56, 86)
BLUE = RGBColor(40, 107, 155)
MID_BLUE = RGBColor(78, 139, 183)
PALE = RGBColor(234, 243, 250)
LIGHT = RGBColor(246, 250, 253)
WHITE = RGBColor(255, 255, 255)
INK = RGBColor(29, 44, 59)
MUTED = RGBColor(92, 116, 135)
AMBER = RGBColor(255, 237, 194)
AMBER_INK = RGBColor(109, 77, 28)
GREEN = RGBColor(40, 136, 98)
PINK = RGBColor(250, 240, 238)

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)

def box(s, x, y, w, h, fill, *, line=None, radius=True):
    z = s.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE,
                            Inches(x), Inches(y), Inches(w), Inches(h))
    z.fill.solid()
    z.fill.fore_color.rgb = fill
    if line is None:
        z.line.fill.background()
    else:
        z.line.color.rgb = line
        z.line.width = Pt(1.2)
    return z

def txt(s, x, y, w, h, content, *, size=20, color=INK,
        bold=False, align=PP_ALIGN.LEFT, margin=.06):
    z = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = z.text_frame
    tf.clear()
    tf.word_wrap = True
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    tf.margin_left = tf.margin_right = Inches(margin)
    tf.margin_top = tf.margin_bottom = Inches(.012)
    lines = content if isinstance(content, (tuple, list)) else [content]
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.text = str(line)
        p.font.name = "Yu Gothic"
        p.font.size = Pt(size)
        p.font.color.rgb = color
        p.font.bold = bold
        p.alignment = align
        p.space_after = Pt(5)
    return z

def slide(title, number, subtitle=None):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    txt(s, .65, .15, 12.0, .62, title, size=30, bold=True, align=PP_ALIGN.CENTER)
    box(s, .50, .87, 12.33, .035, BLUE, radius=False)
    if subtitle:
        txt(s, .72, .99, 11.95, .41, subtitle, size=16, color=MUTED,
            align=PP_ALIGN.CENTER)
    box(s, .65, 7.05, 12.0, .013, MID_BLUE, radius=False)
    txt(s, .79, 7.13, 3.0, .19, "競技かるた札のYOLO認識", size=10, color=MUTED)
    txt(s, 5.14, 7.12, 3.2, .19, "アノテーション手法", size=10, color=MUTED,
        align=PP_ALIGN.CENTER)
    txt(s, 12.02, 7.12, .42, .19, str(number), size=11, color=MUTED,
        align=PP_ALIGN.RIGHT)
    return s

def node(s, x, y, w, h, text, *, fill=PALE, fontsize=19, strong=False,
         outline=None, color=INK):
    box(s, x, y, w, h, fill, line=outline)
    txt(s, x+.10, y+.03, w-.20, h-.06, text,
        size=fontsize, color=color, bold=strong, align=PP_ALIGN.CENTER)

def down(s, x, y, *, color=BLUE):
    z=s.shapes.add_shape(MSO_SHAPE.DOWN_ARROW, Inches(x), Inches(y),
                         Inches(.34), Inches(.28))
    z.fill.solid()
    z.fill.fore_color.rgb=color
    z.line.fill.background()

def right(s, x, y, *, color=BLUE):
    z=s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW, Inches(x), Inches(y),
                         Inches(.41), Inches(.24))
    z.fill.solid()
    z.fill.fore_color.rgb=color
    z.line.fill.background()

def headline(s, x, y, w, name):
    box(s, x, y, w, .44, BLUE)
    txt(s, x+.06, y+.02, w-.12, .38, name, size=19, color=WHITE,
        bold=True, align=PP_ALIGN.CENTER)

# Slide 1: motivation
s = slide("自動アノテーション導入の理由", 1,
          "札の外観が比較的一定である点に着目し、画像処理で外枠を推定")
headline(s, .75, 1.56, 5.73, "一般物体の自動アノテーション")
headline(s, 6.80, 1.56, 5.73, "競技かるた札の特徴")
node(s, .87, 2.14, 5.49, 1.25,
     "形状・色・背景が対象ごとに変化しやすい", fontsize=20, fill=LIGHT)
node(s, 6.93, 2.14, 5.47, 1.25,
     "矩形に近い形状／白い札面／有色の縁", fontsize=20, fill=PALE)
node(s, .87, 3.65, 5.49, 1.15,
     "ルールベースでの正確な枠推定は難しい", fontsize=19, fill=LIGHT)
node(s, 6.93, 3.65, 5.47, 1.15,
     "色・輪郭などの画像特徴を利用しやすい", fontsize=19, fill=PALE)
down(s, 6.93+2.54, 4.92)
node(s, 2.05, 5.31, 9.27, .76,
     "OpenCVを用いて外枠候補を自動生成し、必要な画像のみ手動修正",
     fill=BLUE, color=WHITE, strong=True, fontsize=21)
txt(s, 1.13, 6.33, 11.05, .37,
    "ねらい：100札への展開を見据え、1枚ずつ手で枠を指定する作業を削減する",
    size=18, color=NAVY, bold=True, align=PP_ALIGN.CENTER)

# Slide 2: parallel flowchart
s = slide("外枠検出の流れ：正面画像と斜め画像", 2,
          "撮影方向に応じて検出方法を切り替え、最後は同じYOLO形式のラベルを作成")
headline(s, .75, 1.45, 5.68, "正面画像（h01 など）")
headline(s, 6.90, 1.45, 5.68, "動画フレーム・固定角度画像")
left_steps=[
    ("元画像",LIGHT),
    ("グレースケール変換・平滑化",PALE),
    ("白い札面を2値化",PALE),
    ("輪郭抽出・最小外接回転矩形",PALE),
    ("矩形を拡張して外枠を推定",LIGHT),
]
right_steps=[
    ("元画像",LIGHT),
    ("HSV色空間へ変換",PALE),
    ("緑色の外枠を抽出",PALE),
    ("輪郭抽出・凸包・四角形近似",PALE),
    ("札の四隅を推定",LIGHT),
]
for x,steps in ((.85,left_steps),(7.00,right_steps)):
    for i,(name,fill) in enumerate(steps):
        y=2.06+i*.73
        node(s,x,y,5.45,.48,name,fill=fill,fontsize=18,outline=MID_BLUE if i==4 else None)
        if i<4:
            down(s,x+2.53,y+.49)
txt(s, 5.92, 5.40, 1.47, .42, "共通処理", size=17,
    color=BLUE, bold=True, align=PP_ALIGN.CENTER)
down(s, 6.49, 5.87)
node(s, 2.30, 6.18, 8.74, .55,
     "四隅 → 水平矩形 → 正規化したYOLOラベル（class, x, y, w, h）",
     fill=BLUE, color=WHITE, fontsize=18, strong=True)

# Slide 3: algorithm details
s = slide("正面画像：白色領域から外枠を推定", 3)
node(s, .77, 1.49, 3.62, .72, "① グレースケール・ぼかし", strong=True,fontsize=18)
right(s,4.47,1.74)
node(s, 4.96, 1.49, 3.62, .72, "② 白色領域の2値化",strong=True,fontsize=18)
right(s,8.65,1.74)
node(s, 9.14, 1.49, 3.35, .72, "③ 輪郭・回転矩形",strong=True,fontsize=18)
box(s, 1.12, 2.56, 11.00, 1.25, LIGHT, line=MID_BLUE)
txt(s, 1.44, 2.75, 10.38, .82,
    ["大津の2値化（Otsu）／明度105以上の白色抽出",
     "輪郭の面積・縦横比・充填率で候補を選別"],size=18,color=NAVY)
down(s, 6.46, 3.96)
node(s, 2.39, 4.34, 8.55, .82,
     "④ 検出した白い領域を拡張し、緑色の縁を含む外枠を推定",
     fill=BLUE,color=WHITE,strong=True,fontsize=20)
box(s, 1.32, 5.47, 10.70, 1.04, PALE)
txt(s, 1.62, 5.57, 10.13, .82,
    ["初期設定：短辺方向 +10% ／ 長辺方向 +6%",
     "注意：緑色の外枠を直接検出する方法ではない"],size=18,color=NAVY)

# Slide 4: video details and fallback
s = slide("動画画像：緑色の外枠と四隅を推定", 4,
          "斜め撮影による台形変形を考慮した処理")
node(s,.75,1.60,3.42,.78,"① HSVで緑色を抽出",strong=True,fontsize=19)
right(s,4.23,1.85)
node(s,4.72,1.60,3.42,.78,"② Closingで緑を連結",strong=True,fontsize=18)
right(s,8.22,1.85)
node(s,8.69,1.60,3.88,.78,"③ 輪郭を四角形に近似",strong=True,fontsize=18)
box(s,.89,2.75,11.55,.98,LIGHT,line=MID_BLUE)
txt(s,1.13,2.83,11.07,.81,
    ["HSV緑色範囲：H 30〜96、S 26〜255、V 25〜255",
     "凸包（convexHull）→ 多角形近似（approxPolyDP）／4点が難しい場合は回転矩形"],size=17,color=NAVY)
down(s,6.49,3.82)
node(s,2.57,4.18,8.22,.65,"札らしいか判定：面積・位置・縦横比・文字の濃淡",
     fill=PALE,fontsize=18,strong=True)
down(s,6.49,4.92)
node(s,1.06,5.25,5.18,.70,"成功：四隅を確定しラベル生成",fill=BLUE,color=WHITE,strong=True,fontsize=18)
node(s,7.07,5.25,5.18,.70,"失敗：緑の抽出条件を緩めて再探索",fill=AMBER,color=AMBER_INK,strong=True,fontsize=17)
txt(s,7.10,6.13,5.10,.44,"再検出も失敗 → 四隅4点を手動指定",size=16,color=AMBER_INK,bold=True,
    align=PP_ALIGN.CENTER)

# Slide 5: shared output
s = slide("共通処理：四隅からYOLOラベルを生成",5)
headline(s,.91,1.43,5.34,"入力：札の四隅（4点）")
headline(s,7.01,1.43,5.34,"出力：物体検出用ラベル")
node(s,1.20,2.20,4.75,1.16,"(x₁,y₁)  (x₂,y₂)\n(x₃,y₃)  (x₄,y₄)",fontsize=22,fill=LIGHT)
node(s,7.31,2.20,4.75,1.16,"class_id  cx  cy  w  h",fontsize=22,fill=LIGHT)
right(s,6.45,2.68)
box(s,1.04,3.86,11.25,1.24,PALE)
txt(s,1.38,4.01,10.60,.94,
    ["四隅の最小・最大 x/y から画像軸に平行な長方形を取得",
     "中心座標・幅・高さを画像サイズで割り、0〜1に正規化"],size=19,color=NAVY)
node(s,2.11,5.60,9.12,.67,
     "正面と斜め画像は検出方法が違っても、同じ形式で学習に利用できる",
     fill=BLUE,color=WHITE,strong=True,fontsize=18)
txt(s,1.48,6.46,10.50,.28,
    "※ 自動生成したラベルは仮ラベル。プレビュー確認と手動修正を行う。",
    size=15,color=MUTED,align=PP_ALIGN.CENTER)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output",type=Path,default=DEFAULT_OUTPUT)
    a=p.parse_args()
    a.output.parent.mkdir(parents=True,exist_ok=True)
    prs.save(str(a.output))
    print(f"Created {len(prs.slides)} editable slides: {a.output}")
    print("Text boxes, arrows, tables and colored panels are editable shapes.")

if __name__=="__main__":
    main()
