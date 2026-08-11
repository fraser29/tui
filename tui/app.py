"""The main viewer window - a subclassable 4-panel medical image viewer.

Extension model
---------------
Subclass :class:`ViewerApp` and override :meth:`customise` to register custom
buttons.  Inside any custom callback you have full access to the data and
markups via :attr:`state` (and the convenience properties below).  Example::

    class MyViewer(ViewerApp):
        def customise(self):
            self.set_custom_button(0, 0, "Count points", self.count_points)

        def count_points(self):
            ps = self.markups.effective_points(self.current_time_id)
            print(len(ps.points), "points at t", self.current_time_id)

    launch("/path/to/data.vti", viewer_class=MyViewer)
    launch(vtk_dict, viewer_class=MyViewer, subject=my_subject)
"""

from __future__ import annotations

import logging
import os
import sys
from typing import Callable, Dict, Optional, Tuple

import numpy as np
from PyQt5 import QtCore, QtGui, QtWidgets
from vtk.util import numpy_support as vtk_np

from .core.enums import MarkupMode, ViewType
from .core.image_series import ImageSeries
from .core.markups import Markups, Spline
from .io import (
    load_image_series,
    load_markup_labelmap,
    load_markup_polydata,
    load_surface_as_labelmap,
    save_markups,
)
from .io.loader import as_image_series
from .state import ViewerState
from .ui.side_panel import CUSTOM_COLS, SidePanel
from .views import SliceView, VolumeView

logger = logging.getLogger(__name__)

_GRID_POSITIONS: Dict[ViewType, Tuple[int, int]] = {
    ViewType.AXIAL: (0, 0),
    ViewType.SAGITTAL: (0, 1),
    ViewType.CORONAL: (1, 0),
    ViewType.VOLUME: (1, 1),
}


