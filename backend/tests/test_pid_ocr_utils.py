from backend.app.pid_ocr_utils import extract_candidates, deduplicate


def test_split_equipment_label_is_joined():
    header = "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
    rows = (
        "5\t1\t1\t1\t1\t1\t100\t200\t25\t12\t87\tSC\n"
        "5\t1\t1\t1\t1\t2\t128\t200\t20\t12\t89\t01\n"
    )
    candidates = extract_candidates(header + rows, 1000, 1000)
    assert any(item["tag"] == "SC01" for item in candidates)


def test_overlapping_same_tag_is_deduplicated():
    candidate = {"tag": "SC01", "confidence": 70, "box": {"x": .1, "y": .2, "width": .04, "height": .02}}
    lower = {**candidate, "confidence": 40}
    assert deduplicate([lower, candidate]) == [candidate]
