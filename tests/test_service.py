from pathlib import Path

from yawpose_annotator.models import PoseRecord
from yawpose_annotator.repository import CorrectionRepository
from yawpose_annotator.service import AnnotationService


def record(image: str, yaw: float, *, source: str = "s1", pitch: float | None = 0) -> PoseRecord:
    return PoseRecord(
        image=image,
        image_path=Path("/data") / image,
        source=source,
        yaw=yaw,
        pitch=pitch,
        raw={"image": image, "source": source, "yaw_deg": yaw, "pitch_deg": pitch},
    )


def test_adjust_save_and_reset(tmp_path: Path) -> None:
    service = AnnotationService(
        [record("a.jpg", 30)],
        CorrectionRepository(tmp_path / "corrections.jsonl"),
    )
    service.select("a.jpg")

    service.adjust_yaw(22)
    assert service.effective("a.jpg").yaw == 52
    assert service.dirty_count == 1
    assert service.save() == 1
    assert service.modified_count == 1

    service.reset_selected()
    service.save()
    assert service.modified_count == 0
    assert service.corrections == {}


def test_wraparound_filter(tmp_path: Path) -> None:
    service = AnnotationService(
        [record("a.jpg", 350), record("b.jpg", 10), record("c.jpg", 180)],
        CorrectionRepository(tmp_path / "corrections.jsonl"),
    )

    service.set_filter(source=None, yaw_min=340, yaw_max=20, modified_only=False)

    assert [pose.record.image for pose in service.filtered()] == ["a.jpg", "b.jpg"]
