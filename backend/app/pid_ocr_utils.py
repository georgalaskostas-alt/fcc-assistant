"""Local OCR word grouping for engineering labels. Results are hypotheses, not verified tags."""
from __future__ import annotations

import csv
import io
import re

LABEL = re.compile(r"^[A-Z]{1,6}[- ]?\d{1,6}[A-Z]?(?:[- ]?[A-Z])?$", re.I)


def extract_candidates(tsv: str, image_width: int, image_height: int, *, offset_x: int = 0,
                       offset_y: int = 0, scale: float = 1.0) -> list[dict]:
    """Read Tesseract TSV, joining neighboring tokens on the same line."""
    lines: dict[tuple[str, str, str, str], list[dict]] = {}
    for row in csv.DictReader(io.StringIO(tsv), delimiter="\t"):
        if row.get("level") != "5":
            continue
        try:
            confidence = float(row["conf"])
            x, y, w, h = (int(row[k]) for k in ("left", "top", "width", "height"))
        except (ValueError, TypeError, KeyError):
            continue
        word = (row.get("text") or "").strip().upper()
        if confidence < 15 or not word or w <= 0 or h <= 0:
            continue
        key = tuple(row.get(k, "") for k in ("page_num", "block_num", "par_num", "line_num"))
        lines.setdefault(key, []).append({"word": word, "conf": confidence, "x": x, "y": y, "w": w, "h": h})
    found = []
    for words in lines.values():
        words.sort(key=lambda item: item["x"])
        for i, first in enumerate(words):
            for count in (1, 2, 3):
                group = words[i:i + count]
                if len(group) != count:
                    continue
                if any(group[j+1]["x"] - (group[j]["x"] + group[j]["w"]) >
                       max(18, 1.5 * max(group[j]["h"], group[j+1]["h"])) for j in range(count-1)):
                    continue
                label = "".join(item["word"].strip("- ") for item in group)
                if not LABEL.fullmatch(label):
                    continue
                x0 = min(item["x"] for item in group)
                y0 = min(item["y"] for item in group)
                x1 = max(item["x"] + item["w"] for item in group)
                y1 = max(item["y"] + item["h"] for item in group)
                x = (offset_x + x0 / scale) / image_width
                y = (offset_y + y0 / scale) / image_height
                w = (x1 - x0) / scale / image_width
                h = (y1 - y0) / scale / image_height
                if not all(0 <= v <= 1 for v in (x, y, w, h)) or x+w > 1.01 or y+h > 1.01:
                    continue
                found.append({"tag": label, "confidence": round(min(item["conf"] for item in group), 1),
                              "box": {"x": x, "y": y, "width": w, "height": h},
                              "status": "unverified_ocr_candidate"})
    return found


def deduplicate(candidates: list[dict]) -> list[dict]:
    """Keep the best OCR hypothesis for overlapping boxes with the same label."""
    kept: list[dict] = []
    for item in sorted(candidates, key=lambda c: c["confidence"], reverse=True):
        x, y = item["box"]["x"], item["box"]["y"]
        if any(other["tag"] == item["tag"] and abs(other["box"]["x"] - x) < 0.015
               and abs(other["box"]["y"] - y) < 0.015 for other in kept):
            continue
        kept.append(item)
    return kept[:500]