class ViewerApp(QtWidgets.QMainWindow):
    """4-panel (axial / sagittal / coronal / 3D) viewer with markup support."""

    def __init__(self, data=None, *, image_series: Optional[ImageSeries] = None,
                 title: str = "TUI", work_dir: Optional[str] = None):
        super().__init__()
        if image_series is not None and data is not None:
            raise TypeError("pass data or image_series=, not both")
        source = image_series if image_series is not None else data
        if source is None:
            raise TypeError(
                "ViewerApp requires image data: pass a path, vtkImageData, "
                "{time: image} dict, image list, or ImageSeries as data=")
        series = as_image_series(source)
        self.state = ViewerState(series)
        self._custom_callbacks: Dict[Tuple[int, int], Callable] = {}
        self._views_started = False
        self._last_cursor_slice: Optional[SliceView] = None
        self._last_cursor_display: Optional[Tuple[int, int]] = None
        
        self._work_dir = work_dir

        self.setWindowTitle(title)
        self.resize(1400, 900)
        self._build_ui()
        self._connect_signals()
        self._install_shortcuts()
        self._populate_controls()
        # User extension hook - safe to register custom buttons here.
        self.customise()

    @property
    def WORK_DIR(self) -> str:
        """Default directory for open/save dialogs and one-click exports.

        Resolves in order: an explicit ``work_dir`` (constructor arg or later
        assignment), the ``TUI_WORK_DIR`` environment variable, then the current
        working directory - so it always yields a real directory.
        """
        return self._work_dir or os.environ.get("TUI_WORK_DIR") or os.getcwd()

    @WORK_DIR.setter
    def WORK_DIR(self, value: Optional[str]) -> None:
        self._work_dir = value

    # ===================================================================== UI
    def _build_ui(self) -> None:
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        root = QtWidgets.QHBoxLayout(central)

        left = QtWidgets.QVBoxLayout()
        root.addLayout(left, 1)

        # 2x2 grid of views.
        self.grid_widget = QtWidgets.QWidget()
        self.grid_layout = QtWidgets.QGridLayout(self.grid_widget)
        self.grid_layout.setContentsMargins(0, 0, 0, 0)
        self.grid_layout.setSpacing(2)
        left.addWidget(self.grid_widget, 1)

        self.views: Dict[ViewType, QtWidgets.QWidget] = {
            ViewType.AXIAL: SliceView(ViewType.AXIAL, self.state),
            ViewType.SAGITTAL: SliceView(ViewType.SAGITTAL, self.state),
            ViewType.CORONAL: SliceView(ViewType.CORONAL, self.state),
            ViewType.VOLUME: VolumeView(self.state),
        }
        self._apply_grid_layout()

        # Time slider.
        self.time_bar = self._build_time_bar()
        left.addWidget(self.time_bar)

        # Right side panel.
        self.side_panel = SidePanel()
        root.addWidget(self.side_panel, 0)

        self._build_menu()
        self._build_status_bar()

    def _build_status_bar(self) -> None:
        """Footer showing xyz / ijk / value under the cursor."""
        self._cursor_label = QtWidgets.QLabel(self._CURSOR_HINT)
        self._cursor_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self.statusBar().addWidget(self._cursor_label)

    def _build_time_bar(self) -> QtWidgets.QWidget:
        # The bar is always shown (a single-point slider for non-temporal data)
        # to keep the layout simple.  NB: do not call setVisible() here while the
        # widget is still parentless - that pops it as a separate top-level
        # window.  Visibility/enabled state is configured in _sync_time_bar once
        # the widget is parented by the layout.
        bar = QtWidgets.QWidget()
        h = QtWidgets.QHBoxLayout(bar)
        h.setContentsMargins(4, 2, 4, 2)
        h.addWidget(QtWidgets.QLabel("Time"))
        self.time_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.time_slider.setMinimum(0)
        h.addWidget(self.time_slider, 1)
        self.time_label = QtWidgets.QLabel()
        self.time_label.setMinimumWidth(120)
        h.addWidget(self.time_label)
        return bar

    def _sync_time_bar(self) -> None:
        """Configure the (always-visible) time slider for the current series."""
        n = self.state.image_series.n_times
        self.time_slider.setMaximum(max(0, n - 1))
        self.time_slider.setValue(self.state.current_time_id)
        # A single-frame slider has nothing to drag, so disable it.
        self.time_slider.setEnabled(self.state.image_series.is_temporal)
        self.time_label.setText(self._time_label_text())

    def _time_label_text(self) -> str:
        s = self.state
        return f"{s.current_time_id + 1}/{s.image_series.n_times}  (t={s.current_time:g})"

    def _build_menu(self) -> None:
        menu = self.menuBar().addMenu("&File")
        open_act = menu.addAction("Open...")
        open_act.triggered.connect(self._on_open)
        save_act = menu.addAction("Save markups...")
        save_act.triggered.connect(lambda: self._on_action("save"))
        menu.addSeparator()
        quit_act = menu.addAction("Quit")
        quit_act.triggered.connect(self.close)

        markups_menu = self.menuBar().addMenu("&Markups")
        load_poly_act = markups_menu.addAction("Load polydata...")
        load_poly_act.triggered.connect(self._on_load_polydata)
        load_label_act = markups_menu.addAction("Load labelmap...")
        load_label_act.triggered.connect(self._on_load_labelmap)
        load_surf_act = markups_menu.addAction("Load surf2labelmap...")
        load_surf_act.triggered.connect(self._on_load_surf2labelmap)
        markups_menu.addSeparator()
        export_poly_act = markups_menu.addAction("Export polydata...")
        export_poly_act.triggered.connect(self._on_export_polydata)
        export_label_act = markups_menu.addAction("Export labelmap...")
        export_label_act.triggered.connect(self._on_export_labelmap)
        markups_menu.addSeparator()
        paint_limits_act = markups_menu.addAction("Set paint intensity limits...")
        paint_limits_act.triggered.connect(self._on_set_paint_limits)

        help_menu = self.menuBar().addMenu("&Help")
        help_act = help_menu.addAction("Usage help")
        help_act.setShortcut(QtGui.QKeySequence(QtCore.Qt.Key_F1))
        help_act.triggered.connect(self._show_help)

    def _apply_grid_layout(self, maximised: Optional[ViewType] = None) -> None:
        for v in self.views.values():
            self.grid_layout.removeWidget(v)
            v.hide()
        if maximised is None:
            for vt, (r, c) in _GRID_POSITIONS.items():
                self.grid_layout.addWidget(self.views[vt], r, c)
                self.views[vt].show()
        else:
            self.grid_layout.addWidget(self.views[maximised], 0, 0)
            self.views[maximised].show()

    # ================================================================ signals
    def _connect_signals(self) -> None:
        sp = self.side_panel
        sp.sigMaximise.connect(self._maximise)
        sp.sigShowGrid.connect(lambda: self._maximise(None))
        sp.sigArrayChanged.connect(self._on_array_changed)
        sp.sigModeChanged.connect(self._on_mode_changed)
        sp.sigAction.connect(self._on_action)
        sp.sigPaintRadius.connect(lambda r: setattr(self.state, "paint_radius", r))
        sp.sigPaintLabel.connect(lambda v: setattr(self.state, "paint_label", v))
        sp.sigShowMarkups.connect(self._on_show_markups)
        sp.sigShowCrosshair.connect(self._on_show_crosshair)
        sp.sigResetFrame.connect(self._on_reset_frame)
        sp.sigPeriodicChanged.connect(self._on_periodic_changed)
        sp.sigHelp.connect(self._show_help)

        self.time_slider.valueChanged.connect(self._on_time_changed)

        for vt, view in self.views.items():
            view.sigViewActivated.connect(self._on_view_activated)
            if isinstance(view, SliceView):
                view.sigPointPicked.connect(self._on_point_picked)
                view.sigPaint.connect(self._on_paint)
                view.sigFrameChanged.connect(self.refresh_all)
                view.sigWindowLevel.connect(self._on_window_level)
                view._cursor_tracker = self._on_slice_cursor  # set by app

    def _install_shortcuts(self) -> None:
        """Window-level keyboard shortcuts."""
        for key, delta in ((QtCore.Qt.Key_Left, -1), (QtCore.Qt.Key_Right, +1)):
            sc = QtWidgets.QShortcut(QtGui.QKeySequence(key), self)
            sc.setContext(QtCore.Qt.WindowShortcut)
            sc.activated.connect(lambda d=delta: self._step_time(d))

        sc_q = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Q), self)
        sc_q.setContext(QtCore.Qt.WindowShortcut)
        sc_q.activated.connect(self.close)

        sc_pt = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_Period), self)
        sc_pt.setContext(QtCore.Qt.WindowShortcut)
        sc_pt.activated.connect(self._add_point_at_cursor)

        sc_u = QtWidgets.QShortcut(QtGui.QKeySequence(QtCore.Qt.Key_U), self)
        sc_u.setContext(QtCore.Qt.WindowShortcut)
        sc_u.activated.connect(lambda: self._on_action("undo"))

        sc_ctrl_z = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+Z"), self)
        sc_ctrl_z.setContext(QtCore.Qt.WindowShortcut)
        sc_ctrl_z.activated.connect(lambda: self._on_action("undo"))

        sc_ctrl_s = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+S"), self)
        sc_ctrl_s.setContext(QtCore.Qt.WindowShortcut)
        sc_ctrl_s.activated.connect(self.save_markups_helper)

        for key, mode in (
            (QtCore.Qt.Key_N, MarkupMode.NAVIGATE),
            (QtCore.Qt.Key_A, MarkupMode.POINTS),
            (QtCore.Qt.Key_S, MarkupMode.SPLINES),
            (QtCore.Qt.Key_P, MarkupMode.PAINT),
            (QtCore.Qt.Key_M, MarkupMode.MODIFY),
        ):
            sc = QtWidgets.QShortcut(QtGui.QKeySequence(key), self)
            sc.setContext(QtCore.Qt.WindowShortcut)
            sc.activated.connect(lambda m=mode: self._set_markup_mode(m))

    _CURSOR_HINT = "Move the cursor over a slice panel to read xyz / ijk / value"

    def _on_slice_cursor(self, view: SliceView, x: int, y: int) -> None:
        self._last_cursor_slice = view
        self._last_cursor_display = (x, y)
        self._update_cursor_readout(view, x, y)

    def _update_cursor_readout(self, view: SliceView, x: int, y: int) -> None:
        """Update the footer with xyz (3dp), ijk and value under the cursor.

        ``xyz`` is reported in true world (patient) coordinates - the patient
        transform is applied when present.  ``ijk``/value are only shown when the
        point lies inside the image volume; otherwise the footer notes this.
        """
        try:
            world = view.display_to_world(x, y)
            xyz = self._to_patient(world)
            inside, ijk, value = self._probe_image(world)
        except Exception:  # noqa: BLE001 - a readout must never break the UI
            return
        txt = f"xyz = ({xyz[0]:.3f}, {xyz[1]:.3f}, {xyz[2]:.3f})"
        if inside:
            txt += (f"    ijk = ({ijk[0]}, {ijk[1]}, {ijk[2]})"
                    f"    value = {value:g}")
        else:
            txt += "    ijk = -    value = -    (cursor outside image)"
        self._cursor_label.setText(txt)

    def _to_patient(self, world) -> Tuple[float, float, float]:
        """Map an axis-aligned working-grid point to true world (patient) space."""
        m = getattr(self.state.image_series, "patient_matrix", None)
        if m is None or np.allclose(m, np.eye(4)):
            return (float(world[0]), float(world[1]), float(world[2]))
        v = np.asarray(m, dtype=float) @ np.array(
            [world[0], world[1], world[2], 1.0])
        return (float(v[0]), float(v[1]), float(v[2]))

    def _probe_image(self, world):
        """Return ``(inside, ijk, value)`` for a working-grid world point.

        ``ijk`` and ``value`` are ``None`` when the point is outside the volume.
        """
        series = self.state.image_series
        b = series.bounds
        sp = series.spacing
        tol = (0.5 * abs(sp[0]), 0.5 * abs(sp[1]), 0.5 * abs(sp[2]))
        inside = (b[0] - tol[0] <= world[0] <= b[1] + tol[0]
                  and b[2] - tol[1] <= world[1] <= b[3] + tol[1]
                  and b[4] - tol[2] <= world[2] <= b[5] + tol[2])
        if not inside:
            return False, None, None
        i, j, k = self.state.world_to_voxel(world)
        ex = series.extent
        img = self.state.current_image
        if self.state.array_name:
            img.GetPointData().SetActiveScalars(self.state.array_name)
        value = img.GetScalarComponentAsDouble(i + ex[0], j + ex[2], k + ex[4], 0)
        return True, (i, j, k), value

    def _resolve_pointer_on_slice(self) -> Optional[Tuple[SliceView, int, int]]:
        """Return (slice view, vtk display x, y) for the pointer, if known."""
        for vt in (ViewType.AXIAL, ViewType.SAGITTAL, ViewType.CORONAL):
            view = self.views[vt]
            if not isinstance(view, SliceView) or not view.isVisible():
                continue
            disp = view.display_xy_at_global_cursor()
            if disp is not None:
                return view, disp[0], disp[1]
        if self._last_cursor_slice is not None and self._last_cursor_display is not None:
            if self._last_cursor_slice.isVisible():
                return (self._last_cursor_slice,
                        self._last_cursor_display[0],
                        self._last_cursor_display[1])
        return None

    def _step_time(self, delta: int) -> None:
        if not self.state.image_series.is_temporal:
            return
        new = min(max(self.time_slider.value() + delta, 0),
                  self.time_slider.maximum())
        self.time_slider.setValue(new)  # triggers _on_time_changed

    def _add_point_at_cursor(self) -> None:
        """Add a landmark under the pointer on a slice panel (``.`` shortcut)."""
        resolved = self._resolve_pointer_on_slice()
        if resolved is None:
            QtWidgets.QMessageBox.information(
                self, "Add point",
                "Move the pointer over a slice panel first.")
            return
        view, x, y = resolved
        tid = self.state.current_time_id
        xyz = view.display_to_world(x, y)
        self.state.markups.add_point(tid, xyz)
        self.refresh_all()

    def _populate_controls(self) -> None:
        names = self.state.image_series.array_names
        self.side_panel.set_arrays(names, self.state.array_name)
        self.side_panel.set_mode(self.state.mode)
        self._sync_time_bar()
        cb = self.side_panel.periodic_cb
        cb.blockSignals(True)
        cb.setChecked(self.state.markups.periodic)
        cb.blockSignals(False)

    # ================================================================== events
    def showEvent(self, event):  # noqa: N802
        super().showEvent(event)
        if not self._views_started:
            for view in self.views.values():
                view.start()
            self._views_started = True
            self.refresh_all()

    def closeEvent(self, event):  # noqa: N802
        for view in self.views.values():
            view.close_view()
        super().closeEvent(event)

    # ============================================================== rendering
    def refresh_all(self) -> None:
        for view in self.views.values():
            view.refresh()

    # ============================================================== handlers
    def _on_time_changed(self, value: int) -> None:
        self.state.set_time_id(value)
        self.time_label.setText(self._time_label_text())
        self.refresh_all()

    def _on_array_changed(self, name: str) -> None:
        self.state.set_array(name)
        self.refresh_all()

    def _on_mode_changed(self, mode: MarkupMode) -> None:
        if mode is not MarkupMode.SPLINES:
            self.state.active_spline = None
        self.state.mode = mode
        logger.debug("Markup mode -> %s", mode)

    def _set_markup_mode(self, mode: MarkupMode) -> None:
        """Switch markup mode from the keyboard (keeps side-panel toggle in sync)."""
        self._on_mode_changed(mode)
        self.side_panel.set_mode(mode)

    def _on_show_markups(self, show: bool) -> None:
        self.state.show_markups = show
        self.refresh_all()

    def _on_show_crosshair(self, show: bool) -> None:
        self.state.show_crosshair = show
        self.refresh_all()

    def _on_reset_frame(self) -> None:
        self.state.reset_frame()
        self.refresh_all()

    def _on_periodic_changed(self, enabled: bool) -> None:
        self.state.markups.periodic = enabled
        self.refresh_all()

    def _on_window_level(self) -> None:
        """Window/level changed in one panel -> apply to every panel."""
        for view in self.views.values():
            view.apply_window_level()

    # ================================================================== help
    _HELP_HTML = """
<h2>TUI viewer &mdash; usage</h2>
<p>Four panels show the <b>axial</b>, <b>sagittal</b> and <b>coronal</b> slices
plus a <b>3D</b> view. Click a <i>Layout</i> button (or double-click a panel) to
maximise one view; <i>Grid (2&times;2)</i> restores all four.</p>

<h3>Mouse (any mode)</h3>
<ul>
<li><b>Mouse wheel</b> over a slice &mdash; scroll through slices.</li>
<li><b>3D panel</b> &mdash; left-drag rotates, wheel zooms, middle-drag pans.</li>
</ul>

<h3>Markup modes</h3>
<p>Pick a mode in the <i>Markup</i> panel (or with the keyboard). The left/right
mouse buttons on a slice panel do different things per mode:</p>
<table cellpadding="4">
<tr><th align="left">Mode</th><th align="left">Left button</th>
    <th align="left">Right button</th></tr>
<tr><td><b>Navigate</b></td>
    <td>Drag the crosshair centre to move all planes, or drag a crosshair line
        to rotate (double-oblique). Elsewhere, drag to adjust
        window/level (brightness&nbsp;/&nbsp;contrast).</td>
    <td>&ndash;</td></tr>
<tr><td><b>Add points</b></td>
    <td>Click to drop a landmark point.</td><td>&ndash;</td></tr>
<tr><td><b>Add splines</b></td>
    <td>Click to add spline control points. Use <i>New spline</i> to start a
        fresh spline and <i>Close spline</i> to close the loop.</td>
    <td>&ndash;</td></tr>
<tr><td><b>Paint</b></td>
    <td>Drag to paint with a 3D spherical brush (set <i>Brush</i> size and
        <i>Label</i>).</td>
    <td>Drag to erase.</td></tr>
<tr><td><b>Modify</b></td>
    <td>Drag the nearest handle to move it; click on a spline line to insert a
        control point. Editing an interpolated (cyan) frame turns it into an
        editable keyframe.</td>
    <td>Delete the nearest handle.</td></tr>
</table>

<h3>Time (4D data)</h3>
<p>Drag the <i>Time</i> slider to move between time steps. Manual markups are
keyframes; frames in between are interpolated (shown in cyan). Enable
<i>Periodic interpolation</i> for cyclic data (e.g. cardiac/respiratory).</p>

<h3>Keyboard shortcuts</h3>
<table cellpadding="4">
<tr><td><b>&larr;</b> / <b>&rarr;</b></td><td>Previous / next time step</td></tr>
<tr><td><b>N</b></td><td>Navigate mode</td></tr>
<tr><td><b>A</b></td><td>Add points mode</td></tr>
<tr><td><b>S</b></td><td>Add splines mode</td></tr>
<tr><td><b>P</b></td><td>Paint mode</td></tr>
<tr><td><b>M</b></td><td>Modify mode</td></tr>
<tr><td><b>.</b></td><td>Add a point under the pointer</td></tr>
<tr><td><b>U</b> or <b>Ctrl+Z</b></td><td>Undo last markup in this frame</td></tr>
<tr><td><b>Ctrl+S</b></td><td>Save markups</td></tr>
<tr><td><b>F1</b></td><td>Show this help</td></tr>
<tr><td><b>Q</b></td><td>Quit</td></tr>
</table>
"""

    def _show_help(self) -> None:
        """Show a small, scrollable window with usage help and shortcuts."""
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("TUI help")
        dlg.resize(560, 640)
        layout = QtWidgets.QVBoxLayout(dlg)
        browser = QtWidgets.QTextBrowser()
        browser.setOpenExternalLinks(True)
        browser.setHtml(self._HELP_HTML)
        layout.addWidget(browser)
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Close)
        buttons.rejected.connect(dlg.reject)
        buttons.accepted.connect(dlg.accept)
        layout.addWidget(buttons)
        dlg.exec_()

    def _maximise(self, view_type: Optional[ViewType]) -> None:
        self._apply_grid_layout(view_type)
        if self._views_started:
            QtCore.QTimer.singleShot(0, self.refresh_all)

    def _on_view_activated(self, view) -> None:
        self._maximise(view.view_type)

    def _on_point_picked(self, view, xyz: Tuple[float, float, float]) -> None:
        tid = self.state.current_time_id
        if self.state.mode is MarkupMode.POINTS:
            self.state.markups.add_point(tid, xyz)
        elif self.state.mode is MarkupMode.SPLINES:
            if self.state.active_spline is None:
                self.state.active_spline = self.state.markups.add_spline(tid)
            self.state.active_spline.control_points.append(tuple(xyz))
        self.refresh_all()

    def _on_paint(self, view, xyz: Tuple[float, float, float], erase: bool) -> None:
        if self.state.mode is not MarkupMode.PAINT:
            return
        tid = self.state.current_time_id
        mask = self.state.markups.paint_mask(tid, create=True)
        ijk = self.state.world_to_voxel(xyz)
        value = 0 if erase else self.state.paint_label
        # Painting (not erasing) is gated to voxels within the intensity limits.
        intensity = None if erase else self._current_intensity_view()
        limits = None if erase else (self.state.paint_lower, self.state.paint_upper)
        box = self._paint_sphere(mask, ijk, self.state.paint_radius, value,
                                 intensity=intensity, limits=limits)
        if box is None:
            return
        # Fast path: update only the painted sub-region and redraw only the
        # panel under the cursor; the other slice overlays are updated cheaply
        # (no render) and the 3D view is left to the stroke-end full refresh.
        for vt in (ViewType.AXIAL, ViewType.SAGITTAL, ViewType.CORONAL):
            v = self.views[vt]
            v.update_paint_region(mask, box, render=(v is view))

    @staticmethod
    def _paint_sphere(mask: np.ndarray, ijk, radius: int, value: int,
                      intensity: Optional[np.ndarray] = None,
                      limits: Optional[Tuple[float, float]] = None):
        """Paint a filled 3D ball of voxels centred on ``ijk``.

        A spherical brush spans several slices, so the stroke is visible (and
        editable) from all three orthogonal panels rather than a single plane.
        When ``intensity`` (an ``(nx,ny,nz)`` array aligned with ``mask``) and
        ``limits`` ``(lower, upper)`` are given, only voxels whose intensity lies
        within the limits are affected.  Returns the affected
        ``(i0,i1,j0,j1,k0,k1)`` box, or ``None`` if empty.
        """
        nx, ny, nz = mask.shape
        i, j, k = int(ijk[0]), int(ijk[1]), int(ijk[2])
        r = int(radius)
        i0, i1 = max(0, i - r), min(nx, i + r + 1)
        j0, j1 = max(0, j - r), min(ny, j + r + 1)
        k0, k1 = max(0, k - r), min(nz, k + r + 1)
        if i0 >= i1 or j0 >= j1 or k0 >= k1:
            return None
        ii = np.arange(i0, i1)[:, None, None]
        jj = np.arange(j0, j1)[None, :, None]
        kk = np.arange(k0, k1)[None, None, :]
        ball = (ii - i) ** 2 + (jj - j) ** 2 + (kk - k) ** 2 <= r ** 2
        if intensity is not None and limits is not None:
            lo, hi = limits
            sub = intensity[i0:i1, j0:j1, k0:k1]
            ball &= (sub >= lo) & (sub <= hi)
            if not ball.any():
                return None
        mask[i0:i1, j0:j1, k0:k1][ball] = value
        return (i0, i1, j0, j1, k0, k1)

    def _current_intensity_view(self) -> Optional[np.ndarray]:
        """Return the current display array as an ``(nx,ny,nz)`` numpy view.

        Aligned with the paint mask (same F-order shape, extent-based index 0),
        so a paint box slices straight into it.  Returns ``None`` if unavailable.
        """
        img = self.state.current_image
        pd = img.GetPointData()
        arr = pd.GetArray(self.state.array_name) if self.state.array_name else None
        if arr is None:
            arr = pd.GetScalars()
        if arr is None:
            return None
        np_arr = vtk_np.vtk_to_numpy(arr)  # no copy
        if np_arr.ndim > 1:  # multi-component -> gate on the first component
            np_arr = np_arr[:, 0]
        return np_arr.reshape(img.GetDimensions(), order="F")

    def _on_set_paint_limits(self) -> None:
        """Dialog to set the lower/upper intensity limits used when painting."""
        lo_range, hi_range = self.state.full_scalar_range()
        span = (hi_range - lo_range) or 1.0

        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Paint intensity limits")
        form = QtWidgets.QFormLayout(dlg)
        form.addRow(QtWidgets.QLabel(
            "Painting only affects voxels whose value is within these limits.\n"
            f"Display array '{self.state.array_name}' range: "
            f"{lo_range:0.2f} to {hi_range:0.2f}."))

        def _threshold_edit(value: float) -> QtWidgets.QLineEdit:
            sb = QtWidgets.QLineEdit()
            sb.setText(f"{value:0.2f}")
            return sb

        lower = _threshold_edit(self.state.paint_lower)
        upper = _threshold_edit(self.state.paint_upper)
        form.addRow("Lower limit", lower)
        form.addRow("Upper limit", upper)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
            | QtWidgets.QDialogButtonBox.RestoreDefaults)
        form.addRow(buttons)
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        buttons.button(QtWidgets.QDialogButtonBox.RestoreDefaults).clicked.connect(
            lambda: (lower.setText(f"{lo_range:.2f}"), upper.setText(f"{hi_range:.2f}")))

        if dlg.exec_() != QtWidgets.QDialog.Accepted:
            return
        try:
            lo = float(lower.text())
        except ValueError:
            print(f"WARNING: error reading lower threshold - reset to {lo_range}")
            lo = lo_range
        try:
            hi = float(upper.text())
        except ValueError:
            print(f"WARNING: error reading upper threshold - reset to {hi_range}")
            hi = hi_range
        self.state.paint_lower, self.state.paint_upper = min(lo, hi), max(lo, hi)

    def _on_action(self, action: str) -> None:
        tid = self.state.current_time_id
        m = self.state.markups
        if action == "new_spline":
            self.state.active_spline = None
        elif action == "close_spline":
            if self.state.active_spline is not None:
                self.state.active_spline.closed = True
                self.state.active_spline = None
        elif action == "undo":
            self._undo(tid)
        elif action == "clear_frame":
            m.clear_time(tid)
            self.state.active_spline = None
        elif action == "clear_all":
            self._clear_all_frames()
        elif action == "save":
            self.save_markups_helper()
        self.refresh_all()

    def _clear_all_frames(self) -> None:
        if self.state.markups.is_empty():
            return
        reply = QtWidgets.QMessageBox.question(
            self, "Clear all frames",
            "Remove all markups (points, splines and paint) from every time step?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No)
        if reply == QtWidgets.QMessageBox.Yes:
            self.state.markups.clear_all()
            self.state.active_spline = None

    def _undo(self, tid: int) -> None:
        m = self.state.markups
        if self.state.mode is MarkupMode.SPLINES:
            sp = self.state.active_spline
            if sp is not None and sp.control_points:
                sp.control_points.pop()
                if not sp.control_points:
                    m.remove_last_spline(tid)
                    self.state.active_spline = None
            else:
                m.remove_last_spline(tid)
        elif self.state.mode is MarkupMode.PAINT:
            m.clear_paint(tid)
        else:
            m.remove_last_point(tid)

    # ============================================================ custom API
    def customise(self) -> None:
        """Override to register custom buttons / behaviour. No-op by default."""

    def set_custom_button(self, row: int, col: int, label: str,
                          callback: Callable[[], None]) -> None:
        """Configure the custom button at (``row``, ``col``) in the 6x2 grid."""
        btn = self.side_panel.custom_buttons[row][col]
        btn.setText(label)
        btn.setEnabled(True)
        try:
            btn.clicked.disconnect()
        except TypeError:
            pass
        btn.clicked.connect(lambda _=False, cb=callback: self._run_callback(cb))
        self._custom_callbacks[(row, col)] = callback

    def set_custom_buttons(self, mapping: Dict[int, Tuple[str, Callable]]) -> None:
        """Set buttons by flat index 0..11 (row-major over the 6x2 grid)."""
        for index, (label, callback) in mapping.items():
            self.set_custom_button(index // CUSTOM_COLS, index % CUSTOM_COLS,
                                   label, callback)

    def _run_callback(self, callback: Callable[[], None]) -> None:
        try:
            callback()
        except Exception:  # noqa: BLE001 - never let a user callback kill the UI
            logger.exception("Custom button callback failed")
        self.refresh_all()

    # ====================================================== convenience props
    @property
    def image_series(self) -> ImageSeries:
        return self.state.image_series

    @property
    def markups(self) -> Markups:
        return self.state.markups

    @property
    def current_time_id(self) -> int:
        return self.state.current_time_id

    @property
    def current_array(self) -> str:
        return self.state.array_name

    @property
    def current_image(self):
        return self.state.current_image

    def refresh(self) -> None:
        self.refresh_all()

    def save_markups(self, out_dir: str, prefix: str = "markup",
                     include_interpolated: bool = True):
        return save_markups(self.markups, self.image_series, out_dir,
                            prefix=prefix, include_interpolated=include_interpolated)

    # ----------------------------------------------------------- file dialogs
    def _on_open(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Open image", self.WORK_DIR,
            "Image data (*.vti *.pvd *.nii *.nii.gz *.nrrd *.mha *.mhd)")
        if not path:
            return
        try:
            series = load_image_series(path)
        except Exception as exc:  # noqa: BLE001
            QtWidgets.QMessageBox.critical(self, "Open failed", str(exc))
            return
        self._reset_with_series(series)

    def _reset_with_series(self, series: ImageSeries) -> None:
        self.state = ViewerState(series)
        for view in self.views.values():
            view.state = self.state
            view.prepare_geometry() if isinstance(view, SliceView) else None
        self._populate_controls()  # configures the time slider via _sync_time_bar
        self.refresh_all()

    # -------------------------------------------------- markup load / export
    _POLYDATA_FILTER = "Polydata (*.vtp *.vtk *.vtu *.stl)"
    _LABELMAP_FILTER = "Label map (*.vti *.nii *.nii.gz *.nrrd *.mha *.mhd)"

    def _on_load_polydata(self) -> None:
        """Load points/splines from a polydata file into the current frame."""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Load markup polydata", self.WORK_DIR, self._POLYDATA_FILTER)
        if not path:
            return
        try:
            points, splines = load_markup_polydata(path, self.image_series)
        except Exception as exc:  # noqa: BLE001
            QtWidgets.QMessageBox.critical(self, "Load polydata failed", str(exc))
            return
        if not points and not splines:
            QtWidgets.QMessageBox.information(
                self, "Load polydata", "No points or splines found in the file.")
            return
        tid = self.state.current_time_id
        for xyz in points:
            self.state.markups.add_point(tid, xyz)
        for spline in splines:
            self.state.markups.add_spline(tid, spline)
        self.state.active_spline = None
        self.refresh_all()

    def _on_load_labelmap(self) -> None:
        """Load a label map into the current frame's paint mask (merged in)."""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Load labelmap", self.WORK_DIR, self._LABELMAP_FILTER)
        if not path:
            return
        try:
            mask = load_markup_labelmap(path, self.image_series)
        except Exception as exc:  # noqa: BLE001
            QtWidgets.QMessageBox.critical(self, "Load labelmap failed", str(exc))
            return
        self._merge_paint_mask(mask)

    def _on_load_surf2labelmap(self) -> None:
        """Voxelise a closed surface into the current frame's paint mask."""
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Load surface to voxelise", self.WORK_DIR, self._POLYDATA_FILTER)
        if not path:
            return
        try:
            mask = load_surface_as_labelmap(
                path, self.image_series, self.state.current_time_id,
                fill_value=self.state.paint_label)
        except Exception as exc:  # noqa: BLE001
            QtWidgets.QMessageBox.critical(
                self, "Load surf2labelmap failed", str(exc))
            return
        self._merge_paint_mask(mask)

    def _merge_paint_mask(self, mask: np.ndarray) -> None:
        """Merge a loaded ``(nx,ny,nz)`` mask into the current paint mask."""
        if not mask.any():
            QtWidgets.QMessageBox.information(
                self, "Load labelmap", "The label map is empty (no set voxels).")
            return
        tid = self.state.current_time_id
        existing = self.state.markups.paint_mask(tid, create=True)
        set_voxels = mask > 0
        existing[set_voxels] = mask[set_voxels]
        self.refresh_all()

    def _on_export_polydata(self) -> None:
        self._export_markups(("points", "splines"), "Export polydata",
                             self._POLYDATA_FILTER)

    def _on_export_labelmap(self) -> None:
        self._export_markups(("paint",), "Export labelmap",
                             self._LABELMAP_FILTER)

    def _export_markups(self, kinds: Tuple[str, ...], title: str,
                        file_filter: str) -> None:
        m = self.state.markups
        present = {
            "points": bool(m.point_keyframes()),
            "splines": bool(m.spline_keyframes()),
            "paint": bool(m.paint_keyframes()),
        }
        nonempty = [k for k in kinds if present[k]]
        if not nonempty:
            QtWidgets.QMessageBox.information(
                self, title, "There are no markups of this type to export.")
            return
        # Ask for a full save path via the file selector, then split it into the
        # (out_dir, prefix) pair the underlying save logic expects.
        start = os.path.join(self.WORK_DIR, "markup")
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, title, start, file_filter)
        if not path:
            return
        out_dir = os.path.dirname(path) or "."
        prefix = os.path.basename(path)
        prefix = os.path.splitext(prefix)[0]  # drop the chosen extension
        if prefix.endswith(".nii"):  # handle the .nii.gz double extension
            prefix = prefix[:-4]
        if not prefix:
            QtWidgets.QMessageBox.warning(self, title, "Please choose a filename.")
            return
        # Use the chosen name verbatim (no "_points"/"_paint" suffix). Points and
        # splines share the .vtp extension, so only drop the suffix when a single
        # output file will be written (otherwise the two would collide).
        kind_suffix = len(nonempty) > 1
        try:
            files = save_markups(self.markups, self.image_series, out_dir,
                                 prefix=prefix, kinds=kinds,
                                 kind_suffix=kind_suffix)
        except Exception as exc:  # noqa: BLE001
            QtWidgets.QMessageBox.critical(self, "Export failed", str(exc))
            return
        QtWidgets.QMessageBox.information(
            self, title, f"Wrote {len(files)} file(s) to {out_dir}.")


    def save_markups_helper(self, filename: str = None) -> None:
        if filename and os.sep in filename:
            out_dir = os.path.dirname(filename)
            filename = os.path.basename(filename)
        else:
            out_dir = self.WORK_DIR
            if filename is None:
                filename, ok = QtWidgets.QInputDialog.getText(
                    self, "Save markups", "Filename:")
                if not ok or not filename.strip():
                    return
        try:
            files = self.save_markups(out_dir, prefix=filename.strip())
        except Exception as exc:  # noqa: BLE001
            QtWidgets.QMessageBox.critical(self, "Save failed", str(exc))
            return


