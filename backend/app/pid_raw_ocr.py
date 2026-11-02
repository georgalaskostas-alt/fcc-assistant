"""Bounded, unfiltered Tesseract word diagnostics for engineer review."""
from __future__ import annotations
import csv
import io

def raw_ocr_words(tsv: str, image_width: int, image_height: int, *, offset_x: int = 0,
                  offset_y: int = 0, limit: int = 150) -> list[dict]:
    output: list[dict] = []
    for row in csv.DictReader(io.StringIO(tsv), delimiter="\t"):
        if row.get("level") != "5": continue
        try:
            x,y,w,h = (int(row[k]) for k in ("left","top","width","height"))
            confidence = float(row["conf"])
        except (KeyError, ValueError, TypeError): continue
        word = (row.get("text") or "").strip()
        if not word or w <= 0 or h <= 0: continue
        box = {"x":(offset_x+x)/image_width,"y":(offset_y+y)/image_height,
               "width":w/image_width,"height":h/image_height}
        if box["x"] < 0 or box["y"] < 0 or box["x"]+box["width"]>1.01 or box["y"]+box["height"]>1.01: continue
        output.append({"text":word[:100], "confidence":round(confidence,1),"box":box,
                       "status":"raw_unverified_ocr"})
        if len(output)>=limit: break
    return output
