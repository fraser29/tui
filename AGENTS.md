# AGENTS.md — TUI / PIWAKAWAKA

Guidance for AI coding agents working in this repository.

## Project summary

**TUI** is a PyQt5 + VTK medical imaging viewer for 4D (3D + time) markup workflows. A companion **PIWAKAWAKA** viewer (`-2D` CLI flag) provides 2D slice viewing (axial/coronal/sagittal/custom stacks) with spline-friendly markup.

Design goals: simplicity and easy customization (mod buttons, keyboard shortcuts) for study-scale batch work—not a full Slicer/MITK replacement.

**Author:** Fraser M. Callaghan  
**Package:** `tui` (see `pyproject.toml`, entry point `tui = tui.tuiMaster:main`)

## External dependencies

| Package | Role |
|---------|------|
| `vtk` (≥9.3) | Rendering, widgets, image IO |
| `PyQt5` | UI |
| `spydcmtk` | DICOM → VTK, patient metadata |
| `ngawari` | `fIO`, `vtkfilters`, `ftk` (splines, polydata, file IO) — **not vendored in this repo** |

Agents cannot run the app in a bare sandbox without `ngawari` installed. Do not mock or stub it unless the task explicitly requires tests without it.

## Repository layout

```
tui/                          # Python package
  __init__.py                 # configure_logging(), set_log_level()
  tuiMaster.py                # CLI, TUIProject / TUIBasic, launch helpers
  tuiViewer.py                # 3D/4D TUIMarkupViewer (reslice cursor, 4-panel)
  piwakawakaViewer.py         # 2D PIWAKAWAKAMarkupViewer
  baseMarkupViewer.py         # Shared viewer logic (save, animation, buttons)
  baseMarkupUI.py             # Shared Qt UI layout
  tuimarkupui.py              # TUI-specific UI (incl. send-to-piwakawaka buttons)
  piwakawakamarkupui.py       # PIWAKAWAKA UI
  tuiMarkups.py               # Markups, points, splines (vtkSplineWidget)
  tuiStyles.py / piwakawakaStyles.py  # Interactor styles
  tuiUtils.py                 # Dialogs, orientation constants
  tui3D.py                    # Standalone 3D surface tool
  help_tui.txt / help_piwakawaka.txt
pyproject.toml
README.md
```

## Architecture

### Class hierarchy

```
BaseMarkupUI                    # Qt widgets (generated-style layout)
  ├── tuimarkupui.Ui_BASEUI
  └── piwakawakamarkupui.Ui_BASEUI

BaseMarkupViewer                # Logic mixin (no Qt window)
  ├── TUIMarkupViewer           # 3D reslice + grid + markup
  └── PIWAKAWAKAMarkupViewer    # 2D slices + custom oblique stacks

_TUIProj
  ├── TUIProject  → self.ex = TUIMarkupViewer()
  │     └── TUIBasic          # Example customized buttons
  └── TUI2DProject → self.ex = PIWAKAWAKAMarkupViewer()
        └── TUI2D
```

Viewers use **multiple inheritance**: `(QMainWindow, Ui_BASEUI, BaseMarkupViewer)`.

### Markup model (`tuiMarkups.py`)

- `Markups` holds per–time-index collections: `Points`, `Splines`, `Polydata`, `Masks`.
- **TUI (3D):** splines tied to reslice planes in 3D; `showSplines_timeID_CP`.
- **PIWAKAWAKA (2D):** splines also keyed by `sliceID`; `showSplines_timeID_sliceID`.
- Manual splines: `is_manual=True` (orange). Interpolated: `is_manual=False` (cyan), created by `interpolateSplinesFromManualKeyframes()`.

### TUI → PIWAKAWAKA handoff

`tuiViewer._launchPiwakawakaWithResliceData()` opens a child PIWAKAWAKA window with shared `vtiDict` and custom slice centers/normals. Custom mod buttons are cloned via `clone_mod_push_button_dict_for_viewer()` so project callbacks (`saveROI`, etc.) run with `project.ex` temporarily pointed at the child viewer.

## Running and developing

```bash
# Install (editable)
pip install -e .

# 3D TUI
tui -in /path/to/data.vti
tui -in /path/to/dicom_dir -logLevel DEBUG

# 2D PIWAKAWAKA
tui -in /path/to/data.vti -2D
```

**Library use from another app:**

