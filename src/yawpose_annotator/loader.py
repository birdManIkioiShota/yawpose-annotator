from __future__ import annotations

import json
from pathlib import Path

from .models import PoseRecord


def load_records(dataset_root: Path, labels_path: Path) -> list[PoseRecord]:
    root = dataset_root.expanduser().resolve()
    labels = labels_path.expanduser().resolve()
    if not labels.is_file():
        raise FileNotFoundError(f"labels file not found: {labels}")

    records: list[PoseRecord] = []
    seen: set[str] = set()
    with labels.open("r", encoding="utf-8") as fh:
        for line_number, line in enumerate(fh, start=1):
            if not line.strip():
                continue
            data = json.loads(line)
            try:
                image = str(data["image"])
                yaw = float(data["yaw_deg"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"invalid row at {labels}:{line_number}") from exc
            if image in seen:
                raise ValueError(f"duplicate image key at {labels}:{line_number}: {image}")
            seen.add(image)

            image_path = _resolve_image(root, image)
            pitch_raw = data.get("pitch_deg")
            pitch = None if pitch_raw is None else float(pitch_raw)
            records.append(
                PoseRecord(
                    image=image,
                    image_path=image_path,
                    source=str(data.get("source", "unknown")),
                    yaw=yaw % 360.0,
                    pitch=pitch,
                    raw=data,
                )
            )

    records.sort(key=lambda r: (r.source, r.yaw, r.pitch if r.pitch is not None else 999.0, r.image))
    return records


def _resolve_image(root: Path, image: str) -> Path:
    candidate = Path(image)
    resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"image escapes dataset root: {image}") from exc
    return resolved
