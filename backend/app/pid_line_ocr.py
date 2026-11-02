"""Unverified piping line-number OCR hypotheses from nearby TSV words."""
from __future__ import annotations
import csv
import io
import re

# Broad prefilter only. Site-specific regex remains the authority in the UI.
PREFILTER = re.compile(r'^\d{1,3}(?:"|IN)?-?[A-Z0-9]{1,8}-[A-Z0-9]{3,12}(?:-[A-Z0-9]{1,8})?$', re.I)

def extract_line_labels(tsv: str, width: int, height: int, *, offset_x: int = 0, offset_y: int = 0) -> list[dict]:
    lines: dict[tuple[str, ...], list[dict]] = {}
    for row in csv.DictReader(io.StringIO(tsv), delimiter="\t"):
        if row.get("level") != "5": continue
        try:
            confidence = float(row["conf"])
            x,y,w,h = (int(row[k]) for k in ("left","top","width","height"))
        except (ValueError, TypeError, KeyError): continue
        token = (row.get("text") or "").strip().upper().replace("–","-").replace("—","-").replace("″",'"')
        if confidence < 15 or not token or w <= 0 or h <= 0: continue
        key = tuple(row.get(k,"") for k in ("page_num","block_num","par_num","line_num"))
        lines.setdefault(key,[]).append(dict(token=token,x=x,y=y,w=w,h=h,conf=confidence))
    result=[]
    for words in lines.values():
        words.sort(key=lambda item:item["x"])
        for i in range(len(words)):
            for n in range(1,7):
                group=words[i:i+n]
                if len(group)!=n: break
                if any(group[j+1]["x"]-(group[j]["x"]+group[j]["w"]) > max(14,group[j]["h"]*1.5)
                       for j in range(len(group)-1)): break
                label="".join(item["token"] for item in group).replace(" ","")
                if not PREFILTER.fullmatch(label): continue
                x0=min(v["x"] for v in group); y0=min(v["y"] for v in group)
                x1=max(v["x"]+v["w"] for v in group); y1=max(v["y"]+v["h"] for v in group)
                box={"x":(offset_x+x0)/width,"y":(offset_y+y0)/height,
                     "width":(x1-x0)/width,"height":(y1-y0)/height}
                if box["x"]+box["width"]>1.01 or box["y"]+box["height"]>1.01: continue
                result.append({"tag":label,"box":box,"confidence":round(min(v["conf"] for v in group),1),
                               "status":"unverified_line_ocr_hypothesis"})
    return result
