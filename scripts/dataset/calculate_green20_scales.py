"""Calculate 3 relative card scales from reviewed h01/h02/h03 annotations.

Safe/read-only for images and annotations. Does not build any dataset.
Run:
  uv run --no-sync python scripts/dataset/calculate_green20_scales.py
Output:
  reports/green20_scales_YYYYMMDD_HHMMSS.csv
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/raw/green20/train/single/top"
ANNOTATIONS = ROOT / "data/annotations/green20"
METADATA = ROOT / "data/metadata/green20_cards.csv"
EXT = {".png", ".jpg", ".jpeg"}


def read_report(path: Path):
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def measure(height: str, session: str, expected_ids: set[int]):
    image_dir = RAW / f"{height}_{session}"
    annotation_dir = ANNOTATIONS / f"green20_{height}_{session}"
    report_path = annotation_dir / "report.csv"
    if not image_dir.is_dir():
        raise FileNotFoundError(f"撮影画像のフォルダがありません: {image_dir}")
    if not report_path.is_file():
        raise FileNotFoundError(f"アノテーションのreport.csvがありません: {report_path}")
    images = {p.name: p for p in image_dir.iterdir()
              if p.is_file() and p.suffix.lower() in EXT}
    rows = read_report(report_path)
    if len(images) != 20 or len(rows) != 20:
        raise ValueError(f"{height}: 画像・レポートは各20件必要です (画像={len(images)}, レポート={len(rows)})")
    if len({r["filename"] for r in rows}) != 20 or set(images) != {r["filename"] for r in rows}:
        raise ValueError(f"{height}: 画像名とreport.csvのfilenameが一致していません")
    fractions = []
    seen_ids = set()
    details = []
    for row in rows:
        name = row["filename"]
        card_id = int(row["card_id"])
        if card_id not in expected_ids or card_id in seen_ids:
            raise ValueError(f"{height}: 札番号の重複または不明な番号: {card_id}")
        seen_ids.add(card_id)
        if row["status"] != "REVIEW":
            raise ValueError(f"{height}: 未確認または検出失敗の画像: {name}, {row['status']}")
        if f"_top_{height}_{session}" not in Path(name).stem:
            raise ValueError(f"{height}: 画像名の高さ/セッションが不一致: {name}")
        label_path = annotation_dir / "labels" / f"{Path(name).stem}.txt"
        if not label_path.is_file():
            raise FileNotFoundError(f"{height}: ラベルがありません: {label_path}")
        image = cv2.imdecode(np.fromfile(str(images[name]), dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f"画像を開けません: {images[name]}")
        h, w = image.shape[:2]
        if int(row["image_width"]) != w or int(row["image_height"]) != h:
            raise ValueError(f"{height}: report.csvの画像サイズが元画像と違います: {name}")
        raw_points = row.get("corner_points_px", "")
        points = np.asarray([list(map(float, p.split(","))) for p in raw_points.split(";")],
                            dtype=np.float32)
        if points.shape != (4, 2) or not np.isfinite(points).all():
            raise ValueError(f"{height}: 四隅座標が不正です: {name}")
        area = abs(float(cv2.contourArea(points)))
        fraction = area / (w * h)
        if not (0.0001 < fraction < 0.95):
            raise ValueError(f"{height}: 札の相対面積が不正です: {name}, {fraction:.6f}")
        apparent_size = float(np.sqrt(fraction))
        fractions.append(apparent_size)
        details.append((height, session, card_id, name, w, h, area, fraction, apparent_size))
    if seen_ids != expected_ids:
        raise ValueError(f"{height}: 緑20札の札番号が全件揃っていません")
    return float(np.median(fractions)), details


def main():
    ap = argparse.ArgumentParser(description="緑20札のh01/h02/h03倍率を再計算（画像の変更なし）")
    ap.add_argument("--output", type=Path, default=None, help="出力CSVのパス（省略時はreports/に日時付きで保存）")
    args = ap.parse_args()
    with METADATA.open(encoding="utf-8-sig", newline="") as f:
        ids = {int(row["card_id"]) for row in csv.DictReader(f)}
    if len(ids) != 20:
        raise ValueError("green20_cards.csvには札番号20種類が必要です")
    samples = {}
    all_details = []
    for height in ("h01", "h02", "h03"):
        value, details = measure(height, "s01", ids)
        samples[height] = value
        all_details.extend(details)
    h01 = samples["h01"]
    scale_values = {h: samples[h] / h01 for h in ("h01", "h02", "h03")}
    print("\n=== h01を基準にした3倍率（札の見かけの大きさ） ===")
    for h in ("h01", "h02", "h03"):
        print(f"{h}: size={samples[h]:.7f} / scale={scale_values[h]:.5f}")
    print("※ 20札の sqrt(札四角形面積/画像面積) の中央値を使用")
    output = (args.output or
              ROOT / "reports" / f"green20_scales_{datetime.now():%Y%m%d_%H%M%S}.csv")
    if not output.is_absolute():
        output = ROOT / output
    if output.exists():
        raise FileExistsError(f"既存ファイルには上書きできません: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["height", "session", "normalized_card_size_median",
                         "applied_scale_from_h01", "cards"])
        for h in ("h01", "h02", "h03"):
            writer.writerow([h, "s01", f"{samples[h]:.7f}", f"{scale_values[h]:.5f}", 20])
    print(f"\n保存先: {output}")
    print("元画像・アノテーション・データセットは変更していません。")


if __name__ == "__main__":
    main()
