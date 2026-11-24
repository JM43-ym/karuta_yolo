"""Create editable blue-accented slides: annotation tradeoffs and 5-frame extraction.

Source of algorithm: scripts/capture/extract_karuta_frames.py
Run from repository root:
    uv run --no-sync --with python-pptx python scripts/presentation/create_annotation_comparison_frames_slides.py

PowerPoint shapes/text/tables remain editable. No image-generation placeholders
are required. The slides explain the current implementation, not a proposed one.
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
DEFAULT = ROOT / "reports" / "YOLO_annotation_comparison_5frames_editable.pptx"
C = {
    "blue": RGBColor(39, 106, 156),
    "navy": RGBColor(30, 63, 96),
    "light": RGBColor(234, 244, 251),
    "pale": RGBColor(246, 250, 253),
    "white": RGBColor(255, 255, 255),
    "ink": RGBColor(30, 43, 60),
    "muted": RGBColor(92, 111, 132),
    "line": RGBColor(175, 207, 228),
    "accent": RGBColor(56, 141, 185),
    "orange": RGBColor(237, 171, 78),
}
prs=Presentation()
prs.slide_width=Inches(13.333)
prs.slide_height=Inches(7.5)

def rect(sl,x,y,w,h,fill="light",outline=None,rounding=True):
    sh=sl.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE if rounding else MSO_SHAPE.RECTANGLE,
         Inches(x),Inches(y),Inches(w),Inches(h))
    sh.fill.solid()
    sh.fill.fore_color.rgb=C[fill]
    if outline:
        sh.line.color.rgb=C[outline]
        sh.line.width=Pt(1.15)
    else:
        sh.line.fill.background()
    return sh

def text(sl,x,y,w,h,value,size=19,bold=False,color="ink",center=False):
    sh=sl.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    frame=sh.text_frame
    frame.clear()
    frame.word_wrap=True
    frame.vertical_anchor=MSO_ANCHOR.MIDDLE
    frame.margin_left=Inches(.05)
    frame.margin_right=Inches(.05)
    frame.margin_top=Inches(.015)
    frame.margin_bottom=Inches(.015)
    for i,line in enumerate(value if isinstance(value,(list,tuple)) else [value]):
        par=frame.paragraphs[0] if i==0 else frame.add_paragraph()
        par.text=str(line)
        par.font.name="Yu Gothic"
        par.font.size=Pt(size)
        par.font.bold=bold
        par.font.color.rgb=C[color]
        par.alignment=PP_ALIGN.CENTER if center else PP_ALIGN.LEFT
        par.space_after=Pt(5)
    return sh

def page(title,n,subtitle=None):
    sl=prs.slides.add_slide(prs.slide_layouts[6])
    text(sl,.55,.13,12.2,.65,title,30,True,center=True)
    rect(sl,.48,.89,12.35,.035,"blue",rounding=False)
    if subtitle:
        text(sl,.72,.99,11.90,.43,subtitle,16,color="muted",center=True)
    rect(sl,.64,7.05,12.05,.016,"accent",rounding=False)
    text(sl,.75,7.11,4,.22,"競技かるた札認識／アノテーション",10,color="muted")
    text(sl,12.03,7.11,.38,.22,str(n),11,color="muted",center=True)
    return sl

def label(sl,x,y,w,title):
    rect(sl,x,y,w,.48,"blue")
    text(sl,x+.07,y+.01,w-.14,.44,title,19,True,"white",True)

def pill(sl,x,y,w,h,value,fill="light",size=18):
    rect(sl,x,y,w,h,fill,"line" if fill!="blue" else None)
    text(sl,x+.05,y+.03,w-.10,h-.06,value,size,fill=="blue","white" if fill=="blue" else "navy",True)

def arrow(sl,x,y,d="down"):
    typ=MSO_SHAPE.DOWN_ARROW if d=="down" else MSO_SHAPE.RIGHT_ARROW
    sh=sl.shapes.add_shape(typ,Inches(x),Inches(y),Inches(.33 if d=="down" else .40),Inches(.26))
    sh.fill.solid()
    sh.fill.fore_color.rgb=C["accent"]
    sh.line.fill.background()

def bullets(sl,x,y,w,items,step=.66,sz=18):
    for i,v in enumerate(items):
        text(sl,x,y+i*step,w,step-.03,"● "+v,sz,color="navy")

# Slide 1: clear pros/cons comparison
sl=page("自動アノテーション：2方式のメリット・デメリット",1,
        "撮影角度によって札の見え方が異なるため、特徴量を使い分ける")
label(sl,.72,1.50,5.82,"正面：白い札面 → 矩形を拡張")
label(sl,6.79,1.50,5.82,"斜め：緑の外枠 → 四隅を推定")
rect(sl,.72,2.13,5.82,1.72,"pale","line")
rect(sl,6.79,2.13,5.82,1.72,"pale","line")
text(sl,.95,2.23,5.40,.41,"メリット",20,True,"blue")
bullets(sl,1.03,2.69,5.20,["暗い背景なら白色を抽出しやすい","処理が比較的単純・高速"],.46,18)
text(sl,7.01,2.23,5.30,.41,"メリット",20,True,"blue")
bullets(sl,7.08,2.69,5.25,["外枠を直接検出できる","台形など遠近変形に対応しやすい"],.46,18)
rect(sl,.72,4.05,5.82,1.75,"pale","line")
rect(sl,6.79,4.05,5.82,1.75,"pale","line")
text(sl,.95,4.17,5.35,.40,"デメリット",20,True,"navy")
bullets(sl,1.03,4.59,5.25,["枠の厚みは拡張率による推定","台形変形・明るい背景に弱い"],.46,18)
text(sl,7.01,4.17,5.30,.40,"デメリット",20,True,"navy")
bullets(sl,7.08,4.59,5.22,["反射・暗さ・低彩度に影響される","緑色の類似背景を誤検出し得る"],.46,18)
pill(sl,1.13,6.15,11.04,.57,
     "使い分けの理由：正面は矩形近似で十分／斜めは遠近変形を四隅で捉える",size=19)

# Slide 2: why split and caveat, visual geometry diagram
sl=page("なぜ正面画像と斜め画像で検出法を分けたか",2,
        "対象の形状と、撮影時に生じる遠近変形の違い")
label(sl,.86,1.49,5.44,"正面画像")
label(sl,7.02,1.49,5.44,"斜め画像")
# editable card shapes (schematic, not photographs)
rect(sl,1.93,2.16,3.18,1.51,"pale","line")
card=rect(sl,3.00,2.26,1.00,1.28,"white","blue",False)
rect(sl,2.77,2.09,1.46,1.62,"pale","orange",False)
text(sl,1.94,3.89,3.12,.47,"白領域を回転矩形で近似",18,True,"navy",True)
rect(sl,8.08,2.16,3.18,1.51,"pale","line")
sh=sl.shapes.add_shape(MSO_SHAPE.TRAPEZOID, Inches(9.13), Inches(2.30), Inches(1.22), Inches(1.14))
sh.fill.solid(); sh.fill.fore_color.rgb=C["white"];sh.line.color.rgb=C["blue"];sh.line.width=Pt(2)
text(sl,7.50,3.89,4.38,.47,"緑色の輪郭を四角形近似",18,True,"navy",True)
rect(sl,1.22,4.61,10.91,.91,"light","line")
text(sl,1.51,4.75,10.38,.61,
     "正面：白面＋一定の拡張率で簡易推定　／　斜め：緑枠の四隅から台形形状を推定",
     18,True,"navy",True)
rect(sl,1.22,5.78,10.91,.77,"pale","line")
text(sl,1.50,5.86,10.38,.59,
     "※ 2方式を同一画像で定量比較した結果ではなく、撮影条件に合わせた実装上の選択",
     16,color="muted",center=True)

# Slide 3: algorithm flow
sl=page("動画から5フレームを抽出する流れ",3,
        "時刻の5等分ではなく、画像の変化量と鮮明さで選択する")
flow=[
    ("① 動画を読み込み、各フレームの中央付近を解析", "背景端の変化を抑える"),
    ("② グレー化・平滑化し、64×64に縮小", "フレーム間の比較に使用"),
    ("③ 前後フレームの画素差を算出・平滑化", "小さな揺れやノイズを低減"),
    ("④ 画像変化量を累積し、0〜1に正規化", "視点変化の進行度を近似"),
    ("⑤ 進行度を5等分して近傍の鮮明な画像を選択", "ラプラシアン分散で鮮明さ評価"),
    ("⑥ 選んだ元解像度フレームをPNG保存", "抽出記録CSVにも保存"),
]
for i,(a,b) in enumerate(flow):
    yy=1.49+i*.83
    rect(sl,.79,yy,8.16,.57,"light","line")
    text(sl,1.02,yy+.04,7.76,.50,a,19,True,"navy")
    rect(sl,9.22,yy,3.26,.57,"pale","line")
    text(sl,9.39,yy+.04,2.96,.48,b,15,color="muted",center=True)
    if i<5:arrow(sl,4.73,yy+.59)
text(sl,1.00,6.55,11.45,.30,
     "対象：LR / FB の各動画。デフォルト5枚（--per-videoで変更可能）",14,color="muted",center=True)

# Slide 4: conceptual progress
sl=page("「時間」ではなく「画像変化の進行度」で分散して選ぶ",4,
        "撮影速度が一定でなくても、似た視点ばかり選ばないことを目指す")
label(sl,.82,1.43,11.68,"比較イメージ（模式図）")
text(sl,1.01,2.09,3.55,.34,"時間を5等分した場合",20,True,"navy")
text(sl,1.01,4.24,4.20,.34,"画像変化の進行度を5等分",20,True,"navy")
def timeline(y,marks,labels):
    # editable horizontal bar and markers
    rect(sl,1.13,y,10.97,.035,"line",rounding=False)
    for i,f in enumerate(marks):
        x=1.13+10.97*f
        rect(sl,x-.07,y-.16,.14,.36,"blue",rounding=False)
        text(sl,x-.39,y+.34,.78,.32,labels[i],13,color="navy",center=True)
timeline(3.06,[.12,.31,.50,.69,.88],["1","2","3","4","5"])
timeline(5.19,[.10,.23,.44,.73,.92],["1","2","3","4","5"])
text(sl,1.08,3.55,11.35,.44,
     "録画中の動きが偏ると、同じ姿勢に近いフレームが選ばれやすい",17,color="muted")
text(sl,1.08,5.65,11.35,.45,
     "変化が集中する区間を考慮し、視点の変化に沿って候補を広げる",17,color="muted")
rect(sl,1.11,6.24,11.15,.45,"pale","line")
text(sl,1.27,6.29,10.82,.34,
     "注意：実際の角度（例：30°・45°）を測定したものではない",16,True,"navy",True)

# Slide 5: precise selection factors, pros and limitations
sl=page("5フレーム選択：鮮明さも考慮",5,
        "目標位置に近いフレームから、ぶれの少ない画像を優先して選ぶ")
label(sl,.80,1.48,5.77,"選択で重視する2つの指標")
label(sl,6.81,1.48,5.77,"利点と注意点")
rect(sl,.84,2.17,5.67,1.12,"light","line")
text(sl,1.07,2.27,5.22,.88,["画像変化の進行度への近さ",
                                "→ 似た視点への偏りを軽減"],19,True,"navy")
rect(sl,.84,3.53,5.67,1.12,"light","line")
text(sl,1.07,3.65,5.22,.85,["ラプラシアン分散（鮮明さ）",
                                "→ ぶれの少ないフレームを優先"],19,True,"navy")
rect(sl,6.84,2.16,5.70,1.12,"pale","line")
text(sl,7.05,2.27,5.22,.86,["メリット：撮影速度差にある程度対応",
                               "動画ごとに相対的な基準で選ぶ"],18,True,"navy")
rect(sl,6.84,3.53,5.70,1.24,"pale","line")
text(sl,7.05,3.64,5.24,.96,["注意：画素差≠正確なカメラ移動角",
                              "照明・ぶれ・背景変化の影響を受ける"],17,True,"navy")
pill(sl,1.28,5.20,10.78,.70,
     "1動画 → 原則5枚を選択 → 目視確認 → 自動アノテーションへ",size=20)
text(sl,1.31,6.17,10.79,.54,
     "補足：冒頭・末尾約3%を候補から除外。変化量がほぼゼロなら時間方向の進行度を代用。",
     16,color="muted",center=True)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--output",type=Path,default=DEFAULT)
    a=ap.parse_args()
    a.output.parent.mkdir(parents=True,exist_ok=True)
    prs.save(str(a.output))
    print(f"Created {len(prs.slides)} editable slides: {a.output}")
    print("Text, diagrams, markers and comparison panels are editable in PowerPoint.")

if __name__=="__main__":
    main()
