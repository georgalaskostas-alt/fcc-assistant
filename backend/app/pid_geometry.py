"""Conservative raster geometry extraction for P&ID line-segment proposals.

Segments are *unclassified visual evidence*, not piping or signal connections.
Works on local PIL images and does not require cloud services or OpenCV.
"""
from __future__ import annotations

from PIL import Image


def detect_line_segments(image: Image.Image, *, min_length: int = 65,
                         darkness: int = 145, max_segments: int = 2500) -> dict:
    """Detect long horizontal/vertical dark pixel runs at preview resolution.

    No inferred line type, flow direction, equipment endpoint, or connectivity.
    Sampling every second row/column limits CPU cost on large engineering sheets.
    """
    gray = image.convert("L")
    width, height = gray.size
    if width < 1 or height < 1 or width * height > 12_000_000:
        raise ValueError("Raster geometry exceeds supported size")
    px = gray.load()
    segments: list[dict] = []

    def append_run(x1: int, y1: int, x2: int, y2: int) -> None:
        if len(segments) >= max_segments:
            return
        segments.append({
            "x1": round(x1 / width, 6), "y1": round(y1 / height, 6),
            "x2": round(x2 / width, 6), "y2": round(y2 / height, 6),
            "orientation": "horizontal" if y1 == y2 else "vertical",
            "status": "unverified_visual_segment",
            "region_hint": ("title_block_candidate" if (x1+x2)/(2*width)>0.74 and (y1+y2)/(2*height)>0.85 else "drawing_area_candidate"),
        })

    for y in range(0, height, 2):
        start = None
        for x in range(width + 1):
            dark = x < width and px[x, y] < darkness
            if dark and start is None:
                start = x
            elif not dark and start is not None:
                if x - start >= min_length:
                    append_run(start, y, x - 1, y)
                start = None
        if len(segments) >= max_segments:
            break
    # Supplement exact pixel runs with conservative vertical continuity evidence.
    # Slightly tilted or faint scanned lines may disappear from a single column.
    # A narrow lateral search and a bounded dark-pixel gap recover some of them,
    # without connecting arbitrary distant marks or claiming pipe identity.
    if len(segments) < max_segments:
        for x in range(2, width - 2, 4):
            start = None
            last_hit = None
            hits = 0
            for y in range(height):
                dark = any(px[xx, y] < darkness for xx in range(x - 2, x + 3))
                if dark:
                    if start is None:
                        start = y
                        hits = 0
                    last_hit = y
                    hits += 1
                elif start is not None and last_hit is not None and y - last_hit > 5:
                    length = last_hit - start + 1
                    if length >= min_length and hits / length >= 0.85:
                        # Avoid flooding the proposal list with exact duplicates.
                        if not any(item["orientation"] == "vertical"
                                   and abs(item["x1"] - x / width) < 5 / width
                                   and abs(item["y1"] - start / height) < 8 / height
                                   and abs(item["y2"] - last_hit / height) < 8 / height
                                   for item in segments):
                            append_run(x, start, x, last_hit)
                    start = None
                    last_hit = None
                    hits = 0
                if len(segments) >= max_segments:
                    break
            if start is not None and last_hit is not None and len(segments) < max_segments:
                length = last_hit - start + 1
                if length >= min_length and hits / length >= 0.85:
                    if not any(item["orientation"] == "vertical"
                               and abs(item["x1"] - x / width) < 5 / width
                               and abs(item["y1"] - start / height) < 8 / height
                               and abs(item["y2"] - last_hit / height) < 8 / height
                               for item in segments):
                        append_run(x, start, x, last_hit)
            if len(segments) >= max_segments:
                break
    if len(segments) < max_segments:
        for x in range(0, width, 2):
            start = None
            for y in range(height + 1):
                dark = y < height and px[x, y] < darkness
                if dark and start is None:
                    start = y
                elif not dark and start is not None:
                    if y - start >= min_length:
                        append_run(x, start, x, y - 1)
                    start = None
            if len(segments) >= max_segments:
                break
    return {
        "segments": segments,
        "count": len(segments),
        "truncated": len(segments) >= max_segments,
        "warning": "Pixel-run proposals only. Not classified as process pipes, signals or verified connections.",
    }
