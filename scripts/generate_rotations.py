"""Build green20 YOLO Detect training and validation sets.

Training: independently photographed s01, rotated 0..355 degrees in 5 degree steps.
Validation: independently photographed s02, unchanged.
No test data is used here. Keep future multi-card competition photos untouched for test.

Commands:
    uv run python scripts/generate_rotations.py
    uv run python scripts/generate_rotations.py --overwrite

IMPORTANT: Review every source annotation and its preview before running.
Generated 1440 PNG files can take considerable disk space.
"""
from __future__ import annotations

import argparse
import csv
import shutil
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/green20/top"
ANNOTATIONS = ROOT / "data/annotations"
DEFAULT_OUTPUT = ROOT / "data/datasets/green20_v1"
EXTENSIONS = {".png", ".jpg", ".jpeg"}
HEADERS = ("filename", "card_id", "class_id", "status", "corner_points_px")


def load_image(path: Path) -> np.ndarray:
    image = cv2.imdecode(np.fromfile(str(path), dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"Cannot read image: {path}")
    return image


def save_png(path: Path, image: np.ndarray) -> None:
    ok, encoded = cv2.imencode(".png", image)
    if not ok:
        raise ValueError(f"Cannot encode: {path}")
    encoded.tofile(str(path))


def read_report(path: Path) -> dict[str, dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"Annotation report not found: {path}")
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not set(HEADERS).issubset(reader.fieldnames or []):
            raise ValueError(f"Missing expected columns in {path}")
        rows = list(reader)
    if len(rows) != 20:
        raise ValueError(f"Expected 20 report rows in {path}, found {len(rows)}")
    lookup = {row["filename"]: row for row in rows}
    if len(lookup) != 20:
        raise ValueError(f"Duplicate filenames in {path}")
    for row in rows:
        if row["status"] != "REVIEW":
            raise ValueError(f"Unusable annotation for {row['filename']}: {row['status']}")
    return lookup


def get_corners(row: dict[str, str], image_path: Path, shape: tuple[int, ...]) -> np.ndarray:
    try:
        pts = [tuple(map(float, xy.split(",")))
               for xy in row["corner_points_px"].split(";")]
        corners = np.asarray(pts, dtype=np.float32)
        if corners.shape != (4, 2) or not np.isfinite(corners).all():
            raise ValueError("Expected four finite x,y points")
        if int(row["image_width"]) != shape[1] or int(row["image_height"]) != shape[0]:
            raise ValueError("Report image dimensions differ from source")
        return corners
    except (TypeError, KeyError, ValueError) as exc:
        raise ValueError(f"Invalid corners for {image_path.name}: {exc}") from exc


def xywh_from_corners(points: np.ndarray, width: int, height: int) -> tuple[float, ...]:
    xy0 = points.min(axis=0)
    xy1 = points.max(axis=0)
    # Reject truncation instead of silently clipping a rotated card.
    tolerance = 1.1
    if (xy0 < -tolerance).any() or xy1[0] > width + tolerance or xy1[1] > height + tolerance:
        raise ValueError("Rotated card falls outside image")
    xy0 = np.maximum(xy0, 0)
    xy1 = np.minimum(xy1, [width, height])
    center = (xy0 + xy1) / 2
    size = xy1 - xy0
    values = (center[0] / width, center[1] / height,
              size[0] / width, size[1] / height)
    if not all(0 <= v <= 1 for v in values) or values[2] <= 0 or values[3] <= 0:
        raise ValueError("Invalid normalized bounding box")
    return tuple(float(v) for v in values)


def rotation(image: np.ndarray, corners: np.ndarray, angle: int) -> tuple[np.ndarray, np.ndarray]:
    h, w = image.shape[:2]
    matrix = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
    sine, cosine = abs(matrix[0, 1]), abs(matrix[0, 0])
    out_w = int(np.ceil(h * sine + w * cosine))
    out_h = int(np.ceil(h * cosine + w * sine))
    matrix[0, 2] += out_w / 2 - w / 2
    matrix[1, 2] += out_h / 2 - h / 2
    rotated = cv2.warpAffine(image, matrix, (out_w, out_h),
                             flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT,
                             borderValue=(0, 0, 0))
    transformed = cv2.transform(corners.reshape(1, 4, 2), matrix)[0]
    return rotated, transformed


def write_label(path: Path, class_id: int, bbox: tuple[float, ...]) -> None:
    path.write_text(str(class_id) + " " + " ".join(f"{n:.6f}" for n in bbox) + "\n",
                    encoding="utf-8")


def session_sources(session: str) -> tuple[Path, Path, dict[str, dict[str, str]], list[Path]]:
    source = RAW / f"h01_{session}"
    report = ANNOTATIONS / f"green20_h01_{session}" / "report.csv"
    if not source.is_dir():
        raise FileNotFoundError(f"Source folder missing: {source}")
    lookup = read_report(report)
    images = sorted(p for p in source.iterdir() if p.is_file() and p.suffix.lower() in EXTENSIONS)
    if len(images) != 20:
        raise ValueError(f"Expected 20 images in {source}; found {len(images)}")
    if {p.name for p in images} != set(lookup):
        raise ValueError(f"Report filenames and source images differ for {session}")
    return source, report, lookup, images


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--step", type=int, default=5, help="Angular increment, degrees")
    parser.add_argument("--overwrite", action="store_true",
                        help="Delete existing generated output directory before rebuilding")
    args = parser.parse_args()
    if args.step <= 0 or 360 % args.step != 0:
        parser.error("--step must be a positive divisor of 360")
    output = args.output.resolve()
    if output == ROOT or output == ROOT / "data" or output == RAW or output == ANNOTATIONS:
        parser.error("Unsafe output path")
    if output.exists() and any(output.iterdir()):
        if not args.overwrite:
            parser.error(f"Output is not empty: {output}. Use --overwrite only for generated data.")
        # Constrain destructive operation to project's generated dataset directory.
        if output != DEFAULT_OUTPUT.resolve():
            parser.error("--overwrite is only allowed for the default generated dataset directory")
        shutil.rmtree(output)

    _, _, train_rows, train_images = session_sources("s01")
    _, _, val_rows, val_images = session_sources("s02")

    with (ROOT / "data/metadata/green20_cards.csv").open(
            "r", encoding="utf-8-sig", newline="") as f:
        cards = list(csv.DictReader(f))
    card_to_class = {int(c["card_id"]): i for i, c in enumerate(cards)}
    if len(cards) != 20 or len(card_to_class) != 20:
        raise ValueError("Expected 20 unique cards in mapping CSV")

    # Ensure labels exist and are consistent before starting generation.
    for session, rows, photos in (("s01", train_rows, train_images),
                                  ("s02", val_rows, val_images)):
        for photo in photos:
            row = rows[photo.name]
            if int(row["card_id"]) not in card_to_class:
                raise ValueError(f"Unknown card: {photo.name}")
            if int(row["class_id"]) != card_to_class[int(row["card_id"])]:
                raise ValueError(f"Incorrect class for {photo.name}")
            if f"_top_h01_{session}" not in photo.stem:
                raise ValueError(f"Unexpected filename: {photo.name}")
            label = ANNOTATIONS / f"green20_h01_{session}" / "labels" / (photo.stem + ".txt")
            if not label.is_file():
                raise FileNotFoundError(f"Missing source label: {label}")

    for split in ("train", "val"):
        (output / "images" / split).mkdir(parents=True, exist_ok=True)
        (output / "labels" / split).mkdir(parents=True, exist_ok=True)

    count = 0
    for i, photo in enumerate(train_images, 1):
        image = load_image(photo)
        row = train_rows[photo.name]
        corners = get_corners(row, photo, image.shape)
        class_id = int(row["class_id"])
        for angle in range(0, 360, args.step):
            transformed_image, transformed_corners = rotation(image, corners, angle)
            hh, ww = transformed_image.shape[:2]
            bbox = xywh_from_corners(transformed_corners, ww, hh)
            name = f"{photo.stem}_rot{angle:03d}"
            save_png(output / "images/train" / f"{name}.png", transformed_image)
            write_label(output / "labels/train" / f"{name}.txt", class_id, bbox)
            count += 1
        print(f"Train {i:02d}/20: {photo.name} -> {360 // args.step} images")

    for i, photo in enumerate(val_images, 1):
        image = load_image(photo)
        row = val_rows[photo.name]
        corners = get_corners(row, photo, image.shape)
        bbox = xywh_from_corners(corners, image.shape[1], image.shape[0])
        # PNG output even if original was JPEG, no resampling or augmentation.
        save_png(output / "images/val" / f"{photo.stem}.png", image)
        write_label(output / "labels/val" / f"{photo.stem}.txt",
                    int(row["class_id"]), bbox)
        print(f"Val   {i:02d}/20: {photo.name}")

    yaml_file = output / "data.yaml"
    names = [str(c["card_id"]).zfill(3) for c in cards]
    lines = [f"path: '{output.as_posix()}'", "train: images/train", "val: images/val",
             "nc: 20", "names:"]
    lines.extend(f"  {i}: '{name}'" for i, name in enumerate(names))
    yaml_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nFinished: {count} training images + {len(val_images)} validation images")
    print(f"Dataset: {output}\nYAML: {yaml_file}")
    print("No test set was created. Keep future multi-card test photographs independent.")


if __name__ == "__main__":
    main()
