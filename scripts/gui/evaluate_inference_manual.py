"""Manual YOLO inference audit GUI: 10 test images, 5x4 missed positions,
20 missed card IDs and 20x20 true-vs-predicted misclassification matrix.

From repository root:
    uv run --no-sync python scripts/gui/evaluate_inference_manual.py

Only Python standard library is required (tkinter).
Left-click cell: +1; right-click or Shift+left-click: -1.
All edits autosave to runs/manual_evaluation/review.json.
"""
from __future__ import annotations

import csv
import json
import os
import shutil
import tempfile
from datetime import datetime
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

ROOT = Path(__file__).resolve().parents[2]
META = ROOT / "data/metadata/green20_cards.csv"
DEFAULT_DIR = ROOT / "runs/manual_evaluation"
DEFAULT_DATA = DEFAULT_DIR / "review.json"
N_IMAGES = 10
ROWS, COLS = 5, 4

BG = "#f4f8fb"
DARK = "#20394f"
GREEN = "#bceacb"
GREEN_HOVER = "#7fcba1"
BLUE = "#e5f0fa"
RED = "#fce8e6"


def load_cards():
    with META.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 20:
        raise ValueError(f"緑札20枚のカード定義が必要です: {META}")
    return [(str(int(row["card_id"])).zfill(3), row["decision_prefix"]) for row in rows]


def new_data():
    return {
        "version": 1,
        "images": [
            {
                "name": f"テスト画像 {i+1:02d}",
                "missing": [[0 for _ in range(COLS)] for _ in range(ROWS)],
                "missing_cards": [0 for _ in range(20)],
                "misclassified": [[0 for _ in range(20)] for _ in range(20)],
            }
            for i in range(N_IMAGES)
        ],
    }


def migrate(data):
    """Add missed-card counts to older saved projects without losing existing data."""
    if isinstance(data, dict) and isinstance(data.get("images"), list):
        for item in data["images"]:
            if isinstance(item, dict) and "missing_cards" not in item:
                item["missing_cards"] = [0] * 20
    return data


def validate(data):
    if not isinstance(data, dict) or not isinstance(data.get("images"), list) or len(data["images"]) != N_IMAGES:
        raise ValueError("データ形式が異なります（テスト画像10枚が必要）。")
    for index, item in enumerate(data["images"], 1):
        if not isinstance(item.get("name"), str):
            raise ValueError(f"画像{index}: 名前が不正です")
        for field, height, width in (("missing", ROWS, COLS), ("misclassified", 20, 20)):
            mat = item.get(field)
            if not isinstance(mat, list) or len(mat) != height:
                raise ValueError(f"画像{index}: {field} の行数が不正です")
            for row in mat:
                if not isinstance(row, list) or len(row) != width or any(
                    type(x) is not int or x < 0 for x in row
                ):
                    raise ValueError(f"画像{index}: {field} に不正なカウントがあります")
        counts = item.get("missing_cards")
        if (not isinstance(counts, list) or len(counts) != 20 or
                any(type(x) is not int or x < 0 for x in counts)):
            raise ValueError(f"画像{index}: 未検出札の件数が不正です")
        if any(item["misclassified"][i][i] != 0 for i in range(20)):
            raise ValueError(f"画像{index}: 誤分類表の対角線に値があります")


def atomic_save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".manual_", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


