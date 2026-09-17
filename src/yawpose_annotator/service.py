from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .models import Correction, EffectivePose, PoseRecord, SixDQA
from .repository import CorrectionRepository


class AnnotationService:
    def __init__(
        self,
        records: list[PoseRecord],
        repository: CorrectionRepository,
        *,
        qa_records: dict[str, SixDQA] | None = None,
        page_size: int = 30,
    ) -> None:
        if page_size < 1:
            raise ValueError("page_size must be positive")
        self.records = records
        self.records_by_image = {record.image: record for record in records}
        self.qa_records = qa_records or {}
        self.repository = repository
        loaded_corrections = repository.load()
        self.corrections = {
            image: correction
            for image, correction in loaded_corrections.items()
            if image in self.records_by_image
            and (
                not _same(self.records_by_image[image].yaw, correction.corrected_yaw)
                or not _same(self.records_by_image[image].pitch, correction.corrected_pitch)
            )
        }
        self.drafts: dict[str, tuple[float, float | None]] = {}
        self.page_size = page_size
        self.page = 0
        self.source: str | None = None
        self.yaw_min = 0.0
        self.yaw_max = 360.0
        self.modified_only = False
        self.sort_mode = "dataset"
        self.selected_image: str | None = None

    @property
    def sources(self) -> list[str]:
        return sorted({record.source for record in self.records})

    def effective(self, image: str) -> EffectivePose:
        record = self.records_by_image[image]
        correction = self.corrections.get(image)
        yaw = correction.corrected_yaw if correction else record.yaw
        pitch = correction.corrected_pitch if correction else record.pitch
        if image in self.drafts:
            yaw, pitch = self.drafts[image]
        return EffectivePose(
            record=record,
            yaw=yaw,
            pitch=pitch,
            persisted=correction is not None,
            dirty=image in self.drafts,
        )

    def sixd_qa(self, image: str) -> SixDQA | None:
        return self.qa_records.get(image)

    def sixd_error(self, image: str) -> float | None:
        qa = self.sixd_qa(image)
        if qa is None:
            return None
        return _circular_distance(self.records_by_image[image].yaw, qa.yaw)

    def filtered(self) -> list[EffectivePose]:
        result: list[EffectivePose] = []
        for record in self.records:
            if self.source is not None and record.source != self.source:
                continue
            if not _yaw_in_range(record.yaw, self.yaw_min, self.yaw_max):
                continue
            pose = self.effective(record.image)
            if self.modified_only and not pose.modified:
                continue
            result.append(pose)
        if self.sort_mode == "suspicion":
            result.sort(key=self._suspicion_sort_key)
        return result

    def _suspicion_sort_key(self, pose: EffectivePose) -> tuple[int, float]:
        qa = self.sixd_qa(pose.record.image)
        error = self.sixd_error(pose.record.image)
        if qa is None or error is None:
            return (2, 0.0)
        if not qa.reliable:
            return (1, -error)
        return (0, -error)

    @property
    def page_count(self) -> int:
        count = len(self.filtered())
        return max(1, (count + self.page_size - 1) // self.page_size)

    def page_records(self) -> list[EffectivePose]:
        rows = self.filtered()
        self.page = min(self.page, max(0, self.page_count - 1))
        start = self.page * self.page_size
        return rows[start : start + self.page_size]

    def set_filter(
        self,
        *,
        source: str | None,
        yaw_min: float,
        yaw_max: float,
        modified_only: bool,
    ) -> None:
        self.source = source
        self.yaw_min = yaw_min % 360.0
        self.yaw_max = 360.0 if yaw_max == 360.0 else yaw_max % 360.0
        self.modified_only = modified_only
        self.page = 0
        self.selected_image = None

    def set_sort_mode(self, mode: str) -> None:
        if mode not in {"dataset", "suspicion"}:
            raise ValueError(f"unknown sort mode: {mode}")
        self.sort_mode = mode
        self.page = 0
        self.selected_image = None

    def select(self, image: str) -> None:
        if image not in self.records_by_image:
            raise KeyError(image)
        self.selected_image = image

    def adjust_yaw(self, delta: float) -> bool:
        if self.selected_image is None:
            return False
        pose = self.effective(self.selected_image)
        self.drafts[self.selected_image] = ((pose.yaw + delta) % 360.0, pose.pitch)
        return True

    def set_yaw(self, yaw: float) -> bool:
        if self.selected_image is None:
            return False
        pose = self.effective(self.selected_image)
        self.drafts[self.selected_image] = (yaw % 360.0, pose.pitch)
        return True

    def adjust_pitch(self, delta: float) -> bool:
        if self.selected_image is None:
            return False
        pose = self.effective(self.selected_image)
        if pose.pitch is None:
            return False
        self.drafts[self.selected_image] = (pose.yaw, max(-180.0, min(180.0, pose.pitch + delta)))
        return True

    def reset_selected(self) -> bool:
        if self.selected_image is None:
            return False
        record = self.records_by_image[self.selected_image]
        self.drafts[self.selected_image] = (record.yaw, record.pitch)
        return True

    def save(self) -> int:
        if not self.drafts:
            return 0
        now = datetime.now(timezone.utc).isoformat()
        changed = 0
        for image, (yaw, pitch) in self.drafts.items():
            record = self.records_by_image[image]
            if _same(record.yaw, yaw) and _same(record.pitch, pitch):
                self.corrections.pop(image, None)
            else:
                self.corrections[image] = Correction(
                    image=image,
                    original_yaw=record.yaw,
                    corrected_yaw=yaw,
                    original_pitch=record.pitch,
                    corrected_pitch=pitch,
                    updated_at=now,
                )
            changed += 1
        self.repository.save(self.corrections)
        self.drafts.clear()
        return changed

    def export_merged(self, output_path: Path) -> Path:
        target = output_path.expanduser().resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
        temp_path = Path(temp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
                for record in self.records:
                    correction = self.corrections.get(record.image)
                    data = dict(record.raw)
                    if correction:
                        data["yaw_deg"] = correction.corrected_yaw
                        if correction.corrected_pitch is not None:
                            data["pitch_deg"] = correction.corrected_pitch
                    fh.write(json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n")
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(temp_path, target)
        finally:
            if temp_path.exists():
                temp_path.unlink()
        return target

    @property
    def dirty_count(self) -> int:
        return len(self.drafts)

    @property
    def modified_count(self) -> int:
        count = len(self.corrections)
        for image in self.drafts:
            persisted_modified = image in self.corrections
            current_modified = self.effective(image).modified
            count += int(current_modified) - int(persisted_modified)
        return count

    def move_page(self, delta: int) -> None:
        self.page = max(0, min(self.page + delta, self.page_count - 1))
        self.selected_image = None

    def move_selection(self, delta: int) -> None:
        rows = self.page_records()
        if not rows:
            self.selected_image = None
            return
        images = [row.record.image for row in rows]
        if self.selected_image not in images:
            self.selected_image = images[0]
            return
        index = images.index(self.selected_image)
        self.selected_image = images[(index + delta) % len(images)]


def _yaw_in_range(yaw: float, lower: float, upper: float) -> bool:
    if lower == 0.0 and upper == 360.0:
        return True
    if lower <= upper:
        return lower <= yaw <= upper
    return yaw >= lower or yaw <= upper


def _circular_distance(a: float, b: float) -> float:
    return abs((a - b + 180.0) % 360.0 - 180.0)


def _same(a: float | None, b: float | None, *, eps: float = 1e-6) -> bool:
    if a is None or b is None:
        return a is b
    return abs(a - b) <= eps
