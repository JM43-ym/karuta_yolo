"""Build a local visual review gallery of provisional YOLO video annotations.

Example:
  uv run --no-sync python scripts/review_karuta_annotations.py --color green20
Creates data/annotations/video_frames/green20/review_gallery.html.
Open that HTML with your usual browser. Images/labels are never modified.
"""
from __future__ import annotations
import sys as _sys
from pathlib import Path as _Path
_SCRIPTS_DIR = _Path(__file__).resolve().parents[1]
if str(_SCRIPTS_DIR) not in _sys.path:
    _sys.path.insert(0, str(_SCRIPTS_DIR))


import argparse
import csv
import html
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
COLORS = ("green20", "blue20", "pink20", "yellow20", "orange20")
CARD = re.compile(r"^card_(\d{3})_(LR|FB)_h01_(s\d+)_f(\d{6})\.png$", re.I)


def safe_href(root: Path, target: Path) -> str:
    # Use a relative path with forward slashes for Windows file:// browser display.
    import os
    return Path(os.path.relpath(target, root)).as_posix()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--color", choices=COLORS, required=True)
    ap.add_argument("--session", default="s01")
    args = ap.parse_args()
    with (ROOT / "data/metadata" / f"{args.color}_cards.csv").open(
            encoding="utf-8-sig", newline="") as f:
        cards = list(csv.DictReader(f))
    out = ROOT / "data/annotations/video_frames" / args.color
    out.mkdir(parents=True, exist_ok=True)
    target = out / "review_gallery.html"
    entries = []
    for card in cards:
        cid = int(card["card_id"])
        for direction in ("LR", "FB"):
            frames = (ROOT / "data/raw" / args.color / "train/single/oblique/extracted" /
                      f"h01_{args.session}" / direction)
            annotations = out / f"h01_{args.session}" / (direction + "_annotated")
            preview_dir = annotations / "previews"
            label_dir = annotations / "labels"
            report = annotations / "annotation_report.csv"
            statuses = {}
            if report.exists():
                with report.open(encoding="utf-8-sig",newline="") as f:
                    statuses = {r["image"]:r.get("status","") for r in csv.DictReader(f)}
            paths = sorted(frames.glob(f"card_{cid:03d}_{direction}_h01_{args.session}_f*.png"))
            for path in paths:
                if CARD.fullmatch(path.name) is None:
                    continue
                preview = preview_dir / (path.stem+".jpg")
                label = label_dir / (path.stem+".txt")
                preview_exists = preview.is_file()
                label_exists = label.is_file()
                status = statuses.get(path.name, "NO_REPORT")
                if not preview_exists or not label_exists:
                    status = "NEEDS_REVIEW: missing preview/label" if status in ("REVIEW", "SKIPPED_EXISTING_LABEL") else status
                entries.append((card, direction, path, preview, preview_exists, label, label_exists, status))

    counts = Counter(x[-1] for x in entries)
    blocks = []
    for card in cards:
        cid = int(card["card_id"])
        group = html.escape(card["group_id"])
        prefix = html.escape(card["decision_prefix"])
        bits = [f'<section><h2>{group} / {cid:03d} — {prefix}</h2><div class="grid">']
        for entry in entries:
            row, direction, source, preview, has_preview, label, has_label, status = entry
            if int(row["card_id"]) != cid:
                continue
            img = preview if has_preview else source
            img_src = html.escape(safe_href(out,img),quote=True)
            source_href = html.escape(safe_href(out,source),quote=True)
            label_href = html.escape(safe_href(out,label),quote=True) if has_label else ""
            rectified = preview.parent.parent / "rectified" / (source.stem + ".png")
            rectified_link = (f' · <a href="{html.escape(safe_href(out,rectified),quote=True)}">射影補正</a>'
                              if rectified.is_file() else "")
            status_html = html.escape(status)
            cl = "warn" if (status.startswith("FAIL") or "missing" in status or status=="NO_REPORT") else "normal"
            bits.append(
                f'<article class="{cl}">'
                f'<a href="{source_href}"><img loading="lazy" src="{img_src}" alt="{cid:03d} {direction}"></a>'
                f'<div class="meta"><strong>{direction}</strong> · {html.escape(source.stem.split("_")[-1])}</div>'
                f'<div class="status">{status_html}</div>'
                + (f'<a href="{label_href}">YOLO label</a>' if has_label else '<span>NO LABEL</span>')
                + rectified_link
                + '</article>'
            )
        bits.append("</div></section>")
        blocks.append("".join(bits))
    missing = 40-len({(int(e[0]["card_id"]),e[1]) for e in entries})
    summary = ", ".join(f"{html.escape(k)}: {n}" for k,n in sorted(counts.items()))
    doc = """<!doctype html>
<html lang="ja"><head><meta charset="utf-8"><title>Karuta Annotation Review</title>
<style>
body{font-family:system-ui,'Yu Gothic',sans-serif;margin:22px;background:#f4f6f8;color:#1b2631}
h1{margin-bottom:8px}p{line-height:1.6}section{margin:22px 0 28px;padding:16px;background:white;border:1px solid #e0e4e8;border-radius:12px}
h2{font-size:19px;margin:0 0 12px}.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(210px,1fr));gap:12px}
article{border:1px solid #d9e0e5;border-radius:8px;padding:7px;background:#fbfcfd}
article.warn{border-color:#df8e6b;background:#fff7f1}
article img{width:100%;height:160px;object-fit:contain;background:#e8ebed}
.meta,.status{font-size:12px;margin-top:6px;overflow-wrap:anywhere}a{color:#1263a3}
.status{font-weight:600}
</style></head><body>
"""
    doc += f"<h1>{html.escape(args.color)} アノテーション確認一覧</h1>"
    doc += (f"<p>合計 {len(entries)} フレーム / 撮影未検出の札×方向 {missing} 件。"
            f"各画像をクリックすると元PNGを開きます。<br>状態: {summary or 'まだ抽出画像なし'}</p>")
    doc += ("<p><b>注意：</b>プレビューの四隅・外接枠・札番号を目視で確認してください。"
            " REVIEWは未承認です。失敗画像は手動アノテーションが必要です。"
            "このHTMLで画像を見てもラベルは承認・修正されません。</p>")
    doc += "".join(blocks) + "</body></html>"
    target.write_text(doc, encoding="utf-8")
    print(f"Open in a browser: {target}")
    print(f"Frames: {len(entries)}, missing color-card/direction recordings: {missing}")
    print(f"Statuses: {dict(counts)}")
    print("Gallery is for visual review only; does not approve/correct labels.")


if __name__ == "__main__":
    main()