```python
import logging
import tui

tui.configure_logging(level=logging.DEBUG)  # before importing tui.tuiMaster
from tui.tuiMaster import LaunchCustomApp, TUIProject

class MyProject(TUIProject):
  def setup(self, inputPath, workDir=None, scalar=None):
    super().setup(inputPath, workDir, scalar)
    self.ex.updatePushButtonDict({
      0: ['Save ROI', self.saveROI],
    })

  def saveROI(self):
    self.ex.saveLine(LINE_LOOP=self.ex.splineClosed, prefix='roi')

LaunchCustomApp(MyProject, '/path/to/data')
```

Do **not** call `configure_logging(level="INFO")` at import time in library modules; host apps own logging setup.

## Customization patterns

### Mod push buttons

- Dict shape: `{index: ['Label', callable], ...}` (indices 0–11).
- Applied with `viewer.updatePushButtonDict(d)`.
- Prefer **project methods** that use `self.ex.*` so piwakawaka rebinding works.
- Avoid bare lambdas capturing the 3D viewer unless you accept they will not rebind to piwakawaka.

### Qt `clicked` slots

`QPushButton.clicked` may pass a `checked` bool. Handlers are wrapped with `as_qt_button_slot()` in `baseMarkupViewer.updatePushButtonDict`—project methods should take only `self`, not extra signal args.

### Saving markups

- `savePoints()`, `saveLine()`, `saveVOI()` → `getMarkupAsPolydata()` / `getMarkupAsPolydata_lines()`.
- Spline mode: resamples via `MarkupSpline.getPoints(nSplinePts)`; sparse auto splines fall back if `ftk.splinePoints` / periodic `splprep` fails.
- PIWAKAWAKA world export must pass each spline’s **`timeID`** into `imageCS_To_WorldCS_X` (not only `currentTimeID`).

## Logging

- Logger namespace: `tui.*` (e.g. `tui.baseMarkupViewer`, `tui.piwakawakaViewer`).
- `tui.configure_logging()` — idempotent stream handler on package logger `tui`.
- `tui.set_log_level()` — level only, for apps with existing handlers.
- `TUIProject(..., VERBOSE=True)` sets DEBUG on the `tui` logger.

## Coding conventions

- Match existing style: minimal diffs, no drive-by refactors, reuse `ngawari.vtkfilters` / `fIO`.
- UI strings and help text live in `help_*.txt` and `*markupui.py` where applicable.
- VTK warnings suppressed globally in viewer modules (`vtkOutputWindow`, `vtkLogger`).
- Comments only for non-obvious coordinate-system or VTK behaviour.

## Common pitfalls (read before changing markup / piwakawaka)

1. **Separate `Markups` per viewer** — saving from piwakawaka must use piwakawaka’s `self.ex`, not the parent TUI viewer (handled by button rebind + `project.ex` swap).
2. **PIWAKAWAKA coordinates** — interpolated splines need **x, y, z** in image space; `imageCS_To_WorldCS_X` needs the spline’s `timeID` and `sliceID`.
3. **Auto spline export** — 12-handle interpolated splines may fail periodic `splprep`; fallbacks live in `MarkupSpline.getPoints` and `_resample_polyline_handles`.
4. **Do not reset logging on import** in `tuiMaster` or other modules used as a library.
5. **`ngawari` is required** — grep `/home/fraser/DEV/ngawari` only if present locally; do not duplicate vtkhelpers into this repo.

## Tests

No automated test suite in this repository. Validate interactively or with small scripts that mock viewers only when `ngawari` is unavailable.

## Git / PR

- Do not commit unless the user asks.
- Do not force-push `main`.
- Keep commit messages focused on *why*.

## Files agents touch most often

| Task | Start here |
|------|------------|
| New save button / workflow | Subclass `TUIProject` in user code, or `TUIBasic` in `tuiMaster.py` |
| 3D viewer behaviour | `tuiViewer.py`, `baseMarkupViewer.py` |
| 2D / splines / interpolate | `piwakawakaViewer.py`, `tuiMarkups.py` |
| Spline polydata / export bugs | `tuiMarkups.py` (`MarkupSpline`, `MarkupSplines`) |
| Launch piwakawaka from TUI | `tuiViewer._launchPiwakawakaWithResliceData` |
| UI layout | `baseMarkupUI.py`, `tuimarkupui.py`, `piwakawakamarkupui.py` |
| Logging | `tui/__init__.py` |
