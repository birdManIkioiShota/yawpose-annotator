from __future__ import annotations

import html
import math
from pathlib import Path
from urllib.parse import quote

from nicegui import app, events, ui

from .models import EffectivePose
from .service import AnnotationService


class AnnotatorUI:
    def __init__(
        self,
        service: AnnotationService,
        dataset_root: Path,
        export_path: Path,
    ) -> None:
        self.service = service
        self.dataset_root = dataset_root.resolve()
        self.export_path = export_path.resolve()
        self.cards: dict[str, object] = {}
        self.contents: dict[str, object] = {}
        self.status_label = None
        self.page_label = None
        self.grid = None
        self.filtered_count = 0
        self.page_count = 1

    def build(self) -> None:
        app.add_static_files("/dataset", str(self.dataset_root))
        ui.add_css(
            """
            body { background: #111827; color: #e5e7eb; }
            .pose-card { background: #1f2937; padding: 6px; cursor: pointer; }
            .pose-card-selected { outline: 4px solid #facc15; }
            .pose-card-dirty { box-shadow: inset 0 0 0 2px #38bdf8; }
            .pose-card img { width: 100%; aspect-ratio: 1 / 1; object-fit: cover; display: block; }
            .pose-meta { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }
            """
        )
        with ui.column().classes("w-full p-3 gap-2"):
            ui.label("YawPose Annotator").classes("text-2xl font-bold")
            self._build_controls()
            self.status_label = ui.label().classes("text-sm text-gray-300")
            self.page_label = ui.label().classes("text-sm text-gray-300")
            self.grid = ui.grid(columns=6).classes("w-full gap-2")
        self._render_page()
        self._update_status()
        ui.keyboard(on_key=self._on_key).on(
            "key",
            js_handler="""(e) => {
                const blocked = ['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown',
                                 'PageUp', 'PageDown', 'Enter'];
                if (blocked.includes(e.key)) e.event.preventDefault();
                emit(e);
            }""",
        )

    def _build_controls(self) -> None:
        sources = {"__all__": "all sources"} | {source: source for source in self.service.sources}
        with ui.row().classes("items-end gap-2 flex-wrap"):
            source = ui.select(sources, value="__all__", label="source").classes("w-48")
            yaw_min = ui.number(label="original yaw min", value=0, min=0, max=360, step=1).classes(
                "w-36"
            )
            yaw_max = ui.number(label="original yaw max", value=360, min=0, max=360, step=1).classes(
                "w-36"
            )
            modified_only = ui.checkbox("modified only", value=False)

            def apply_filter() -> None:
                self.service.set_filter(
                    source=None if source.value == "__all__" else str(source.value),
                    yaw_min=float(yaw_min.value or 0),
                    yaw_max=float(yaw_max.value if yaw_max.value is not None else 360),
                    modified_only=bool(modified_only.value),
                )
                self._render_page()
                self._update_status()

            ui.button("Apply filter", on_click=apply_filter)
            ui.button("Save (Enter)", on_click=self._save)
            ui.button("Export merged labels", on_click=self._export)

        with ui.row().classes("items-center gap-2 flex-wrap"):
            ui.button("Prev page", on_click=lambda: self._move_page(-1))
            ui.button("Next page", on_click=lambda: self._move_page(1))
            ui.separator().props("vertical")
            ui.button("Yaw -10", on_click=lambda: self._adjust_yaw(-10))
            ui.button("Yaw -1", on_click=lambda: self._adjust_yaw(-1))
            ui.button("Yaw +1", on_click=lambda: self._adjust_yaw(1))
            ui.button("Yaw +10", on_click=lambda: self._adjust_yaw(10))
            for label, value in [
                ("front 0", 0),
                ("left 90", 90),
                ("back 180", 180),
                ("right 270", 270),
            ]:
                ui.button(label, on_click=lambda value=value: self._set_yaw(value))
            ui.button("Reset", on_click=self._reset)

        ui.label(
            "Keys: ←/→ yaw ±1°, Shift+←/→ ±10°, ↑/↓ pitch ±1°, "
            "Shift+↑/↓ ±10°, J/K selection, PgUp/PgDn page, R reset, Enter save"
        ).classes("text-xs text-gray-400")

    def _render_page(self) -> None:
        if self.grid is None:
            return
        self.cards.clear()
        self.contents.clear()
        self.grid.clear()
        rows = self.service.page_records()
        self.filtered_count = len(self.service.filtered())
        self.page_count = self.service.page_count
        if rows and self.service.selected_image not in {row.record.image for row in rows}:
            self.service.select(rows[0].record.image)
        with self.grid:
            for pose in rows:
                with ui.card().classes(self._card_classes(pose)) as card:
                    content = ui.html(self._tile_html(pose), sanitize=False).classes("w-full")
                    card.on("click", lambda _, image=pose.record.image: self._select(image))
                    self.cards[pose.record.image] = card
                    self.contents[pose.record.image] = content
        self._update_page_label()

    def _refresh_pose(self, image: str) -> None:
        pose = self.service.effective(image)
        content = self.contents.get(image)
        card = self.cards.get(image)
        if content is not None:
            content.set_content(self._tile_html(pose))
        if card is not None:
            card.classes(replace=self._card_classes(pose))
        self._update_status()

    def _select(self, image: str) -> None:
        previous = self.service.selected_image
        self.service.select(image)
        for target in {previous, image}:
            if target and target in self.cards:
                self._refresh_pose(target)

    def _adjust_yaw(self, delta: float) -> None:
        image = self.service.selected_image
        if image and self.service.adjust_yaw(delta):
            self._refresh_pose(image)

    def _set_yaw(self, yaw: float) -> None:
        image = self.service.selected_image
        if image and self.service.set_yaw(yaw):
            self._refresh_pose(image)

    def _adjust_pitch(self, delta: float) -> None:
        image = self.service.selected_image
        if image and self.service.adjust_pitch(delta):
            self._refresh_pose(image)

    def _reset(self) -> None:
        image = self.service.selected_image
        if image and self.service.reset_selected():
            self._refresh_pose(image)

    def _save(self) -> None:
        count = self.service.save()
        self._render_page()
        self._update_status()
        ui.notify(f"saved {count} staged record(s)")

    def _export(self) -> None:
        if self.service.dirty_count:
            self.service.save()
        path = self.service.export_merged(self.export_path)
        self._render_page()
        self._update_status()
        ui.notify(f"exported: {path}")

    def _move_page(self, delta: int) -> None:
        self.service.move_page(delta)
        self._render_page()
        self._update_status()

    def _move_selection(self, delta: int) -> None:
        previous = self.service.selected_image
        self.service.move_selection(delta)
        current = self.service.selected_image
        for target in {previous, current}:
            if target and target in self.cards:
                self._refresh_pose(target)

    def _on_key(self, e: events.KeyEventArguments) -> None:
        if not e.action.keydown:
            return
        step = 10.0 if e.modifiers.shift else 1.0
        if e.key.arrow_left:
            self._adjust_yaw(-step)
        elif e.key.arrow_right:
            self._adjust_yaw(step)
        elif e.key.arrow_up:
            self._adjust_pitch(step)
        elif e.key.arrow_down:
            self._adjust_pitch(-step)
        elif e.key == "j":
            self._move_selection(1)
        elif e.key == "k":
            self._move_selection(-1)
        elif e.key == "PageDown":
            self._move_page(1)
        elif e.key == "PageUp":
            self._move_page(-1)
        elif e.key == "r":
            self._reset()
        elif e.key == "Enter" and not e.action.repeat:
            self._save()

    def _update_status(self) -> None:
        if self.status_label is None:
            return
        selected = self.service.selected_image or "none"
        self.status_label.set_text(
            f"records={len(self.service.records):,}  filtered={self.filtered_count:,}  "
            f"modified={self.service.modified_count:,}  staged={self.service.dirty_count:,}  "
            f"selected={selected}"
        )
        self._update_page_label()

    def _update_page_label(self) -> None:
        if self.page_label is not None:
            self.page_label.set_text(
                f"page {self.service.page + 1} / {self.page_count}  "
                f"({self.service.page_size} per page)"
            )

    def _card_classes(self, pose: EffectivePose) -> str:
        classes = ["pose-card", "w-full"]
        if pose.record.image == self.service.selected_image:
            classes.append("pose-card-selected")
        if pose.dirty:
            classes.append("pose-card-dirty")
        return " ".join(classes)

    def _tile_html(self, pose: EffectivePose) -> str:
        rel = pose.record.image_path.relative_to(self.dataset_root).as_posix()
        url = "/dataset/" + quote(rel, safe="/")
        yaw_svg = _indicator_svg(pose.record.yaw, pose.yaw, mode="yaw")
        pitch_svg = _indicator_svg(pose.record.pitch, pose.pitch, mode="pitch")
        status = "FIXED" if pose.modified else ""
        dirty = " *" if pose.dirty else ""
        pitch_text = _delta_text(pose.record.pitch, pose.pitch, prefix="p")
        yaw_text = _delta_text(pose.record.yaw, pose.yaw, prefix="y")
        return f"""
        <div title="{html.escape(pose.record.image)}">
          <div style="position:relative">
            <img src="{html.escape(url)}" loading="lazy" />
            <div style="position:absolute;left:4px;bottom:4px;display:flex;gap:4px">
              {pitch_svg}{yaw_svg}
            </div>
          </div>
          <div class="pose-meta" style="margin-top:4px">
            <div>{html.escape(pose.record.source)}</div>
            <div>{status}{dirty} {yaw_text}</div>
            <div>{pitch_text}</div>
          </div>
        </div>
        """


