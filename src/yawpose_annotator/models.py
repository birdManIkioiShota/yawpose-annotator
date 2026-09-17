from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class PoseRecord:
    image: str
    image_path: Path
    source: str
    yaw: float
    pitch: float | None
    raw: dict[str, Any]


@dataclass(frozen=True, slots=True)
class SixDQA:
    image: str
    yaw: float
    pitch: float
    roll: float | None = None

    @property
    def reliable(self) -> bool:
        return abs(self.yaw) >= 10.0 and abs(self.pitch) < 60.0


@dataclass(frozen=True, slots=True)
class Correction:
    image: str
    original_yaw: float
    corrected_yaw: float
    original_pitch: float | None
    corrected_pitch: float | None
    updated_at: str

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Correction":
        return cls(
            image=str(data["image"]),
            original_yaw=float(data["original_yaw"]),
            corrected_yaw=float(data["corrected_yaw"]),
            original_pitch=(
                None if data.get("original_pitch") is None else float(data["original_pitch"])
            ),
            corrected_pitch=(
                None if data.get("corrected_pitch") is None else float(data["corrected_pitch"])
            ),
            updated_at=str(data["updated_at"]),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "image": self.image,
            "original_yaw": self.original_yaw,
            "corrected_yaw": self.corrected_yaw,
            "original_pitch": self.original_pitch,
            "corrected_pitch": self.corrected_pitch,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True, slots=True)
class EffectivePose:
    record: PoseRecord
    yaw: float
    pitch: float | None
    persisted: bool
    dirty: bool

    @property
    def modified(self) -> bool:
        return _different(self.record.yaw, self.yaw) or _different(self.record.pitch, self.pitch)


def _different(a: float | None, b: float | None, *, eps: float = 1e-6) -> bool:
    if a is None or b is None:
        return a is not b
    return abs(a - b) > eps
