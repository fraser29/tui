# AGENTS.md — TUI

Guidance for AI coding agents working in this repository.

## Project summary

**TUI** is a PyQt5 + VTK 4-panel medical image viewer (axial / sagittal /
coronal / 3D) for 3D and 4D (3D + time) data with point / spline / paint markup
and per-time-step interpolation. It is a clean-room successor to the older `tui`
viewer (see `../tui`), designed from the start for testability and extension.

**Package:** `tui` (entry point `tui = tui.cli:main`).

## External dependencies

| Package | Role |
|---------|------|
| `vtk` (>=9.3) | Rendering, image slicing |
| `PyQt5` | UI |
| `numpy` / `scipy` | Markup maths / interpolation |
| `ngawari` | `fIO` (all file IO), `vtkfilters`, `ftk` (splines) — local source at `/home/fraser/DEV/ngawari` |
| `spydcmtk` | DICOM directory reading |

A working env with all of the above: `/home/fraser/DEV/envs/dev/bin/python`
(also `main`, `cfihura`). The system `python3` lacks PyQt5.

## Hard rules

1. **All file IO goes through `ngawari.fIO`** — never add bare `vtkXMLReader`
   calls outside `tui/io/`. The IO layer (`tui/io/`) is the single
   ngawari integration point.
2. **Keep the model headless.** `tui/core/` and `tui/state.py` must not
   import Qt or `tui.views`. This keeps `tests/test_core.py` runnable
   without a display.
3. **Qt/VTK imports are lazy at the package top level** (`tui/__init__.py`
   exposes `ViewerApp`/`launch` via `__getattr__`). Don't import `tui.app`
   at module import time from `core`/`io`.

## Architecture

```
core/            headless model (Orientation/ViewType/MarkupMode,
                 ImageSeries, Markups+interpolation)
io/              ngawari-backed load_image_series / save_markups
state.py         ViewerState: shared mutable state (data, markups, current
                 time/array/slice, window/level, mode) - the subclass API surface
views/           SliceView (2D), VolumeView (3D), SliceInteractorStyle
ui/side_panel.py right control panel (emits high-level signals)
app.py           ViewerApp(QMainWindow) wires state+views+ui; subclassable
cli.py           argparse entry point
examples/        ExampleViewer (demo custom buttons)
```

Data flow: the UI/interactors mutate `ViewerState` (or call `ViewerApp`
handlers), then `ViewerApp.refresh_all()` tells every view to re-read state and
re-render. Views are dumb renderers of `state`.

## Reslice frame (crosshair / double-oblique)

- `ViewerState` holds a **reslice frame**: `center` (world point) + `axes`
  (3×3 orthonormal, rows `e0,e1,e2`). Each panel slices with a `vtkPlane`
  through `center` whose normal is `axes[orientation.axis]`.
- Slicing uses **`vtkImageResliceMapper.SetSlicePlane(plane)`** (NOT
  `vtkImageSliceMapper`) in both `SliceView` and `VolumeView`, so oblique planes
  render in world space and markups/paint overlay correctly.
- `state.rotate_about(orientation, theta)` rotates the frame about a panel's
  normal — this keeps all three planes mutually perpendicular (the invariant the
  user asked for). The crosshair drag in `SliceView` calls it.
- `step_along_normal` scrolls; `set_center` translates; `reset_frame` restores
  axis-aligned. `is_axis_aligned()` gates the slice-index annotation.

## Coordinate conventions (read before touching views/markups)

- Image arrays are `(nx, ny, nz)` in **Fortran order** to match
  `ngawari.vtkfilters.getScalarsAsNumpy(RETURN_3D=True)` and `setArrayFromNumpy`.
  Paint masks use this shape; flatten with `ravel(order="F")`.
- `Orientation.axis` == out-of-plane frame axis index: SAGITTAL=0, CORONAL=1,
  AXIAL=2.
- Points / spline control points are stored in **world** coordinates; paint in
  voxel space. `ViewerState.world_to_voxel` / `voxel_to_world` convert.
- The viewer always works on an **axis-aligned grid**, but oriented volumes are
  mapped back to true world/patient coordinates via the 4x4
  `ImageSeries.patient_matrix` (`= T(O)·D·T(-O)`, columns of `D` are the unit
  direction cosines). `has_patient_transform` reports a non-identity matrix.
  - **DICOM** (`_dicom_patient_matrix`): `D = [row | col | slice]` built from the
    `ImageOrientationPatient` (row+col cosines) and `SliceVector` field data that
    `spydcmtk` writes onto the VTI (slice falls back to `row × col` for a single
    slice). DICOM is loaded with `buildVTIDict(TRUE_ORIENTATION=False)`.
    Do **not** use `DIRECTION_VECTORS=True` — that matrix is transposed and its
    slice vector is garbage for single-slice series.
  - **Other formats** (`_extract_and_normalise_orientation`): read the image's
    own direction matrix, then reset it to identity.
  - On export, `save_markups` bakes `patient_matrix` into polydata and tags paint
    masks with `D` so markups are saved in **true world (patient) coordinates**.
