"""GUI smoke test: build the full viewer offscreen, drive markups, render.

Requires a working (possibly virtual) display + OpenGL.  Saves a screenshot of
each panel so the result can be eyeballed.  Run::

    python tests/smoke_gui.py
"""

from __future__ import annotations

import os
import sys

import numpy as np
import vtk
from PyQt5 import QtWidgets

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from tui.core.image_series import ImageSeries  # noqa: E402
from tui.core.enums import MarkupMode, ViewType  # noqa: E402
from tui.app import ViewerApp  # noqa: E402
from tui.examples.custom_app import ExampleViewer  # noqa: E402


def _make_temporal_series(n=3, dims=(40, 40, 40)) -> ImageSeries:
    """A simple 4D phantom: a moving bright blob over time."""
    time_to_image = {}
    nx, ny, nz = dims
    xx, yy, zz = np.meshgrid(
        np.arange(nx), np.arange(ny), np.arange(nz), indexing="ij")
    for t in range(n):
        cx = 10 + 5 * t
        blob = np.exp(-(((xx - cx) ** 2 + (yy - 20) ** 2 + (zz - 20) ** 2) / 50.0))
        data = (200 * blob + 30).astype(np.float32)
        img = vtk.vtkImageData()
        # Non-zero starting extent mirrors real data and exercises the
        # world<->voxel extent offset used by painting.
        img.SetExtent(5, 5 + nx - 1, 7, 7 + ny - 1, 9, 9 + nz - 1)
        img.SetSpacing(1.0, 1.0, 1.0)
        from ngawari import vtkfilters
        vtkfilters.setArrayFromNumpy(img, data, "PixelData", SET_SCALAR=True, IS_3D=True)
        # add a second array to exercise the array selector
        vtkfilters.setArrayFromNumpy(img, data * 2.0, "PixelData_x2", IS_3D=True)
        time_to_image[float(t)] = img
    return ImageSeries(time_to_image)


def _screenshot(view, path):
    rw = view._render_window
    w2i = vtk.vtkWindowToImageFilter()
    w2i.SetInput(rw)
    w2i.Update()
    writer = vtk.vtkPNGWriter()
    writer.SetFileName(path)
    writer.SetInputConnection(w2i.GetOutputPort())
    writer.Write()


def main():
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    series = _make_temporal_series()
    viewer = ExampleViewer(series, title="smoke")
    viewer.resize(1200, 800)
    viewer.show()
    app.processEvents()

    # Verify temporal control is enabled.
    assert viewer.time_slider.isEnabled(), "time slider should be enabled for 4D"
    assert viewer.time_bar.isVisible()

    # Array selector populated.
    names = series.array_names
    assert set(names) == {"PixelData", "PixelData_x2"}, names

    # Drive markups programmatically (mirrors what the interactor would do).
    st = viewer.state
    st.mode = MarkupMode.POINTS
    c = series.center
    viewer._on_point_picked(viewer.views[ViewType.AXIAL], c)
    viewer._on_point_picked(viewer.views[ViewType.AXIAL], (c[0] + 5, c[1], c[2]))

    st.mode = MarkupMode.SPLINES
    for p in [(10, 10, 20), (30, 10, 20), (30, 30, 20), (10, 30, 20)]:
        viewer._on_point_picked(viewer.views[ViewType.AXIAL], p)
    viewer._on_action("close_spline")

    st.mode = MarkupMode.PAINT
    st.paint_radius = 4
    viewer._on_paint(viewer.views[ViewType.AXIAL], series.center, erase=False)
    assert st.markups.has_paint(0), "paint should have marked the frame"
    # Painting the volume centre must land near the array centre, not the edge
    # (regression guard for the extent-offset bug).
    _m = st.markups.paint_mask(0, create=False)
    _centroid = np.argwhere(_m > 0).mean(axis=0)
    _mid = np.array(_m.shape) / 2.0
    assert np.all(np.abs(_centroid - _mid) < 6), (_centroid, _mid)

    # Move to a later time, add a keyframe spline, check interpolation exists.
    viewer.time_slider.setValue(2)
    st.mode = MarkupMode.SPLINES
    for p in [(10, 10, 20), (30, 10, 20), (30, 30, 20), (10, 30, 20)]:
        viewer._on_point_picked(viewer.views[ViewType.AXIAL], p)
    viewer._on_action("close_spline")
    interp = st.markups.effective_splines(1)
    assert interp and not interp[0].is_manual, "frame 1 should be interpolated"

    # Exercise the array selector + maximise + custom button.
    viewer._on_array_changed("PixelData_x2")
    viewer._apply_grid_layout(ViewType.SAGITTAL)
    viewer._apply_grid_layout(None)
    viewer.add_centre_point()  # custom callback
    app.processEvents()
    viewer.refresh_all()
    app.processEvents()

    # Double-oblique: rotate the frame about two different axes; planes must
    # stay mutually orthogonal.
    from tui.core.enums import Orientation
    viewer.time_slider.setValue(0)
    st.rotate_about(Orientation.AXIAL, 0.4)
    st.rotate_about(Orientation.SAGITTAL, 0.3)
    a = st.axes
    import numpy as _np
    gram = a @ a.T
    assert _np.allclose(gram, _np.eye(3), atol=1e-6), f"axes not orthonormal:\n{gram}"
    assert not st.is_axis_aligned()
    viewer.refresh_all()
    app.processEvents()

    # Modify: grab a spline handle and move it.
    st.mode = MarkupMode.MODIFY
    sp = st.markups.manual_splines(0)
    assert sp, "expected a manual spline at t=0"
    before = tuple(sp[0].control_points[0])
    sp[0].control_points[0] = (before[0] + 3, before[1] + 2, before[2])
    assert sp[0].control_points[0] != before
    viewer.refresh_all()
    app.processEvents()

    # Capture the oblique state for visual inspection before resetting.
    out = os.path.join(HERE, "_smoke_out")
    os.makedirs(out, exist_ok=True)
    for vt, view in viewer.views.items():
        _screenshot(view, os.path.join(out, f"oblique_{vt.value}.png"))

    # Reset planes back to axis-aligned.
    viewer._on_reset_frame()
    assert st.is_axis_aligned()
    app.processEvents()

    out = os.path.join(HERE, "_smoke_out")
    os.makedirs(out, exist_ok=True)
    for vt, view in viewer.views.items():
        _screenshot(view, os.path.join(out, f"panel_{vt.value}.png"))

    # Save markups to confirm IO path end-to-end.
    files = viewer.save_markups(os.path.join(out, "markups"), include_interpolated=True)
    print("Saved markup files:", len(files))
    print("Screenshots in:", out)
    print("SMOKE OK")


if __name__ == "__main__":
    main()
