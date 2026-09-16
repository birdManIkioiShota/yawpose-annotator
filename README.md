# yawpose-annotator

Local, keyboard-first annotation UI for manually auditing and correcting YawPose ground-truth yaw/pitch values.

The original `labels_fixed.jsonl` is never modified. Manual overrides are stored separately in `manual_corrections.jsonl`, and a merged label file can be exported when needed.

## Requirements

- Windows 10/11 with PowerShell, or Ubuntu 22.04/24.04
- Git
- [uv](https://docs.astral.sh/uv/)
- About 1.4 GB of free space for the compressed YawPose archive, plus space for extraction

The project uses Python 3.12. `uv` can install and manage the required Python interpreter, so a system-wide Python installation is not required.

## Windows setup

The commands in this section are intended for PowerShell.

### 1. Install Git and uv

Install Git if it is not already available. Git for Windows can be obtained from:

https://git-scm.com/download/win

Install `uv` with the official installer.

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Open a new PowerShell window after installation, then verify that `uv` is available.

```powershell
uv --version
```

### 2. Clone this repository

```powershell
git clone https://github.com/birdManIkioiShota/yawpose-annotator.git
cd yawpose-annotator
```

### 3. Install Python and project dependencies

Install Python 3.12 through `uv`, then synchronize the project environment.

```powershell
uv python install 3.12
uv sync --group dev
```

`uv` creates and manages the virtual environment automatically. Manual activation is not required.

### 4. Download YawPose

The official dataset is published as `yawpose.tar.gz` in the `resources` release of PINTO0309/YawNet.

Release page:

https://github.com/PINTO0309/YawNet/releases/tag/resources

Direct download:

https://github.com/PINTO0309/YawNet/releases/download/resources/yawpose.tar.gz

Create a local dataset directory and download the archive with `curl.exe`.

```powershell
New-Item -ItemType Directory -Force .\datasets | Out-Null
curl.exe -L "https://github.com/PINTO0309/YawNet/releases/download/resources/yawpose.tar.gz" -o .\datasets\yawpose.tar.gz
```

The archive published when this README was last updated has this SHA-256 digest.

```text
08df8f2e5df8d2c5c0509475688cf1366c69b96b393f1cbbbf87aeb9ced9118a
```

Verify the downloaded archive with PowerShell.

```powershell
Get-FileHash .\datasets\yawpose.tar.gz -Algorithm SHA256
```

### 5. Extract YawPose

Current Windows versions include a `tar` command that can extract the archive directly.

```powershell
New-Item -ItemType Directory -Force .\datasets\yawpose | Out-Null
tar -xzf .\datasets\yawpose.tar.gz -C .\datasets\yawpose
```

The dataset root passed to the application is the directory that directly contains both `labels_fixed.jsonl` and `images\`.

The expected minimum layout is shown here.

```text
yawpose/
├── images/
├── labels_fixed.jsonl
├── train.jsonl
├── val.jsonl
├── qa_sixd.jsonl
└── ...
```

If extraction created an additional top-level directory, locate the actual dataset root with PowerShell.

```powershell
Get-ChildItem .\datasets\yawpose -Recurse -Filter labels_fixed.jsonl
```

Use the parent directory of the returned `labels_fixed.jsonl` as the dataset path.

### 6. Launch the annotator

If `datasets\yawpose\labels_fixed.jsonl` exists directly, launch the application with this command.

```powershell
uv run yawpose-annotator .\datasets\yawpose
```

An absolute dataset path can also be used.

```powershell
uv run yawpose-annotator "D:\datasets\yawpose"
```

The application listens on `127.0.0.1:8080` and opens the UI in the default browser.

## Ubuntu setup

The commands in this section are intended for Ubuntu 22.04 or 24.04.

### 1. Install Git, curl, and uv

Install the basic command-line dependencies first.

```bash
sudo apt update
sudo apt install -y git curl
```

Install `uv` with the official installer.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Reload the shell environment, then verify that `uv` is available.

```bash
source "$HOME/.local/bin/env"
uv --version
```

If the installer prints a different shell initialization command, use the command printed by the installer instead.

### 2. Clone this repository

```bash
git clone https://github.com/birdManIkioiShota/yawpose-annotator.git
cd yawpose-annotator
```

### 3. Install Python and project dependencies

Install Python 3.12 through `uv`, then synchronize the project environment.

```bash
uv python install 3.12
uv sync --group dev
```

`uv` creates and manages the virtual environment automatically. Manual activation is not required.

### 4. Download YawPose

Create a local dataset directory and download the official archive.

```bash
mkdir -p datasets
curl -L "https://github.com/PINTO0309/YawNet/releases/download/resources/yawpose.tar.gz" -o datasets/yawpose.tar.gz
```

The archive published when this README was last updated has this SHA-256 digest.

```text
08df8f2e5df8d2c5c0509475688cf1366c69b96b393f1cbbbf87aeb9ced9118a
```

Verify the downloaded archive with `sha256sum`.

```bash
sha256sum datasets/yawpose.tar.gz
```

### 5. Extract YawPose

Create the extraction directory and unpack the archive.

```bash
mkdir -p datasets/yawpose
tar -xzf datasets/yawpose.tar.gz -C datasets/yawpose
```

The dataset root passed to the application is the directory that directly contains both `labels_fixed.jsonl` and `images/`.

The expected minimum layout is shown here.

```text
yawpose/
├── images/
├── labels_fixed.jsonl
├── train.jsonl
├── val.jsonl
├── qa_sixd.jsonl
└── ...
```

If extraction created an additional top-level directory, locate the actual dataset root with `find`.

```bash
find datasets/yawpose -name labels_fixed.jsonl -print
```

Use the parent directory of the returned `labels_fixed.jsonl` as the dataset path.

### 6. Launch the annotator

If `datasets/yawpose/labels_fixed.jsonl` exists directly, launch the application with this command.

```bash
uv run yawpose-annotator datasets/yawpose
```

An absolute dataset path can also be used.

```bash
uv run yawpose-annotator /data/yawpose
```

The application listens on `127.0.0.1:8080` and opens the UI in the default browser.

## Using the annotator

The UI behavior is the same on Windows and Ubuntu.

### Narrow the samples to audit

The top controls filter samples using the original GT rather than the edited value. This prevents a sample from disappearing from the current audit range immediately after its GT is corrected.

Set a yaw range and, when useful, a source filter before starting manual review. A wraparound yaw range such as `340` to `20` is supported.

The default page contains 30 samples sorted by source, original yaw, pitch, and image name.

### Correct the GT

Select a tile and edit its pose with the keyboard. Each tile displays the original GT in red and the current corrected GT in green. When a value has not been modified, the two lines overlap.

The keyboard controls are defined in this table.

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

### Save and resume the work

Press `Enter` to save staged corrections. By default, corrections are written separately from the original YawPose labels.

The dataset directory will contain the original labels and the manual override file independently.

```text
yawpose/
├── labels_fixed.jsonl          # original file; never modified
├── manual_corrections.jsonl    # manual overrides created by this tool
└── ...
```

Restarting the application with the same dataset root loads the existing correction file and resumes from the saved values.

### Export corrected labels

Use `Export merged labels` in the UI when a complete label file is needed for training or another downstream process.

The default output is `labels_manual_fixed.jsonl`. Export preserves every original JSONL field and replaces only corrected `yaw_deg` and `pitch_deg` values.

The default output files are shown here.

```text
yawpose/
├── labels_fixed.jsonl
├── manual_corrections.jsonl
├── labels_manual_fixed.jsonl
└── ...
```

## Custom paths

The input labels, correction file, and export path can be overridden explicitly when the working files should be kept outside the dataset directory.

A Unix-style example is shown here.

```bash
uv run yawpose-annotator /path/to/yawpose \
  --labels /path/to/yawpose/labels_fixed.jsonl \
  --corrections /work/manual_corrections.jsonl \
  --export /work/labels_manual_fixed.jsonl
```

A Windows PowerShell example is shown here.

```powershell
uv run yawpose-annotator "D:\datasets\yawpose" `
  --labels "D:\datasets\yawpose\labels_fixed.jsonl" `
  --corrections "D:\work\manual_corrections.jsonl" `
  --export "D:\work\labels_manual_fixed.jsonl"
```

The page size and server address can also be changed with CLI options.

```bash
uv run yawpose-annotator /path/to/yawpose \
  --page-size 30 \
  --host 127.0.0.1 \
  --port 8080
```

## Correction format

`manual_corrections.jsonl` contains only samples whose final value differs from the original GT. Each line preserves both values for auditability.

A correction record has this shape.

```json
{"image":"images/example.jpg","original_yaw":30.0,"corrected_yaw":52.0,"original_pitch":null,"corrected_pitch":null,"updated_at":"2026-09-16T00:00:00+00:00"}
```

Saving is atomic: the tool writes a temporary file, fsyncs it, and then replaces the correction file.

## Development

Run the project checks with `uv`.

```bash
uv run pytest
uv run ruff check .
```
