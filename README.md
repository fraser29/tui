# TUI

A customisable **4-panel medical image viewer** built with PyQt5 + VTK.

The window is a 2×2 grid:

```
┌───────────────┬───────────────┐
│   Axial       │   Sagittal    │
├───────────────┼───────────────┤
│   Coronal     │   3D          │
└───────────────┴───────────────┘
```

with a **time slider** along the bottom for temporal (4D) data and a **control
panel** on the right.

## Features

- **4 linked panels**: axial / sagittal / coronal slices + a 3D MPR view
  (orthogonal planes, outline).
- **Double-oblique reslicing**: a draggable **crosshair** translates all planes
  (drag the centre) or rotates them (drag a coloured line). The three planes
  always stay **mutually perpendicular**. *Reset planes* restores axis-aligned.
- **Temporal data**: PVD time series are loaded as multiple time points and
  scrubbed with the time slider. Non-temporal data hides the slider.
- **All IO via [`ngawari`](https://pypi.org/project/ngawari/)** (`fIO`) — `.vti`,
  `.pvd`, `.nii(.gz)`, `.nrrd`, `.mha/.mhd`, and DICOM directories (with the
  optional `spydcmtk` extra).
- **Array selector**: choose which point-data array to display when a volume has
  several.
- **Markup modes**: add points, add splines, paint (a **3D spherical brush**),
  or **modify** existing point/spline handles by dragging — each markup is
  **unique per time step**, with **interpolation** between sparsely annotated
  keyframes.
- **Maximise / grid**: one click to maximise any panel or return to the grid
  (double-click a panel to maximise it too).
- **6×2 grid of user-customisable buttons** wired up by subclassing the viewer.
- **Extensible**: subclass `ViewerApp`, override `customise()`, and your button
  callbacks get full access to the data and markups via `self.state`.

## Install

```bash
pip install -e .
# optional DICOM support:
pip install -e ".[dicom]"
```

Requires `vtk>=9.3`, `PyQt5`, `numpy`, `scipy`, and `ngawari`.

## Run

```bash
# from a single volume
tui -in TEST_DATA/test_data.vti

# choose the starting array
tui -in data.vti -a PixelData

# a temporal series
tui -in study.pvd

# the bundled example with demo custom buttons
tui -in TEST_DATA/test_data.vti --example

# module form
python -m tui -in TEST_DATA/test_data.vti
```

### Controls

| Action | How |
|--------|-----|
| Scroll slices | Mouse wheel over a slice panel |
| Step time backward / forward | Left / Right arrow keys |
| Quit | **Q** |
| Add point at pointer | **.** (period) — over a slice panel |
| Move all planes | Drag the crosshair **centre** (Navigate mode) |
| Rotate planes (oblique) | Drag a crosshair **line** (Navigate mode) — do this in two panels for double-oblique |
| Window / level | Left-drag away from the crosshair in **Navigate** mode |
| Pan / zoom | Middle-drag / right-drag |
| Add point / spline handle | Left-click in **Add points** / **Add splines** mode |
| Move a handle | Left-drag a point/spline handle in **Modify** mode |
| Add a spline control point | Left-click on a spline line in **Modify** mode |
| Delete a handle | Right-click a point/spline handle in **Modify** mode |
| Clear current / all frames | **Clear frame** / **Clear all** buttons |
| Paint / erase | Left-drag / right-click in **Paint** mode (spherical brush) |
| Maximise a panel | Right-panel buttons, or double-click the panel |

## Extending the viewer

Subclass `ViewerApp` and register buttons in `customise()`. Pass a **path,
vtkImageData, `{time: image}` dict, or image list** — you do not need to build
`ImageSeries` yourself (`as_image_series` handles conversion). Each callback runs
with full access to the data and markups:

```python
from tui import launch, ViewerApp
from tui.io import as_image_series  # path, vtkImageData, {time: image} dict, …

class MyViewer(ViewerApp):
    def customise(self):
        self.set_custom_button(0, 0, "Save ROI", self.save_roi)
        # or set several at once by flat index (0..11):
        # self.set_custom_buttons({1: ("Count", self.count_pts)})

    def save_roi(self):
        # self.state gives you everything: image_series, markups, current
        # time/array/slices, window/level, etc.
        self.save_markups("/tmp/roi", include_interpolated=True)

    def count_pts(self):
        ps = self.markups.effective_points(self.current_time_id)
        print(len(ps.points), "points at t", self.current_time_id)

launch("TEST_DATA/test_data.vti", viewer_class=MyViewer)
```

See `tui/examples/custom_app.py` for a complete example.

## Architecture

The model is fully decoupled from the Qt/VTK presentation layer so it can be
tested headlessly:

```
tui/
  core/            # headless data model (no Qt/VTK widgets)
    enums.py       #   Orientation, ViewType, MarkupMode
    image_series.py#   ImageSeries: temporal {time -> vtkImageData}
    markups.py     #   Markups: points/splines/paint + interpolation
  io/              # all reading/writing, via ngawari.fIO
    loader.py      #   load_image_series(), as_image_series()
    markup_io.py   #   save_markups(), build_mask_image()
  state.py         # ViewerState: shared, presentation-agnostic state
  views/           # Qt/VTK widgets
    slice_view.py  #   2D orthogonal slice panel
    volume_view.py #   3D MPR / volume panel
    interactor_styles.py
  ui/
    side_panel.py  # right-hand control panel
  app.py           # ViewerApp (subclassable) + launch()
  cli.py           # `tui` entry point
  examples/        # ExampleViewer
```

## Markup model & interpolation

- Markups are keyed by integer `time_id`. A frame the user has drawn on is a
  *manual keyframe*; other frames are *interpolated* on demand.
- **Points**: linearly interpolated between bracketing keyframes when the point
  counts match, otherwise snapped to the nearest keyframe.
- **Splines**: when bracketing keyframes have matching control-point counts the
  control points are blended directly (keeping a small, editable handle set);
  otherwise they are resampled to a common density (via
  `ngawari.ftk.splinePoints`) and blended.
- **Paint**: a 3D spherical brush writes into a per-keyframe label mask; masks
  are taken from the nearest keyframe (labels are not blended).
- **Modify**: in *Modify* mode you can drag a handle to move it, left-click a
  spline line to insert a control point, and right-click a handle to delete it.
  Editing an *interpolated* (cyan) frame automatically promotes it to an
  editable keyframe; its handles are reduced to the *mean* control-point count
  of the user-drawn splines so it is as easy to edit as a hand-drawn one.
- **Periodic interpolation**: tick *Periodic interpolation* to treat time as
  cyclic — the last keyframe interpolates back to the first across the timeline
  boundary (e.g. a cardiac/respiratory cycle), covering the whole timeline.

Manual markups are drawn in warm colours (yellow points / orange splines),
interpolated markups in cyan.

### Saving in true world coordinates

DICOM (and other oriented) volumes are loaded onto an internal axis-aligned grid
for fast slicing, but the patient orientation (direction-cosine matrix) is kept
as a transform on the series. When you **save markups**, every exported frame
(points, splines and paint masks — including the interpolated ones) is mapped
back into true world / patient coordinates, so the polydata lines up with the
original DICOM in other tools.

## Tests

```bash
# headless model + IO tests (no display needed)
python tests/test_core.py        # or: pytest tests/test_core.py

# full GUI smoke test (needs a display / Xvfb)
python tests/smoke_gui.py
```
