from PIL import Image, ImageDraw
import pytest

from backend.app.pid_geometry import detect_line_segments


def test_detects_horizontal_and_vertical_segments_without_claiming_topology():
    image = Image.new("RGB", (240, 220), "white")
    draw = ImageDraw.Draw(image)
    draw.line((20, 40, 200, 40), fill="black", width=3)
    draw.line((80, 50, 80, 190), fill="black", width=3)
    result = detect_line_segments(image, min_length=60)
    orientations = {segment["orientation"] for segment in result["segments"]}
    assert {"horizontal", "vertical"} <= orientations
    assert all(segment["status"] == "unverified_visual_segment" for segment in result["segments"])
    assert all(0 <= segment[key] <= 1 for segment in result["segments"] for key in ("x1", "y1", "x2", "y2"))


def test_blank_image_has_no_segments():
    result = detect_line_segments(Image.new("RGB", (200, 200), "white"))
    assert result["count"] == 0


def test_geometry_size_limit():
    with pytest.raises(ValueError):
        detect_line_segments(Image.new("L", (4000, 4000), 255))
