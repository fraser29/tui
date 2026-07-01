"""Template for subclassing :class:`tui.ViewerApp` with custom buttons.

Copy this file into your own package (as in kmr-cardiac-research) and wire your own
study-specific actions into the 6×2 **Custom** button grid on the right panel.

**Important:** use absolute ``from tui import ...`` imports (as below), not
``from ..app`` — relative imports only work for files that remain inside the
``tui`` package tree.

Run
---
From the repository root::

    PYTHONPATH=. python -m tui.examples.custom_viewer_template TEST_DATA/test_data.vti

Or from Python::

    from tui import launch
    from tui.examples.custom_viewer_template import CustomViewer
    launch("/path/to/data.vti", viewer_class=CustomViewer)

Extension model
---------------
1. Subclass :class:`~tui.app.ViewerApp`.
2. Override :meth:`customise` and call :meth:`~tui.app.ViewerApp.set_custom_button`
   (row/col in 0..5 / 0..1) or :meth:`~tui.app.ViewerApp.set_custom_buttons`
   (flat index 0..11, row-major).
3. Implement zero-argument callbacks.  Exceptions are logged; they never crash
   the UI.  The viewer calls :meth:`~tui.app.ViewerApp.refresh_all` after
   each callback.

Data access (inside any callback)
---------------------------------
``self.state`` is the full :class:`~tui.state.ViewerState` object.  These
convenience properties on :class:`~tui.app.ViewerApp` are shortcuts:

+---------------------------+------------------------------------------------+
| Property / call           | What you get                                   |
+===========================+================================================+
| ``self.image_series``     | :class:`~tui.core.image_series.ImageSeries`|
| ``self.current_time_id``  | int index of the frame shown in the slider     |
| ``self.current_array``    | name of the scalar array being displayed       |
| ``self.current_image``    | ``vtkImageData`` for the current time step     |
| ``self.markups``          | :class:`~tui.core.markups.Markups` container|
| ``self.save_markups(...)``| export all markups (see File → Save markups)   |
| ``self.refresh()``        | redraw every panel after you mutate state      |
+---------------------------+------------------------------------------------+

See :meth:`CustomViewer._access_cookbook` for copy-paste snippets covering other
time steps, numpy volumes, slice indices, and every markup type.

Passing your own context (e.g. a ``subject`` object)
----------------------------------------------------
Pass whatever image source your pipeline already has — you do **not** need to
build an :class:`~tui.core.image_series.ImageSeries` yourself.
:func:`~tui.io.as_image_series` (called automatically by :class:`ViewerApp`)
accepts a path, a single :class:`vtk.vtkImageData`, a ``{time: image}`` dict,
or a list of volumes.

Override :meth:`__init__` to accept your ``subject`` and forward the image
source to :meth:`ViewerApp.__init__`.  Button callbacks are methods on the
same viewer instance — use ``self.subject``, ``self.WORK_DIR``, etc.::

    from tui import launch
    from tui.io import as_image_series

    class MyViewer(ViewerApp):
        def __init__(self, data, title="TUI", subject=None):
            self.subject = subject
            super().__init__(data, title=title)

        def customise(self):
            if self.subject is not None:
                self.WORK_DIR = self.subject.get_save_dir()
            self.set_custom_button(0, 0, "Save", self.save_roi)

        def save_roi(self):
            path = os.path.join(self.WORK_DIR, f"{self.subject.id}_roi.vtp")
            ...

    # path on subject:
    launch(subject.MIPVTI, viewer_class=MyViewer, subject=subject)

    # in-memory VTK dict already on subject:
    launch(subject.time_to_vtk, viewer_class=MyViewer, subject=subject)

    # explicit conversion (e.g. inside subject before launch):
    series = as_image_series(subject.get_vtk_dict())
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Any, List, Optional

from ngawari import fIO
from PyQt5 import QtWidgets

from tui import ViewerApp, launch
from tui.core.enums import Orientation
from tui.core.markups import Spline
from tui.io.markup_io import _spline_to_polydata, _transform_polydata

logger = logging.getLogger(__name__)


class CustomViewer(ViewerApp):
    """Starting point for a study-specific viewer.

    Edit the class attributes, register buttons in :meth:`customise`, and add
    your own callback methods below.
    """

    # ----------------------------------------------------------------- settings
    # Directory for one-click exports (override with env TUI_WORK_DIR).
    WORK_DIR: str = os.environ.get(
        "TUI_WORK_DIR", os.path.expanduser("~/tui_work"))

    # Basename used by :meth:`save_named_spline` (writes ``<name>.vtp``).
    ROI_SPLINE_NAME: str = "roiABC"

    # Which spline to export when several exist on one frame:
    #   "last"  -> most recently added manual spline
    #   "label" -> first spline whose ``Spline.label`` matches ROI_SPLINE_NAME
    ROI_SPLINE_PICK: str = "last"

    def __init__(self, data, title: str = "TUI", subject: Any = None):
        """``data`` — path, vtkImageData, ``{time: image}`` dict, or image list.

        Optional ``subject`` is your study object (paths, IDs, pipelines, …).
        Set on ``self`` before ``super().__init__`` so :meth:`customise` can
        read it.  :class:`ViewerApp` converts ``data`` to :class:`ImageSeries`
        internally via :func:`~tui.io.as_image_series`.
        """
        self.subject = subject
        super().__init__(data, title=title)

    # ===================================================================== hook
    def customise(self) -> None:
        """Register custom buttons.  Called once during ``ViewerApp`` init."""
        if self.subject is not None:
            # Example: pull save directory from your subject object.
            # self.WORK_DIR = self.subject.get_save_dir()
            pass
        # Row/col layout (6 rows × 2 columns).  Unused slots stay disabled.
        self.set_custom_button(0, 0, f"Save {self.ROI_SPLINE_NAME}",
                               self.save_named_spline)
        self.set_custom_button(0, 1, "Save all markups", self.save_all_markups)

        # --- add your own buttons here ------------------------------------
        # self.set_custom_button(1, 0, "My action", self.my_action)
        #
        # Or set several at once by flat index (0..11, row-major):
        # self.set_custom_buttons({
        #     2: ("Button A", self.action_a),
        #     3: ("Button B", self.action_b),
        # })

    # -------------------------------------------------------- example callbacks
    def save_named_spline(self) -> None:
        """Export one spline at the current time step to ``WORK_DIR/<name>.vtp``.

        This is a common workflow shortcut: draw a spline in **Splines** mode,
        then press the button to drop a named ROI file in your working folder
        without stepping through the File dialog.
        """
        spline = self._pick_spline(self.current_time_id)
        if spline is None:
            QtWidgets.QMessageBox.warning(
                self, "Save spline",
                f"No spline on frame {self.current_time_id + 1} "
                f"(t={self.state.current_time:g}).\n"
                "Draw one in Splines mode first.")
            return
        if len(spline.control_points) < 2:
            QtWidgets.QMessageBox.warning(
                self, "Save spline", "Spline needs at least two control points.")
            return

        os.makedirs(self.WORK_DIR, exist_ok=True)
        path = self._spline_export_path(self.ROI_SPLINE_NAME)
        poly = self._spline_polydata_world(spline)
        fIO.writeVTKFile(poly, path)

        QtWidgets.QMessageBox.information(
            self, "Saved spline",
            f"Wrote {os.path.basename(path)} to:\n{self.WORK_DIR}\n\n"
            f"Frame {self.current_time_id + 1}  "
            f"({len(spline.control_points)} control points, "
            f"{'closed' if spline.closed else 'open'})")

    def save_all_markups(self) -> None:
        """Export every markup type to ``WORK_DIR`` (manual keyframes only)."""
        os.makedirs(self.WORK_DIR, exist_ok=True)
        files = self.save_markups(
            self.WORK_DIR, prefix="markup", include_interpolated=False)
        QtWidgets.QMessageBox.information(
            self, "Saved markups",
            f"Wrote {len(files)} file(s) to:\n{self.WORK_DIR}")

    # ------------------------------------------------------------- your actions
    # def my_action(self) -> None:
    #     """Template for a new callback — uncomment and wire a button above."""
    #     vol = self._numpy_volume(self.current_time_id, self.current_array)
    #     logger.info("volume shape %s, centre voxel value %s",
    #                 vol.shape, vol[vol.shape[0] // 2, vol.shape[1] // 2, vol.shape[2] // 2])

    # =========================================================== access helpers
    def _access_cookbook(self) -> None:
        """Reference snippets — not called automatically; read/copy as needed."""

        # --- images ---------------------------------------------------------
        # Current frame (vtkImageData):
        _img_now = self.current_image

        # Any other time step (0 .. n_times-1):
        _img_t2 = self.image_series.get_image(2)

        # Series metadata:
        _dims = self.image_series.dimensions       # (nx, ny, nz), VTK order
        _spacing = self.image_series.spacing
        _origin = self.image_series.origin
        _n_times = self.image_series.n_times
        _array_names = self.image_series.array_names

        # Numpy scalar volume for the displayed array (Fortran order, 3D):
        _vol = self._numpy_volume(self.current_time_id, self.current_array)

        # --- slices / reslice frame -----------------------------------------
        # Approximate voxel index of the current plane (axis-aligned case):
        _axial_index = self.state.slice_for(Orientation.AXIAL)
        _sagittal_index = self.state.slice_for(Orientation.SAGITTAL)
        _coronal_index = self.state.slice_for(Orientation.CORONAL)

        # World-space crosshair centre and oblique frame axes (3×3, rows e0..e2):
        _center = self.state.center
        _axes = self.state.axes

        # World Z (or X/Y) coordinate of the axial plane centre:
        _z = self.state.slice_world_coord(Orientation.AXIAL)

        # Coordinate helpers (world <-> voxel indices for paint):
        _ijk = self.state.world_to_voxel((_center[0], _center[1], _center[2]))
        _xyz = self.state.voxel_to_world(_ijk)

        # --- markups at the current time ------------------------------------
        _tid = self.current_time_id

        # Effective = manual keyframe or interpolated result (what you see):
        _points = self.markups.effective_points(_tid)
        _splines = self.markups.effective_splines(_tid)
        _paint = self.markups.effective_paint(_tid)   # numpy mask or None

        # Manual-only (what the user actually drew — use for saving):
        _manual_pts = self.markups.manual_points(_tid)
        _manual_splines = self.markups.manual_splines(_tid)
        _manual_paint = self.markups.paint_mask(_tid, create=False)

        # --- markups across the whole series --------------------------------
        _summary = self.markups.summary()   # counts per type
        for _t in self.markups.manual_time_ids():
            _spl = self.markups.manual_splines(_t)
            logger.debug("t=%d has %d manual spline(s)", _t, len(_spl))

        # Iterate every frame (including interpolated) when exporting:
        for _t in range(self.image_series.n_times):
            _eff = self.markups.effective_splines(_t)

        # Active in-progress spline while drawing (or None):
        _active = self.state.active_spline

    def _numpy_volume(self, time_id: int, array_name: str):
        """Return the scalar array as a 3D numpy array (Fortran order)."""
        from ngawari import vtkfilters

        img = self.image_series.get_image(time_id)
        return vtkfilters.getScalarsAsNumpy(
            img, array_name, pointData=True, RETURN_3D=True)

    def _pick_spline(self, time_id: int) -> Optional[Spline]:
        splines = self.markups.manual_splines(time_id)
        if not splines:
            return None
        if self.ROI_SPLINE_PICK == "label":
            for sp in splines:
                if sp.label == self.ROI_SPLINE_NAME:
                    return sp
            return None
        return splines[-1]

    def _spline_export_path(self, basename: str) -> str:
        """Build ``WORK_DIR/<basename>.vtp``, suffixing the time id when 4D."""
        stem = basename
        if self.image_series.is_temporal:
            stem = f"{basename}_t{self.current_time_id:03d}"
        return os.path.join(self.WORK_DIR, f"{stem}.vtp")

    def _spline_polydata_world(self, spline: Spline):
        """Polyline in true world/patient coordinates (matches File → Save)."""
        poly = _spline_to_polydata(spline)
        if self.image_series.has_patient_transform:
            poly = _transform_polydata(poly, self.image_series.patient_matrix)
        return poly


# ------------------------------------------------------------------ standalone
def main(argv: Optional[List[str]] = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print("usage: python -m tui.examples.custom_viewer_template <image>")
        return 2
    return launch(args[0], viewer_class=CustomViewer)


if __name__ == "__main__":
    raise SystemExit(main())
