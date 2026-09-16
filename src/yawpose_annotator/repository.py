from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from .models import Correction


class CorrectionRepository:
    def __init__(self, path: Path) -> None:
        self.path = path.expanduser().resolve()

    def load(self) -> dict[str, Correction]:
        if not self.path.exists():
            return {}
        corrections: dict[str, Correction] = {}
        with self.path.open("r", encoding="utf-8") as fh:
            for line_number, line in enumerate(fh, start=1):
                if not line.strip():
                    continue
                try:
                    correction = Correction.from_dict(json.loads(line))
                except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
                    raise ValueError(f"invalid correction at {self.path}:{line_number}") from exc
                corrections[correction.image] = correction
        return corrections

    def save(self, corrections: dict[str, Correction]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent
        )
        temp_path = Path(temp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
                for image in sorted(corrections):
                    payload = json.dumps(
                        corrections[image].to_dict(), ensure_ascii=False, separators=(",", ":")
                    )
                    fh.write(payload + "\n")
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(temp_path, self.path)
        finally:
            if temp_path.exists():
                temp_path.unlink()
