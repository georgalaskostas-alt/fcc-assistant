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
