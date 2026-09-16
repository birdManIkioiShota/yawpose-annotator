from pathlib import Path

from yawpose_annotator.models import Correction
from yawpose_annotator.repository import CorrectionRepository


def test_round_trip(tmp_path: Path) -> None:
    repository = CorrectionRepository(tmp_path / "corrections.jsonl")
    correction = Correction(
        image="images/a.jpg",
        original_yaw=30,
        corrected_yaw=52,
        original_pitch=None,
        corrected_pitch=None,
        updated_at="2026-09-16T00:00:00+00:00",
    )

    repository.save({correction.image: correction})

    assert repository.load() == {correction.image: correction}
