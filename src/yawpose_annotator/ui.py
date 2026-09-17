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
        self.control_containers: dict[str, object] = {}
        self.status_label = None
        self.page_label = None
        self.grid = None
        self.pagination_row = None
        self.filtered_count = 0
        self.page_count = 1

    def build(self) -> None:
        app.add_static_files("/dataset", str(self.dataset_root))
        resources_root = Path(__file__).resolve().parents[2] / "resources"
        app.add_static_files("/resources", str(resources_root))
        ui.add_css(
            """
            body { background: #111827; color: #e5e7eb; }
            .pose-card { background: #1f2937; padding: 6px; cursor: pointer; }
            .pose-card-selected { outline: 4px solid #facc15; }
            .pose-card-dirty { box-shadow: inset 0 0 0 2px #38bdf8; }
            .pose-photo { width: 100%; aspect-ratio: 1 / 1; object-fit: cover; display: block; }
            .pose-meta { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }
            .pose-indicator {
                position: absolute;
                bottom: 4px;
                width: 72px;
                height: 72px;
                overflow: hidden;
                border: 1px solid rgba(229, 231, 235, .9);
                border-radius: 8px;
                background: rgba(0, 0, 0, .62);
            }
            .pose-indicator-pitch { left: 4px; }
            .pose-indicator-yaw { right: 4px; }
            .pose-indicator-figure {
                position: absolute;
                left: 18px;
                top: 18px;
                width: 36px;
                height: 36px;
                object-fit: contain;
                opacity: .88;
                transform-origin: center;
            }
            .pose-indicator svg { position: absolute; inset: 0; }
            .pose-yaw-controls {
                position: absolute;
                top: 4px;
                left: 4px;
                right: 4px;
                z-index: 2;
                padding: 4px;
                border-radius: 6px;
                background: rgba(17, 24, 39, .82);
            }
            .pose-yaw-controls .q-btn {
                min-width: 0;
                min-height: 24px;
                padding: 0 4px;
                font-size: 10px;
            }
            .annotator-field .q-field__native,
            .annotator-field .q-field__input,
            .annotator-field .q-field__label,
            .annotator-field .q-field__marginal {
                color: #f3f4f6 !important;
            }
            .annotator-field .q-field__control::before {
                border-color: #6b7280 !important;
            }
            .annotator-field .q-field__control:hover::before,
            .annotator-field.q-field--focused .q-field__control::before {
                border-color: #d1d5db !important;
            }
            .annotator-select-popup {
                background: #1f2937 !important;
                color: #f3f4f6 !important;
            }
            .annotator-select-popup .q-item {
                color: #f3f4f6 !important;
            }
            .annotator-select-popup .q-item--active,
            .annotator-select-popup .q-item.q-manual-focusable--focused,
            .annotator-select-popup .q-item:hover {
                background: #374151 !important;
                color: #ffffff !important;
            }
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
        sort_modes = {"dataset": "dataset order", "suspicion": "suspicious first"}
        with ui.row().classes("items-end gap-2 flex-wrap"):
            source = (
                ui.select(sources, value="__all__", label="source")
                .classes("w-48 annotator-field")
                .props("dark outlined popup-content-class=annotator-select-popup")
            )
            yaw_min = (
                ui.number(label="original yaw min", value=0, min=0, max=360, step=1)
                .classes("w-36 annotator-field")
                .props("dark outlined")
            )
            yaw_max = (
                ui.number(label="original yaw max", value=360, min=0, max=360, step=1)
                .classes("w-36 annotator-field")
                .props("dark outlined")
            )
            modified_only = ui.checkbox("modified only", value=False)
            sort_mode = (
                ui.select(sort_modes, value="dataset", label="sort")
                .classes("w-44 annotator-field")
                .props("dark outlined popup-content-class=annotator-select-popup")
            )

            def apply_filter() -> None:
                self.service.set_filter(
                    source=None if source.value == "__all__" else str(source.value),
                    yaw_min=float(yaw_min.value or 0),
                    yaw_max=float(yaw_max.value if yaw_max.value is not None else 360),
                    modified_only=bool(modified_only.value),
                )
                self.service.set_sort_mode(str(sort_mode.value))
                self._render_page()
                self._update_status()

            ui.button("Apply filter", on_click=apply_filter)
            ui.button("Save (Enter)", on_click=self._save)
            ui.button("Export merged labels", on_click=self._export)
        self.pagination_row = ui.row().classes("items-center gap-1 flex-wrap")
        ui.label(
            "Keys: ←/→ yaw ±1°, Shift+←/→ ±10°, ↑/↓ pitch ±1°, "
            "Shift+↑/↓ ±10°, J/K selection, PgUp/PgDn page, R reset, Enter save"
        ).classes("text-xs text-gray-400")

    def _render_page(self) -> None:
        if self.grid is None:
            return
        self.cards.clear()
        self.contents.clear()
        self.control_containers.clear()
        self.grid.clear()
        rows = self.service.page_records()
        self.filtered_count = len(self.service.filtered())
        self.page_count = self.service.page_count
        if rows and self.service.selected_image not in {row.record.image for row in rows}:
            self.service.select(rows[0].record.image)
        with self.grid:
            for pose in rows:
                with ui.card().classes(self._card_classes(pose)) as card:
                    with ui.element("div").classes("relative w-full"):
                        content = ui.html(
                            self._tile_html(pose), sanitize=False
                        ).classes("w-full")
                        controls = ui.element("div")
                    card.on("click", lambda _, image=pose.record.image: self._select(image))
                    self.cards[pose.record.image] = card
                    self.contents[pose.record.image] = content
                    self.control_containers[pose.record.image] = controls
                    self._refresh_controls(pose.record.image)
        self._update_page_label()
        self._render_pagination()

    def _refresh_controls(self, image: str) -> None:
        container = self.control_containers.get(image)
        if container is None:
            return
        container.clear()
        if image != self.service.selected_image:
            return
        with container:
            self._build_image_yaw_controls()

    def _build_image_yaw_controls(self) -> None:
        with ui.row().classes(
            "pose-yaw-controls items-center gap-1 no-wrap"
        ):
            ui.button("FLIP", on_click=self._flip_yaw).props(
                "dense no-caps"
            ).classes("flex-1")
            ui.button("+180°", on_click=lambda: self._adjust_yaw(180)).props(
                "dense no-caps"
            ).classes("flex-1")
            ui.button("RESET", on_click=self._reset).props(
                "dense no-caps"
            ).classes("flex-1")

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
                self._refresh_controls(target)

    def _flip_yaw(self) -> None:
        image = self.service.selected_image
        if image is None:
            return
        current = self.service.effective(image).yaw
        if self.service.set_yaw((-current) % 360.0):
            self._refresh_pose(image)

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

    def _go_to_page(self, page: int) -> None:
        self.service.page = max(0, min(page, self.service.page_count - 1))
        self.service.selected_image = None
        self._render_page()
        self._update_status()

    def _render_pagination(self) -> None:
        if self.pagination_row is None:
            return
        self.pagination_row.clear()
        with self.pagination_row:
            previous = ui.button("<", on_click=lambda: self._move_page(-1)).props(
                "flat dense"
            )
            previous.set_enabled(self.service.page > 0)
            for item in _pagination_items(self.service.page + 1, self.page_count):
                if item is None:
                    ui.label("…").classes("px-1 text-gray-400")
                    continue
                button = ui.button(
                    str(item),
                    on_click=lambda page=item: self._go_to_page(page - 1),
                ).props("flat dense")
                if item == self.service.page + 1:
                    button.props("color=amber")
            next_button = ui.button(">", on_click=lambda: self._move_page(1)).props(
                "flat dense"
            )
            next_button.set_enabled(self.service.page < self.page_count - 1)

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
            f"sort={self.service.sort_mode}  selected={selected}"
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
        yaw_indicator = _pose_indicator_html(pose.record.yaw, pose.yaw, mode="yaw")
        pitch_indicator = _pose_indicator_html(
            pose.record.pitch, pose.pitch, mode="pitch"
        )
        status = "FIXED" if pose.modified else ""
        dirty = " *" if pose.dirty else ""
        pitch_text = _delta_text(pose.record.pitch, pose.pitch, prefix="p")
        yaw_text = _delta_text(pose.record.yaw, pose.yaw, prefix="y")
        qa_text = self._qa_text(pose.record.image)
        return f"""
        <div title="{html.escape(pose.record.image)}">
          <div style="position:relative">
            <img class="pose-photo" src="{html.escape(url)}" loading="lazy" />
            {pitch_indicator}
            {yaw_indicator}
          </div>
          <div class="pose-meta" style="margin-top:4px">
            <div>{html.escape(pose.record.source)}</div>
            <div>{status}{dirty} {yaw_text}</div>
            <div>{pitch_text}</div>
            <div>{qa_text}</div>
          </div>
        </div>
        """

    def _qa_text(self, image: str) -> str:
        qa = self.service.sixd_qa(image)
        error = self.service.sixd_error(image)
        if qa is None or error is None:
            return "SixD n/a"
        reliability = "reliable" if qa.reliable else "unreliable"
        return f"SixD Δ{error:.1f}° {reliability}"


def _pagination_items(current: int, page_count: int) -> list[int | None]:
    visible = {1, page_count}
    visible.update(range(max(1, current - 2), min(page_count, current + 2) + 1))
    pages = sorted(visible)
    items: list[int | None] = []
    previous = 0
    for page in pages:
        if previous and page - previous > 1:
            items.append(None)
        items.append(page)
        previous = page
    return items


def _delta_text(original: float | None, current: float | None, *, prefix: str) -> str:
    if original is None:
        return f"{prefix} n/a"
    if current is None or abs(original - current) < 1e-6:
        return f"{prefix}{original:+.1f}"
    return f"{prefix}{original:+.1f}→{current:+.1f}"


def _pose_indicator_html(
    original: float | None, current: float | None, *, mode: str
) -> str:
    if original is None or current is None:
        return ""
    size = 72
    center = size / 2
    radius = 30
    original_offset = original - current
    original_x, original_y = _camera_point(original_offset, center, radius, mode)
    label = "Y" if mode == "yaw" else "P"
    figure = "topview_man.png" if mode == "yaw" else "body_koutoubu_normal_man.png"
    figure_rotation = current if mode == "yaw" else -current
    return f"""
    <div class="pose-indicator pose-indicator-{mode}">
      <img class="pose-indicator-figure" src="/resources/{figure}" alt=""
           style="transform:rotate({figure_rotation:.2f}deg)" />
      <svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">
        {_fixed_camera_line(center, size, mode)}
        <line x1="{center}" y1="{center}"
              x2="{original_x:.2f}" y2="{original_y:.2f}"
              stroke="#ef4444" stroke-width="2.5"/>
        <circle cx="{original_x:.2f}" cy="{original_y:.2f}"
                r="4" fill="#ef4444"/>
        <circle cx="{center}" cy="{center}" r="2.5" fill="#f8fafc"/>
        <text x="7" y="12" fill="white" font-size="10" font-weight="700"
              text-anchor="middle"
              style="paint-order:stroke;stroke:rgba(0,0,0,.9);stroke-width:2px">
          {label}
        </text>
      </svg>
    </div>
    """


def _fixed_camera_line(center: float, size: int, mode: str) -> str:
    if mode == "yaw":
        start_x, start_y = center, float(size)
    else:
        start_x, start_y = 0.0, center
    return (
        f'<line x1="{start_x}" y1="{start_y}" x2="{center}" y2="{center}" '
        'stroke="#22c55e" stroke-width="2.5"/>'
        f'<circle cx="{start_x}" cy="{start_y}" r="4" fill="#22c55e"/>'
    )


def _camera_point(
    angle: float, center: float, radius: float, mode: str
) -> tuple[float, float]:
    radians = math.radians(angle)
    if mode == "yaw":
        dx = math.sin(radians)
        dy = math.cos(radians)
    else:
        dx = -math.cos(radians)
        dy = -math.sin(radians)
    return center + radius * dx, center + radius * dy