# ----------------------------------------------------------------------------
def _title_for(data) -> str:
    if isinstance(data, str):
        return f"TUI - {os.path.basename(os.path.expanduser(data))}"
    return "TUI"


def launch(data, viewer_class=ViewerApp, array: Optional[str] = None,
           title: Optional[str] = None, argv=None, **viewer_kwargs) -> int:
    """Run ``viewer_class`` on ``data`` until the window is closed.

    ``data`` may be a file path, DICOM directory, :class:`vtk.vtkImageData`,
    a ``{time: image}`` dict, a list of volumes, or an :class:`ImageSeries`
    (see :func:`~tui.io.as_image_series`).  Extra keyword arguments are
    forwarded to the viewer constructor::

        launch(subject.MIPVTI, viewer_class=MyViewer, subject=subject)
        launch(vtk_dict, viewer_class=MyViewer)
    """
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(argv or sys.argv)
    viewer = viewer_class(
        data, title=title or _title_for(data), **viewer_kwargs)
    if array:
        viewer.state.set_array(array)
    viewer.show()
    return app.exec_()


def launch_viewer(data, viewer_class=ViewerApp, title: str = "TUI",
                  array: Optional[str] = None, argv=None,
                  **viewer_kwargs) -> int:
    """Alias for :func:`launch` when the caller already holds in-memory data.

    Accepts the same ``data`` types as :func:`launch` / :func:`as_image_series`.
    """
    return launch(data, viewer_class=viewer_class, title=title, array=array,
                  argv=argv, **viewer_kwargs)
