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

from .core.enums import MarkupMode, ViewType
from .core.image_series import ImageSeries
from .core.markups import Markups, Spline
from .io import load_image_series, save_markups
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
        
        if work_dir is not None:
            self.WORK_DIR = work_dir
        else:
            self.WORK_DIR = os.environ.get("TUI_WORK_DIR", None)

        self.setWindowTitle(title)
        self.resize(1400, 900)
        self._build_ui()
        self._connect_signals()
        self._install_shortcuts()
        self._populate_controls()
        # User extension hook - safe to register custom buttons here.
        self.customise()

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

    def _on_slice_cursor(self, view: SliceView, x: int, y: int) -> None:
        self._last_cursor_slice = view
        self._last_cursor_display = (x, y)

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
        box = self._paint_sphere(mask, ijk, self.state.paint_radius, value)
        if box is None:
            return
        # Fast path: update only the painted sub-region and redraw only the
        # panel under the cursor; the other slice overlays are updated cheaply
        # (no render) and the 3D view is left to the stroke-end full refresh.
        for vt in (ViewType.AXIAL, ViewType.SAGITTAL, ViewType.CORONAL):
            v = self.views[vt]
            v.update_paint_region(mask, box, render=(v is view))

    @staticmethod
    def _paint_sphere(mask: np.ndarray, ijk, radius: int, value: int):
        """Paint a filled 3D ball of voxels centred on ``ijk``.

        A spherical brush spans several slices, so the stroke is visible (and
        editable) from all three orthogonal panels rather than a single plane.
        Returns the affected ``(i0,i1,j0,j1,k0,k1)`` box, or ``None`` if empty.
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
        mask[i0:i1, j0:j1, k0:k1][ball] = value
        return (i0, i1, j0, j1, k0, k1)

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
            self, "Open image", "", "Image data (*.vti *.pvd *.nii *.nii.gz *.nrrd *.mha *.mhd)")
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


    def save_markups_helper(self, filename: str=None) -> None:
        if os.sep in filename:
            out_dir = os.path.dirname(filename)
            filename = os.path.basename(filename)
        else:
            if self.WORK_DIR is None:
                if filename is None:
                    full_filename = QtWidgets.QFileDialog.getSaveFileName(self, "Save markups to")
                    if not full_filename:
                        return
                    filename = os.path.basename(full_filename)
                else:
                    out_dir = QtWidgets.QFileDialog.getExistingDirectory(self, "Save markups to")
                    if not out_dir:
                        return
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