- Slice picking uses orthographic `DisplayToWorld`, then **projects onto the
  (possibly oblique) slice plane** (`SliceView.display_to_world`).
- Painting is a **3D spherical brush** (`ViewerApp._paint_sphere`, returns the
  affected `(i0,i1,j0,j1,k0,k1)` box), so a stroke is visible/editable from all
  panels.
- Paint drags use a **fast path**: `_on_paint` copies only the changed box into
  each slice overlay (`SliceView.update_paint_region`) and renders only the
  panel under the cursor — never `refresh_all` per mouse-move. The full
  four-panel sync (incl. the 3D view) happens once on stroke end
  (`SliceView.end_paint_stroke` -> `sigFrameChanged`). The overlay keeps an
  `(nx,ny,nz)` Fortran view (`_overlay_view`) aligned with the paint mask for
  O(box) updates. Paint masks themselves are F-contiguous so a full overlay
  upload is a memcpy.
- Wheel-scroll and crosshair drags emit `sigResliceChanged` ->
  `ViewerApp.refresh_reslice`: update slice planes / crosshair / near-plane
  markups **without** re-copying the paint volume. `_refresh_paint` also skips
  the upload when `Markups.paint_revision` is unchanged. Do not route those
  interactions through `refresh_all` (a full-volume copy + `Modified()` per
  event is what made slicing crawl once a labelmap exists).
- **MODIFY** mode (`MarkupMode.MODIFY`): `SliceView.modify_grab/insert/delete/
  drag/release`. Left-drag moves the nearest handle on the plane; left-click on
  a spline line inserts a control point; right-click deletes a handle. Hit-tests
  run against *effective* (manual-or-interpolated) handles; on a confirmed hit
  the frame is promoted (`Markups.promote_to_manual`) so interpolated (cyan)
  markups become editable.

## Markups (`core/markups.py`)

- Keyed by integer `time_id`; manual keyframes vs interpolated results.
- `effective_points/splines/paint(time_id)` return interpolated data; `manual_*`
  return only user-drawn data (used for saving).
- Points lerp when counts match else nearest. Splines: lerp control points
  directly when counts match (keeps handles editable) else resample to common N
  then lerp; paint = nearest keyframe (never blended).
- `promote_to_manual(time_id)` materialises an interpolated frame as an editable
  keyframe (used by MODIFY when a cyan markup is activated); promoted splines are
  resampled to the mean manual handle count (`_mean_manual_handle_count` /
  `_resample_spline`) so they are easy to edit. `bake_interpolation()` is the
  programmatic equivalent that fills a range of frames at once (no UI button).
- `clear_all()` wipes every frame ("Clear all" button, `sigAction("clear_all")`,
  confirmed via dialog in `ViewerApp._clear_all_frames`).
- `Markups.periodic` (the "Periodic interpolation" checkbox,
  `sigPeriodicChanged`) makes time cyclic: `_bracket_frac` wraps the last
  keyframe back to the first for frames outside `[first, last]`, and the bake
  fills the whole timeline.

## Extension model

Subclass `ViewerApp`, override `customise()`, call
`self.set_custom_button(row, col, label, callback)` (6×2 grid) or
`self.set_custom_buttons({index: (label, cb)})`. Callbacks take no args and have
full access via `self.state` and the convenience properties
(`image_series`, `markups`, `current_time_id`, `current_array`, `current_image`,
`refresh()`, `save_markups()`). Callback exceptions are caught and logged, never
crash the UI.

## Running / testing

```bash
PY=/home/fraser/DEV/envs/dev/bin/python

# headless model + IO tests (no display)
PYTHONPATH=. $PY tests/test_core.py

# GUI smoke test — needs a real display/GL. In this sandbox, rendering only
# works OUTSIDE the sandbox (request `all` permissions); offscreen GL otherwise
# fails with a GLX BadValue. Writes screenshots to tests/_smoke_out/.
PYTHONPATH=. $PY tests/smoke_gui.py
```

VTK warnings about GLX / XDG runtime dir are environmental noise.

## Conventions

- Minimal diffs, no drive-by refactors. Reuse `ngawari` helpers
  (`vtkfilters`, `ftk`, `fIO`) instead of re-implementing.
- Comments only for non-obvious VTK / coordinate-system behaviour.
- Do not commit unless asked.

## Test data

`TEST_DATA/test_data.vti` — a single-time chest CT, dims `(288, 183, 226)`,
one point array `PixelData`. It is **not** temporal; use a `.pvd` or the
synthetic phantom in `tests/smoke_gui.py` to exercise the time slider.
