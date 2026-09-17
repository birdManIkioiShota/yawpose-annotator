import json
from pathlib import Path

import pytest

from yawpose_annotator.loader import load_records, load_sixd_qa


def test_load_records_sorts_and_reads_pitch(tmp_path: Path) -> None:
    (tmp_path / "images").mkdir()
    labels = tmp_path / "labels_fixed.jsonl"
    rows = [
        {"image": "images/b.jpg", "source": "s2", "yaw_deg": 370, "pitch_deg": 12},
        {"image": "images/a.jpg", "source": "s1", "yaw_deg": 30},
    ]
    labels.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")

    records = load_records(tmp_path, labels)

    assert [record.image for record in records] == ["images/a.jpg", "images/b.jpg"]
    assert records[1].yaw == 10
    assert records[1].pitch == 12


def test_rejects_image_outside_dataset_root(tmp_path: Path) -> None:
    labels = tmp_path / "labels_fixed.jsonl"
    labels.write_text(json.dumps({"image": "../escape.jpg", "yaw_deg": 0}) + "\n")

    with pytest.raises(ValueError, match="escapes dataset root"):
        load_records(tmp_path, labels)


def test_load_sixd_qa_reads_reliability_fields(tmp_path: Path) -> None:
    qa_path = tmp_path / "qa_sixd.jsonl"
    qa_path.write_text(
        json.dumps(
            {
                "image": "images/a.jpg",
                "sixd_yaw": -45.0,
                "sixd_pitch": 20.0,
                "sixd_roll": 3.0,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    qa = load_sixd_qa(qa_path)["images/a.jpg"]

    assert qa.yaw == -45.0
    assert qa.pitch == 20.0
    assert qa.roll == 3.0
    assert qa.reliable is True
