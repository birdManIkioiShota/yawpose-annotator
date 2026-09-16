# yawpose-annotator

Local, keyboard-first annotation UI for manually auditing and correcting YawPose ground-truth yaw/pitch values.

The original `labels_fixed.jsonl` is never modified. Manual overrides are stored separately in `manual_corrections.jsonl`, and a merged label file can be exported when needed.

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- About 1.4 GB of free space for the compressed YawPose archive, plus space for extraction

## Quick start

This section covers the complete path from downloading the official YawPose dataset to launching the annotator and saving corrections.

### 1. Clone this repository

```bash
git clone https://github.com/birdManIkioiShota/yawpose-annotator.git
cd yawpose-annotator
```

When using the implementation PR before it is merged, check out its branch instead.

```bash
git fetch origin chatgpt/feat-initial-annotator
git switch chatgpt/feat-initial-annotator
```

### 2. Install the Python dependencies with uv

```bash
uv sync --group dev
```

`uv` creates and manages the project environment automatically. You do not need to activate a virtual environment manually.

### 3. Download YawPose

The official dataset is published as `yawpose.tar.gz` in PINTO0309/YawNet's `resources` GitHub Release.

Release page:

https://github.com/PINTO0309/YawNet/releases/tag/resources

Direct download:

https://github.com/PINTO0309/YawNet/releases/download/resources/yawpose.tar.gz

The currently published archive used when this README was written has the following SHA-256 digest:

```text
08df8f2e5df8d2c5c0509475688cf1366c69b96b393f1cbbbf87aeb9ced9118a
```

On Windows PowerShell, download the archive with `curl.exe`.

```powershell
New-Item -ItemType Directory -Force .\datasets | Out-Null
curl.exe -L "https://github.com/PINTO0309/YawNet/releases/download/resources/yawpose.tar.gz" -o .\datasets\yawpose.tar.gz
```

On Linux or macOS, use `curl`.

```bash
mkdir -p datasets
curl -L "https://github.com/PINTO0309/YawNet/releases/download/resources/yawpose.tar.gz" -o datasets/yawpose.tar.gz
```

### 4. Extract YawPose

Create an extraction directory and unpack the archive there.

On Windows PowerShell, use the `tar` command bundled with current Windows versions.

```powershell
New-Item -ItemType Directory -Force .\datasets\yawpose | Out-Null
tar -xzf .\datasets\yawpose.tar.gz -C .\datasets\yawpose
```

On Linux or macOS, use the same archive format with the platform `tar` command.

```bash
mkdir -p datasets/yawpose
tar -xzf datasets/yawpose.tar.gz -C datasets/yawpose
```

The dataset root passed to this application is the directory that directly contains both `labels_fixed.jsonl` and `images/`. The extracted dataset contains the files documented by YawNet, including this minimum layout.

```text
yawpose/
├── images/
├── labels_fixed.jsonl
├── train.jsonl
├── val.jsonl
├── qa_sixd.jsonl
└── ...
```

If the archive extraction created an additional top-level directory, pass that inner directory rather than its parent. On PowerShell, the location of `labels_fixed.jsonl` can be found with this command.

```powershell
Get-ChildItem .\datasets\yawpose -Recurse -Filter labels_fixed.jsonl
```

On Linux or macOS, locate it with `find`.

```bash
find datasets/yawpose -name labels_fixed.jsonl -print
```

### 5. Launch the annotator

Pass the dataset root as the positional argument. For example, if `datasets/yawpose/labels_fixed.jsonl` exists directly, launch the application with this command.

```bash
uv run yawpose-annotator datasets/yawpose
```

The application listens on `127.0.0.1:8080` and opens the UI in the default browser.

The dataset path does not need to live inside this repository. An absolute path can be passed instead.

```powershell
uv run yawpose-annotator "D:\datasets\yawpose"
```

### 6. Narrow the samples to audit

The top controls filter samples using the original GT rather than the edited value. This prevents a sample from disappearing from the current audit range immediately after its GT is corrected.

Set a yaw range and, when useful, a source filter before starting manual review. A wraparound yaw range such as `340` to `20` is supported.

The default page contains 30 samples sorted by source, original yaw, pitch, and image name.

### 7. Correct the GT

Select a tile and edit its pose with the keyboard. Each tile displays the original GT in red and the current corrected GT in green. When a value has not been modified, the two lines overlap.

The keyboard controls are defined as follows.

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

Arrow-key repeat events are accepted, so holding an arrow key continuously changes the selected GT.

Modified samples are marked `FIXED`. Unsaved edits also have a blue inset border and `*` marker.

### 8. Save and resume the work

Press `Enter` to save staged corrections. By default, corrections are written separately from the original YawPose labels.

```text
yawpose/
├── labels_fixed.jsonl          # original file; never modified
├── manual_corrections.jsonl    # manual overrides created by this tool
└── ...
```

Restarting the application with the same dataset root loads the existing correction file and resumes from the saved values.

### 9. Export corrected labels

Use `Export merged labels` in the UI when a complete label file is needed for training or another downstream process.

The default output is `labels_manual_fixed.jsonl`. Export preserves every original JSONL field and replaces only corrected `yaw_deg` and `pitch_deg` values.

```text
yawpose/
├── labels_fixed.jsonl
├── manual_corrections.jsonl
├── labels_manual_fixed.jsonl
└── ...
```

## Custom paths

The input labels, correction file, and export path can be overridden explicitly when the working files should be kept outside the dataset directory.

```bash
uv run yawpose-annotator /path/to/yawpose \
  --labels /path/to/yawpose/labels_fixed.jsonl \
  --corrections /work/manual_corrections.jsonl \
  --export /work/labels_manual_fixed.jsonl
```

The page size and server address can also be changed with the CLI options.

```bash
uv run yawpose-annotator /path/to/yawpose \
  --page-size 30 \
  --host 127.0.0.1 \
  --port 8080
```

## Correction format

`manual_corrections.jsonl` contains only samples whose final value differs from the original GT. Each line preserves both values for auditability.

```json
{"image":"images/example.jpg","original_yaw":30.0,"corrected_yaw":52.0,"original_pitch":null,"corrected_pitch":null,"updated_at":"2026-09-16T00:00:00+00:00"}
```

Saving is atomic: the tool writes a temporary file, fsyncs it, and then replaces the correction file.

## Development

Run the project checks with uv.

```bash
uv run pytest
uv run ruff check .
```
