# yawpose-annotator

Local, keyboard-first annotation UI for manually auditing and correcting YawPose ground-truth yaw/pitch values.

The original `labels_fixed.jsonl` is never modified. Manual overrides are stored separately in `manual_corrections.jsonl`, and a merged label file can be exported when needed.

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)

## Setup

```bash
uv sync --group dev
```

## Run

Pass the extracted YawPose directory as the dataset root. By default the app reads `labels_fixed.jsonl` and serves images relative to that directory.

```bash
uv run yawpose-annotator /path/to/yawpose
```

Optional paths can be overridden explicitly.

```bash
uv run yawpose-annotator /path/to/yawpose \
  --labels /path/to/yawpose/labels_fixed.jsonl \
  --corrections /work/manual_corrections.jsonl \
  --export /work/labels_manual_fixed.jsonl
```

The UI is available at `http://127.0.0.1:8080` and opens in the default browser.

## Workflow

The default page contains 30 samples sorted by source, original yaw, pitch, and image name. Filtering uses the original GT so that problematic source/yaw ranges can be audited consistently. A wraparound range such as `340` to `20` is supported.

Each tile displays two pose indicators. Red is the original GT and green is the currently corrected GT. An unchanged value overlaps exactly. Modified samples are marked `FIXED`; unsaved edits also have a blue inset border and `*` marker.

Keyboard controls are designed for continuous manual review:

| Key | Action |
| --- | --- |
| `←` / `→` | yaw -1° / +1° |
| `Shift+←` / `Shift+→` | yaw -10° / +10° |
| `↑` / `↓` | pitch +1° / -1° |
| `Shift+↑` / `Shift+↓` | pitch +10° / -10° |
| `J` / `K` | select next / previous sample on the page |
| `PageDown` / `PageUp` | next / previous page |
| `R` | reset the selected sample to the original GT |
| `Enter` | atomically persist staged corrections |

Arrow-key repeat events are intentionally accepted, so holding an arrow key continuously changes the selected GT.

## Correction format

`manual_corrections.jsonl` contains only samples whose final value differs from the original GT. Each line preserves both values for auditability.

```json
{"image":"images/example.jpg","original_yaw":30.0,"corrected_yaw":52.0,"original_pitch":null,"corrected_pitch":null,"updated_at":"2026-09-16T00:00:00+00:00"}
```

Saving is atomic: the tool writes a temporary file, fsyncs it, and then replaces the correction file.

## Export

`Export merged labels` first saves staged corrections and then writes `labels_manual_fixed.jsonl`. It preserves every original JSONL field and replaces only corrected `yaw_deg` / `pitch_deg` values.

## Development

Run the checks with uv.

```bash
uv run pytest
uv run ruff check .
```
