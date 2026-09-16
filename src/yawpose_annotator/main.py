from __future__ import annotations

import argparse
from pathlib import Path

from nicegui import ui

from .loader import load_records
from .repository import CorrectionRepository
from .service import AnnotationService
from .ui import AnnotatorUI


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Keyboard-first YawPose GT annotator")
    parser.add_argument("dataset_root", type=Path, help="YawPose dataset root containing images/")
    parser.add_argument(
        "--labels",
        type=Path,
        default=None,
        help="input JSONL; defaults to <dataset_root>/labels_fixed.jsonl",
    )
    parser.add_argument(
        "--corrections",
        type=Path,
        default=None,
        help="manual correction JSONL; defaults to <dataset_root>/manual_corrections.jsonl",
    )
    parser.add_argument(
        "--export",
        type=Path,
        default=None,
        help="merged output JSONL; defaults to <dataset_root>/labels_manual_fixed.jsonl",
    )
    parser.add_argument("--page-size", type=int, default=30)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8080)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    root = args.dataset_root.expanduser().resolve()
    labels = (args.labels or root / "labels_fixed.jsonl").expanduser().resolve()
    corrections = (args.corrections or root / "manual_corrections.jsonl").expanduser().resolve()
    export_path = (args.export or root / "labels_manual_fixed.jsonl").expanduser().resolve()

    records = load_records(root, labels)
    service = AnnotationService(
        records,
        CorrectionRepository(corrections),
        page_size=args.page_size,
    )
    AnnotatorUI(service, root, export_path).build()
    ui.run(
        host=args.host,
        port=args.port,
        title="YawPose Annotator",
        reload=False,
        show=True,
    )


if __name__ in {"__main__", "__mp_main__"}:
    main()