def _delta_text(original: float | None, current: float | None, *, prefix: str) -> str:
    if original is None:
        return f"{prefix} n/a"
    if current is None or abs(original - current) < 1e-6:
        return f"{prefix}{original:+.1f}"
    return f"{prefix}{original:+.1f}→{current:+.1f}"


def _indicator_svg(original: float | None, current: float | None, *, mode: str) -> str:
    if original is None or current is None:
        return ""
    size = 46
    center = size / 2
    radius = 18
    old_x, old_y = _endpoint(original, center, radius, mode)
    new_x, new_y = _endpoint(current, center, radius, mode)
    label = "Y" if mode == "yaw" else "P"
    return f"""
    <svg width="{size}" height="{size}" viewBox="0 0 {size} {size}"
         style="background:rgba(0,0,0,.55);border-radius:50%">
      <circle cx="{center}" cy="{center}" r="{radius}" fill="none" stroke="#d1d5db" stroke-width="1"/>
      <line x1="{center}" y1="{center}" x2="{old_x:.2f}" y2="{old_y:.2f}"
            stroke="#ef4444" stroke-width="3"/>
      <line x1="{center}" y1="{center}" x2="{new_x:.2f}" y2="{new_y:.2f}"
            stroke="#22c55e" stroke-width="3"/>
      <text x="3" y="10" fill="white" font-size="8">{label}</text>
    </svg>
    """


def _endpoint(angle: float, center: float, radius: float, mode: str) -> tuple[float, float]:
    radians = math.radians(angle)
    if mode == "yaw":
        dx = math.sin(radians)
        dy = -math.cos(radians)
    else:
        dx = math.cos(radians)
        dy = -math.sin(radians)
    return center + radius * dx, center + radius * dy