class App:
    def __init__(self, root):
        self.root = root
        self.cards = load_cards()
        self.path = DEFAULT_DATA
        self.backed_up_paths = set()
        self.data = new_data()
        if self.path.exists():
            with self.path.open(encoding="utf-8") as f:
                self.data = migrate(json.load(f))
            validate(self.data)

        self.selected = 0  # 0..9 for a test image; 10 for aggregate
        self.name_var = tk.StringVar()
        self.status_var = tk.StringVar()
        self.view_var = tk.StringVar()
        self.totals_var = tk.StringVar()
        self.miss_buttons = []
        self.missed_card_buttons = []
        self.matrix_buttons = []
        self.pred_count_labels = []
        self.actual_count_labels = []

        root.title("YOLO 推論結果：手動集計（緑20札 / テスト画像10枚）")
        root.geometry("1550x950")
        root.minsize(1090, 640)
        root.configure(bg=BG)
        self.build()
        self.refresh()
        root.protocol("WM_DELETE_WINDOW", self.close)

    def build(self):
        header = ttk.Frame(self.root, padding=(12, 12, 12, 4))
        header.pack(fill="x")
        ttk.Label(header, text="YOLO推論・手動集計", font=("Yu Gothic UI", 19, "bold")).pack(side="left", padx=(0, 15))

        self.view = ttk.Combobox(header, textvariable=self.view_var, width=23, state="readonly")
        self.view["values"] = [f"{i+1:02d}：テスト画像" for i in range(10)] + ["10枚合計（閲覧のみ）"]
        self.view.pack(side="left", padx=5)
        self.view.bind("<<ComboboxSelected>>", self.select_image)

        ttk.Label(header, text="画像名").pack(side="left", padx=(13, 4))
        self.name_entry = ttk.Entry(header, textvariable=self.name_var, width=30)
        self.name_entry.pack(side="left", padx=4)
        self.name_entry.bind("<Return>", self.rename)
        ttk.Button(header, text="名前を保存", command=self.rename).pack(side="left", padx=3)
        ttk.Button(header, text="CSV出力", command=self.export).pack(side="right", padx=3)
        ttk.Button(header, text="既存データを開いて追記", command=self.open_data).pack(side="right", padx=3)
        ttk.Button(header, text="別名保存", command=self.save_as).pack(side="right", padx=3)

        ttk.Label(
            self.root,
            text="左クリック：+1回 ／ 右クリック（またはShift+クリック）：−1回 ／ 10枚合計は編集不可・自動集計",
            foreground="#526c80", padding=(14, 3),
        ).pack(anchor="w")
        ttk.Label(self.root, textvariable=self.totals_var, font=("Yu Gothic UI", 12, "bold"), padding=(14, 4)).pack(anchor="w")

        self.workspace = ttk.Panedwindow(self.root, orient="horizontal")
        self.workspace.pack(fill="both", expand=True, padx=10, pady=4)

        left = ttk.LabelFrame(self.workspace, text="未検出：位置と札番号", padding=10)
        right = ttk.LabelFrame(self.workspace, text="誤分類：縦＝正解札 ／ 横＝予測札（20 × 20）", padding=8)
        self.workspace.add(left, weight=2)
        self.workspace.add(right, weight=3)

        ttk.Label(left, text="画像の上側", font=("Yu Gothic UI", 10)).pack(pady=(0, 7))
        miss_grid = ttk.Frame(left)
        miss_grid.pack(fill="x", padx=8)
        for row in range(ROWS):
            line = []
            for col in range(COLS):
                b = tk.Button(miss_grid, text="0", bg=GREEN, activebackground=GREEN_HOVER,
                              font=("Yu Gothic UI", 17, "bold"), width=5, height=2,
                              relief="ridge", bd=1, cursor="hand2")
                b.grid(row=row, column=col, padx=3, pady=4, sticky="nsew")
                b.bind("<Button-1>", lambda e, r=row, c=col: self.click_miss(r, c, -1 if e.state & 0x1 else 1))
                b.bind("<Button-3>", lambda e, r=row, c=col: self.click_miss(r, c, -1))
                line.append(b)
                miss_grid.columnconfigure(col, weight=1)
            self.miss_buttons.append(line)
        ttk.Label(left, text="画像の下側", font=("Yu Gothic UI", 10)).pack(pady=(6, 13))
        ttk.Separator(left).pack(fill="x", pady=3)
        ttk.Label(left, text="位置ごとの未検出件数を入力します。\n1枚のテスト画像で複数件あれば、その分クリックしてください。",
                  justify="left", wraplength=295).pack(anchor="w", pady=8)
        ttk.Label(left, text="※ 行：上→下、列：左→右", foreground="#526c80").pack(anchor="w", pady=(0, 6))
        ttk.Separator(left).pack(fill="x", pady=(5, 10))
        ttk.Label(left, text="未検出した札（札番号・決まり字）", font=("Yu Gothic UI", 12, "bold")).pack(anchor="w")
        ttk.Label(left, text="未検出の札をクリックして記録します。位置と札は別々にカウントします。",
                  foreground="#526c80", wraplength=390, justify="left").pack(anchor="w", pady=(3, 8))
        card_grid = ttk.Frame(left)
        card_grid.pack(fill="x")
        for i, (card_id, prefix) in enumerate(self.cards):
            b = tk.Button(card_grid, text=f"{card_id} {prefix}\n0件", font=("Yu Gothic UI", 10),
                          bg="#edf4ff", activebackground="#b7d8fa", fg=DARK,
                          width=13, height=2, relief="ridge", bd=1, cursor="hand2")
            b.grid(row=i // 4, column=i % 4, padx=2, pady=2, sticky="nsew")
            b.bind("<Button-1>", lambda e, n=i: self.click_missed_card(n, -1 if e.state & 0x1 else 1))
            b.bind("<Button-3>", lambda e, n=i: self.click_missed_card(n, -1))
            card_grid.columnconfigure(i % 4, weight=1)
            self.missed_card_buttons.append(b)

        # Two-axis scrolling lets the complete 20x20 matrix remain usable
        # without shrinking the Japanese card labels too far.
        outer = ttk.Frame(right)
        outer.pack(fill="both", expand=True)
        canvas = tk.Canvas(outer, bg="#fff", highlightthickness=0)
        ys = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        xs = ttk.Scrollbar(outer, orient="horizontal", command=canvas.xview)
        canvas.configure(yscrollcommand=ys.set, xscrollcommand=xs.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        ys.grid(row=0, column=1, sticky="ns")
        xs.grid(row=1, column=0, sticky="ew")
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(0, weight=1)
        self.matrix_frame = tk.Frame(canvas, bg="#fff")
        self.matrix_window = canvas.create_window((0, 0), window=self.matrix_frame, anchor="nw")
        self.matrix_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        self.matrix_canvas = canvas
        self.pair_hint_var = tk.StringVar(value="セルを選ぶと、正解札と予測札の決まり字を表示します。")
        ttk.Label(right, textvariable=self.pair_hint_var, font=("Yu Gothic UI", 11, "bold"),
                  foreground="#20394f", padding=(8, 7)).pack(side="bottom", anchor="w")

        def head(row, col, value, width=7):
            lab = tk.Label(self.matrix_frame, text=value, bg="#e5f0fa", fg=DARK,
                           font=("Yu Gothic UI", 9, "bold"), width=width, height=2,
                           relief="ridge", bd=1)
            lab.grid(row=row, column=col, sticky="nsew")
            return lab

        head(0, 0, "正解＼予測", 17)
        for j, (cid, prefix) in enumerate(self.cards):
            head(0, j+1, f"{cid}\n{prefix}", 8)
        head(0, 21, "誤分類計", 9)
        for i, (cid, prefix) in enumerate(self.cards):
            head(i+1, 0, f"{cid}  {prefix}", 17)
            buttons = []
            for j in range(20):
                b = tk.Button(self.matrix_frame, text=("－" if i == j else "0"),
                              font=("Yu Gothic UI", 10),
                              width=7, height=2, bd=1, relief="ridge",
                              bg=("#e7ecef" if i == j else "#fff9ed"),
                              activebackground="#f4ddb0",
                              state=("disabled" if i == j else "normal"),
                              cursor="hand2" if i != j else "arrow")
                b.grid(row=i+1, column=j+1, sticky="nsew")
                if i != j:
                    b.bind("<Button-1>", lambda e, r=i, c=j: self.click_matrix(r, c, -1 if e.state & 0x1 else 1))
                    b.bind("<Button-3>", lambda e, r=i, c=j: self.click_matrix(r, c, -1))
                    b.bind("<Enter>", lambda e, r=i, c=j: self.show_pair(r, c))
                    b.bind("<Leave>", lambda e: self.clear_pair())
                buttons.append(b)
            self.matrix_buttons.append(buttons)
            self.actual_count_labels.append(head(i+1, 21, "0", 9))
        head(21, 0, "予測別計", 17)
        for j in range(20):
            self.pred_count_labels.append(head(21, j+1, "0", 8))
        self.grand_total = head(21, 21, "0", 9)
        canvas.bind("<MouseWheel>", lambda e: canvas.yview_scroll(-1 if e.delta > 0 else 1, "units"))
        canvas.bind("<Shift-MouseWheel>", lambda e: canvas.xview_scroll(-1 if e.delta > 0 else 1, "units"))

        bottom = ttk.Frame(self.root, padding=(13, 5, 13, 11))
        bottom.pack(fill="x")
        ttk.Label(bottom, textvariable=self.status_var, foreground="#3c6b8d").pack(side="left")
        ttk.Button(bottom, text="次の画像 →", command=self.next_image).pack(side="right", padx=5)
        ttk.Button(bottom, text="← 前の画像", command=self.prev_image).pack(side="right", padx=5)

    def aggregate(self):
        out = {
            "name": "10枚合計",
            "missing": [[0]*COLS for _ in range(ROWS)],
            "missing_cards": [0]*20,
            "misclassified": [[0]*20 for _ in range(20)],
        }
        for item in self.data["images"]:
            for r in range(ROWS):
                for c in range(COLS):
                    out["missing"][r][c] += item["missing"][r][c]
            for r in range(20):
                out["missing_cards"][r] += item["missing_cards"][r]
                for c in range(20):
                    out["misclassified"][r][c] += item["misclassified"][r][c]
        return out

    def current(self):
        return self.aggregate() if self.selected == N_IMAGES else self.data["images"][self.selected]

    def backup_existing(self):
        """Save an unchanged copy once before the first edit of an opened file."""
        key = str(self.path.resolve())
        if key in self.backed_up_paths:
            return
        if self.path.exists():
            backup_dir = self.path.parent / "backups"
            backup_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            dest = backup_dir / f"{self.path.stem}_before_edit_{stamp}{self.path.suffix}"
            shutil.copy2(self.path, dest)
        self.backed_up_paths.add(key)

    def persist(self):
        self.backup_existing()
        atomic_save(self.path, self.data)
        self.status_var.set(f"追記を自動保存しました：{self.path}")

    def select_image(self, event=None):
        ix = self.view.current()
        if ix < 0:
            return
        self.selected = ix
        self.refresh()

    def jump(self, offset):
        self.selected = min(N_IMAGES, max(0, self.selected+offset))
        self.refresh()

    def next_image(self):
        self.jump(1)

    def prev_image(self):
        self.jump(-1)

    def rename(self, event=None):
        if self.selected == N_IMAGES:
            return
        new_name = self.name_var.get().strip()
        if not new_name:
            messagebox.showwarning("画像名", "画像名を入力してください。")
            return
        self.data["images"][self.selected]["name"] = new_name
        self.persist()
        self.refresh()

    def click_miss(self, row, col, delta):
        if self.selected == N_IMAGES:
            return
        item = self.data["images"][self.selected]
        item["missing"][row][col] = max(0, item["missing"][row][col]+delta)
        self.persist()
        self.refresh()

    def click_missed_card(self, index, delta):
        if self.selected == N_IMAGES:
            return
        counts = self.data["images"][self.selected]["missing_cards"]
        counts[index] = max(0, counts[index] + delta)
        self.persist()
        self.refresh()

    def show_pair(self, actual, predicted):
        true_id, true_prefix = self.cards[actual]
        pred_id, pred_prefix = self.cards[predicted]
        self.pair_hint_var.set(
            f"正解：{true_id}（{true_prefix}）  →  予測：{pred_id}（{pred_prefix}）"
        )

    def clear_pair(self):
        self.pair_hint_var.set("セルを選ぶと、正解札と予測札の決まり字を表示します。")

    def click_matrix(self, actual, predicted, delta):
        if self.selected == N_IMAGES or actual == predicted:
            return
        item = self.data["images"][self.selected]
        item["misclassified"][actual][predicted] = max(
            0, item["misclassified"][actual][predicted]+delta
        )
        self.persist()
        self.refresh()

    def refresh(self):
        aggregate = self.selected == N_IMAGES
        self.view.current(self.selected)
        item = self.current()
        self.name_var.set(item["name"])
        self.name_entry.configure(state="disabled" if aggregate else "normal")
        for r in range(ROWS):
            for c in range(COLS):
                val = item["missing"][r][c]
                b = self.miss_buttons[r][c]
                b.configure(text=str(val), bg="#74d19c" if val else GREEN,
                            fg=DARK, cursor="arrow" if aggregate else "hand2")
        for i, (card_id, prefix) in enumerate(self.cards):
            count = item["missing_cards"][i]
            self.missed_card_buttons[i].configure(
                text=f"{card_id} {prefix}\n{count}件",
                bg="#b8d8ff" if count else "#edf4ff",
                cursor="arrow" if aggregate else "hand2"
            )
        for i in range(20):
            total = 0
            for j in range(20):
                val = item["misclassified"][i][j]
                total += val
                if i != j:
                    self.matrix_buttons[i][j].configure(
                        text=str(val), bg="#ffd4c9" if val else "#fff9ed",
                        cursor="arrow" if aggregate else "hand2"
                    )
            self.actual_count_labels[i].configure(text=str(total))
        total_mis = 0
        for j in range(20):
            total = sum(item["misclassified"][i][j] for i in range(20))
            self.pred_count_labels[j].configure(text=str(total))
            total_mis += total
        self.grand_total.configure(text=str(total_mis))
        total_missing = sum(sum(line) for line in item["missing"])
        total_missed_cards = sum(item["missing_cards"])
        done = sum(
            any(v for row in im["missing"] for v in row)
            or any(v for row in im["misclassified"] for v in row)
            or any(im["missing_cards"])
            for im in self.data["images"]
        )
        self.totals_var.set(
            f"{'10枚合計' if aggregate else item['name']}　｜　"
            f"未検出位置：{total_missing}件　　未検出札：{total_missed_cards}件　　誤分類：{total_mis}件　　"
            f"入力あり：{done}/10画像"
        )

    def export(self):
        folder = filedialog.askdirectory(title="CSVの出力先を選択", initialdir=str(self.path.parent))
        if not folder:
            return
        dest = Path(folder)
        def csv_write(path, headers, rows):
            with path.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                writer.writerows(rows)

        data = self.data["images"] + [self.aggregate()]
        missing_rows = []
        missed_cards_rows = []
        confusion_rows = []
        matrix_rows = []
        summary_rows = []
        for ix, item in enumerate(data):
            image_id = f"{ix+1:02d}" if ix < N_IMAGES else "TOTAL"
            missing_n = sum(sum(x) for x in item["missing"])
            missed_cards_n = sum(item["missing_cards"])
            wrong_n = sum(sum(x) for x in item["misclassified"])
            summary_rows.append([image_id, item["name"], missing_n, missed_cards_n, wrong_n])
            for row in range(ROWS):
                for col in range(COLS):
                    missing_rows.append([image_id, item["name"], row+1, col+1,
                                         item["missing"][row][col]])
            for i,(actual_id,actual_prefix) in enumerate(self.cards):
                missed_cards_rows.append([image_id, item["name"], actual_id, actual_prefix,
                                          item["missing_cards"][i]])
                matrix_rows.append([image_id, item["name"], actual_id, actual_prefix]
                                   + item["misclassified"][i])
                for j,(pred_id,pred_prefix) in enumerate(self.cards):
                    n = item["misclassified"][i][j]
                    if n:
                        confusion_rows.append([image_id,item["name"],
                                               actual_id,actual_prefix,pred_id,pred_prefix,n])
        csv_write(dest/"evaluation_summary.csv",
                  ["image_id","image_name","missed_position_count","missed_card_count","misclassified_count"],summary_rows)
        csv_write(dest/"missed_positions.csv",
                  ["image_id","image_name","row_top_to_bottom","column_left_to_right","count"],missing_rows)
        csv_write(dest/"missed_cards.csv",
                  ["image_id","image_name","card_id","decision_prefix","count"],missed_cards_rows)
        csv_write(dest/"misclassification_pairs.csv",
                  ["image_id","image_name","true_card_id","true_prefix",
                   "predicted_card_id","predicted_prefix","count"],confusion_rows)
        csv_write(dest/"misclassification_matrix.csv",
                  ["image_id","image_name","true_card_id","true_prefix"]
                  + [f"pred_{cid}" for cid,_ in self.cards],matrix_rows)
        self.status_var.set(f"CSVを5ファイル出力しました：{dest}")
        messagebox.showinfo("CSV出力完了", f"5ファイルを保存しました。\n{dest}")

    def save_as(self):
        filename = filedialog.asksaveasfilename(
            title="集計データを別名保存", defaultextension=".json",
            filetypes=[("JSON files","*.json")], initialfile="review_backup.json",
            initialdir=str(self.path.parent)
        )
        if filename:
            atomic_save(Path(filename), self.data)
            self.status_var.set(f"別名保存済み：{filename}")

    def open_data(self):
        filename = filedialog.askopenfilename(
            title="既存の集計データを開く", filetypes=[("JSON files","*.json")],
            initialdir=str(self.path.parent)
        )
        if not filename:
            return
        try:
            with Path(filename).open(encoding="utf-8") as f:
                new = migrate(json.load(f))
            validate(new)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            messagebox.showerror("読み込み失敗", str(exc))
            return
        self.data = new
        self.path = Path(filename)
        self.selected = 0
        self.refresh()
        self.status_var.set(f"既存データを読み込みました。追記できます：{filename}")

    def close(self):
        # Edits are already saved immediately; do not overwrite a just-opened file on exit.
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    try:
        app = App(root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        messagebox.showerror("起動できません", str(exc))
        root.destroy()
        raise SystemExit(1)
    root.mainloop()
