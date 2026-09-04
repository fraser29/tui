"""A single 2D orthogonal/oblique slice panel (axial, sagittal or coronal).

Slicing is performed with :class:`vtk.vtkImageResliceMapper` driven by the
shared reslice frame in :class:`~tui.state.ViewerState`, so the same panel
renders both axis-aligned and double-oblique planes.  A crosshair shows where
the other two planes intersect this one and can be dragged to translate or
rotate the frame (planes stay mutually perpendicular).
"""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

import numpy as np
import vtk
from vtk.util import numpy_support as vtk_np
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
from PyQt5 import QtCore, QtWidgets

from ..core.enums import Orientation, ViewType
from ..state import ViewerState
from .interactor_styles import SliceInteractorStyle

logger = logging.getLogger(__name__)

_COL_MANUAL_POINT = (1.0, 0.85, 0.1)
_COL_INTERP_POINT = (0.2, 0.9, 0.9)
_COL_MANUAL_SPLINE = (1.0, 0.55, 0.0)
_COL_INTERP_SPLINE = (0.2, 0.9, 0.9)
_COL_HANDLE = (1.0, 0.2, 0.6)

# Marker sizes in *screen pixels* (constant under zoom, rendered as spheres).
_POINT_PX = 6.0
_HANDLE_PX = 5.0

# Crosshair colour per plane normal axis (0=sagittal,1=coronal,2=axial).
_AXIS_COLOUR = {0: (1.0, 0.35, 0.35), 1: (0.35, 1.0, 0.35), 2: (0.4, 0.6, 1.0)}

_GRAB_PX = 12.0   # pixel radius to grab the centre
_LINE_PX = 8.0    # pixel distance to grab a crosshair line


class SliceView(QtWidgets.QFrame):
    """Renders one slice (possibly oblique) plus paint, markup and crosshair."""

    sigPointPicked = QtCore.pyqtSignal(object, tuple)
    sigPaint = QtCore.pyqtSignal(object, tuple, bool)
    sigFrameChanged = QtCore.pyqtSignal()       # frame or markup edited -> refresh all
    sigResliceChanged = QtCore.pyqtSignal()     # slice/crosshair moved -> geometry only
    sigWindowLevel = QtCore.pyqtSignal()        # window/level edited -> sync all views
    sigViewActivated = QtCore.pyqtSignal(object)

    def __init__(self, view_type: ViewType, state: ViewerState, parent=None):
        super().__init__(parent)
        assert view_type.is_slice
        self.view_type = view_type
        self.orientation: Orientation = view_type.orientation
        self.state = state
        self._grabbed = None  # modify-mode handle reference
        self._wl_anchor = None  # (x, y, window, level) at window/level drag start
        self._last_cursor_display: Optional[Tuple[int, int]] = None

        self.setFrameStyle(QtWidgets.QFrame.Box | QtWidgets.QFrame.Plain)
        self.setLineWidth(1)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)

        self._vtk_widget = QVTKRenderWindowInteractor(self)
        layout.addWidget(self._vtk_widget)
        self._render_window = self._vtk_widget.GetRenderWindow()
        self._interactor = self._render_window.GetInteractor()

        self.renderer = vtk.vtkRenderer()
        self.renderer.SetBackground(0.05, 0.05, 0.08)
        self._render_window.AddRenderer(self.renderer)

        self._style = SliceInteractorStyle(self)
        self._interactor.SetInteractorStyle(self._style)

        self._plane = vtk.vtkPlane()
        self._build_pipeline()
        self._camera_initialised = False
        self.prepare_geometry()
        self._base_mapper.SetInputData(self.state.current_image)

    # ------------------------------------------------------------- lifecycle
    def start(self) -> None:
        self._interactor.Initialize()

    def close_view(self) -> None:
        self._vtk_widget.close()

    # ------------------------------------------------------------- pipeline
    def _build_pipeline(self) -> None:
        self._base_mapper = vtk.vtkImageResliceMapper()
        self._base_mapper.SetSlicePlane(self._plane)
        self._base_mapper.SliceFacesCameraOff()
        self._base_mapper.SliceAtFocalPointOff()
        self._base_slice = vtk.vtkImageSlice()
        self._base_slice.SetMapper(self._base_mapper)
        self._base_slice.GetProperty().SetLayerNumber(0)
        self._base_slice.GetProperty().SetInterpolationTypeToLinear()

        self._paint_mapper = vtk.vtkImageResliceMapper()
        self._paint_mapper.SetSlicePlane(self._plane)
        self._paint_mapper.SliceFacesCameraOff()
        self._paint_mapper.SliceAtFocalPointOff()
        self._paint_slice = vtk.vtkImageSlice()
        self._paint_slice.SetMapper(self._paint_mapper)
        self._paint_slice.GetProperty().SetLayerNumber(1)
        self._paint_slice.GetProperty().SetInterpolationTypeToNearest()
        self._paint_slice.GetProperty().SetLookupTable(self._make_label_lut())
        self._paint_slice.GetProperty().UseLookupTableScalarRangeOn()
        self._paint_slice.GetProperty().SetOpacity(0.45)
        self._paint_slice.VisibilityOff()

        self._stack = vtk.vtkImageStack()
        self._stack.AddImage(self._base_slice)
        self._stack.AddImage(self._paint_slice)
        self._stack.SetActiveLayer(0)
        self.renderer.AddViewProp(self._stack)

        self._overlay_img: Optional[vtk.vtkImageData] = None
        self._overlay_buf: Optional[np.ndarray] = None
        self._overlay_view: Optional[np.ndarray] = None
        self._overlay_key = None  # (id(mask), paint_revision) last uploaded

        # Markup actors.
        self._point_actor, self._point_poly = self._make_point_actor(
            _POINT_PX, _COL_MANUAL_POINT)
        self._spline_manual_actor, self._spline_manual_poly = self._make_line_actor(2.0)
        self._spline_interp_actor, self._spline_interp_poly = self._make_line_actor(2.0)
        self._handle_actor, self._handle_poly = self._make_point_actor(
            _HANDLE_PX, _COL_HANDLE)
        for a in (self._point_actor, self._spline_manual_actor,
                  self._spline_interp_actor, self._handle_actor):
            self.renderer.AddActor(a)

        # Crosshair line actors.
        self._cross_u = self._make_simple_line()
        self._cross_v = self._make_simple_line()
        self.renderer.AddActor(self._cross_u)
        self.renderer.AddActor(self._cross_v)

        self._annotation = vtk.vtkCornerAnnotation()
        self._annotation.SetLinearFontScaleFactor(2)
        self._annotation.SetMaximumFontSize(14)
        self._annotation.GetTextProperty().SetColor(0.9, 0.9, 0.5)
        self.renderer.AddViewProp(self._annotation)

    @staticmethod
    def _make_label_lut() -> vtk.vtkLookupTable:
        lut = vtk.vtkLookupTable()
        lut.SetNumberOfTableValues(16)
        lut.SetTableRange(0, 15)
        lut.Build()
        palette = [
            (0, 0, 0, 0),
            (0.90, 0.10, 0.10, 1.0), (0.10, 0.70, 0.90, 1.0),
            (0.20, 0.85, 0.20, 1.0), (0.95, 0.75, 0.10, 1.0),
            (0.70, 0.30, 0.90, 1.0), (0.95, 0.45, 0.10, 1.0),
        ]
        for i in range(16):
            lut.SetTableValue(*([i] + list(palette[i % len(palette)])))
        lut.SetTableValue(0, 0, 0, 0, 0)
        return lut

    def _make_point_actor(self, px: float, colour) -> Tuple[vtk.vtkActor, vtk.vtkPolyData]:
        """Marker actor drawn as screen-sized spheres (constant under zoom)."""
        poly = vtk.vtkPolyData()
        poly.SetPoints(vtk.vtkPoints())
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputData(poly)
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        prop = actor.GetProperty()
        prop.SetColor(*colour)
        prop.SetPointSize(px)
        prop.RenderPointsAsSpheresOn()
        return actor, poly

    def _make_line_actor(self, width: float) -> Tuple[vtk.vtkActor, vtk.vtkPolyData]:
        poly = vtk.vtkPolyData()
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputData(poly)
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetLineWidth(width)
        return actor, poly

    def _make_simple_line(self) -> vtk.vtkActor:
        src = vtk.vtkLineSource()
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(src.GetOutputPort())
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetLineWidth(1.5)
        actor.GetProperty().SetOpacity(0.8)
        actor._source = src  # keep a handle to update endpoints
        return actor

    # --------------------------------------------------------------- geometry
    def prepare_geometry(self) -> None:
        img = self.state.image_series.reference
        dims = img.GetDimensions()
        n = dims[0] * dims[1] * dims[2]
        self._overlay_img = vtk.vtkImageData()
        # Match the source extent (not just dimensions) so a non-zero starting
        # extent keeps the paint overlay aligned with the anatomy.
        self._overlay_img.SetExtent(img.GetExtent())
        self._overlay_img.SetSpacing(img.GetSpacing())
        self._overlay_img.SetOrigin(img.GetOrigin())
        buf = np.zeros(n, dtype=np.uint8)
        varr = vtk_np.numpy_to_vtk(buf, deep=1)
        varr.SetName("paint")
        self._overlay_img.GetPointData().SetScalars(varr)
        self._overlay_buf = vtk_np.vtk_to_numpy(self._overlay_img.GetPointData().GetScalars())
        # (nx, ny, nz) Fortran view onto the same buffer, aligned with the paint
        # mask so a painted sub-region can be copied in without a full O(N) pass.
        self._overlay_view = self._overlay_buf.reshape(dims, order="F")
        self._overlay_key = None
        self._paint_mapper.SetInputData(self._overlay_img)
        self._camera_initialised = False

    def _update_plane(self) -> None:
        self._plane.SetOrigin(*self.state.center)
        self._plane.SetNormal(*self.state.normal_for(self.orientation))

    def _init_camera(self) -> None:
        cam = self.renderer.GetActiveCamera()
        cam.ParallelProjectionOn()
        c = self.state.image_series.center
        cam.SetFocalPoint(*c)
        b = self.state.image_series.bounds
        dist = max(b[1] - b[0], b[3] - b[2], b[5] - b[4]) * 2.0
        n = self.state.normal_for(self.orientation)
        cam.SetPosition(c[0] + n[0] * dist, c[1] + n[1] * dist, c[2] + n[2] * dist)
        cam.SetViewUp(*self.state.camera_up_for(self.orientation))
        self.renderer.ResetCamera()
        self._camera_initialised = True

    def _orient_camera(self) -> None:
        """Re-aim the camera along the current normal, preserving zoom."""
        cam = self.renderer.GetActiveCamera()
        fp = np.asarray(cam.GetFocalPoint())
        dist = cam.GetDistance()
        n = self.state.normal_for(self.orientation)
        cam.SetPosition(*(fp + n * dist))
        cam.SetViewUp(*self.state.camera_up_for(self.orientation))

    # ----------------------------------------------------------------- render
    def refresh(self) -> None:
        if self._overlay_buf is None:
            self.prepare_geometry()
        self._update_plane()
        self._refresh_image()
        self._refresh_paint()
        self._finish_refresh()

    def refresh_reslice(self) -> None:
        """Re-render after the reslice frame moved (scroll / crosshair).

        The paint overlay volume is already on the mapper; re-uploading it and
        calling ``Modified`` is what made slicing crawl once a labelmap exists.
        """
        self._update_plane()
        self._finish_refresh()

    def _finish_refresh(self) -> None:
        self._refresh_markups()
        self._refresh_crosshair()
        self._refresh_annotation()
        if not self._camera_initialised:
            self._init_camera()
        else:
            self._orient_camera()
        self.renderer.ResetCameraClippingRange()
        self._render_window.Render()

    def _refresh_image(self) -> None:
        img = self.state.current_image
        if self.state.array_name:
            img.GetPointData().SetActiveScalars(self.state.array_name)
        self._base_mapper.SetInputData(img)
        self._apply_window_level_prop()

    def _apply_window_level_prop(self) -> None:
        prop = self._base_slice.GetProperty()
        prop.SetColorWindow(self.state.window)
        prop.SetColorLevel(self.state.level)

    def apply_window_level(self) -> None:
        """Re-apply the shared window/level and redraw (no geometry rebuild)."""
        self._apply_window_level_prop()
        self._render_window.Render()

    def _refresh_paint(self) -> None:
        if not self.state.show_markups:
            self._paint_slice.VisibilityOff()
            return
        mask = self.state.markups.effective_paint(self.state.current_time_id)
        if mask is None:
            if self._overlay_key is not None:
                self._overlay_buf[:] = 0
                self._overlay_img.Modified()
                self._overlay_key = None
            self._paint_slice.VisibilityOff()
            return
        key = (id(mask), self.state.markups.paint_revision)
        if key == self._overlay_key:
            self._paint_slice.VisibilityOn()
            return
        # Full upload: only when the mask object/revision actually changed.
        self._overlay_buf[:] = np.ascontiguousarray(mask.ravel(order="F"))
        self._overlay_img.Modified()
        self._overlay_key = key
        self._paint_slice.SetVisibility(bool(mask.any()))

    def _refresh_markups(self) -> None:
        show = self.state.show_markups
        tid = self.state.current_time_id
        n = self.state.normal_for(self.orientation)
        c = self.state.center
        tol = 1.5 * max(self.state.image_series.spacing)

        def near_plane(p):
            return abs(float(np.dot(np.asarray(p) - c, n))) <= tol

        ps = self.state.markups.effective_points(tid) if show else None
        pts = [p for p in ps.points if near_plane(p)] if ps else []
        self._set_glyph_points(self._point_poly, pts)
        self._point_actor.GetProperty().SetColor(
            *(_COL_MANUAL_POINT if (ps and ps.is_manual) else _COL_INTERP_POINT))
        self._point_actor.SetVisibility(bool(pts))

        manual_curves, interp_curves, handles = [], [], []
        if show:
            for s in self.state.markups.effective_splines(tid):
                if len(s.control_points) >= 2:
                    (manual_curves if s.is_manual else interp_curves).append(
                        s.sampled(150))
                if s.is_manual:
                    handles.extend(p for p in s.control_points if near_plane(p))
        self._set_lines(self._spline_manual_poly, manual_curves)
        self._set_lines(self._spline_interp_poly, interp_curves)
        self._spline_manual_actor.GetProperty().SetColor(*_COL_MANUAL_SPLINE)
        self._spline_interp_actor.GetProperty().SetColor(*_COL_INTERP_SPLINE)
        self._spline_manual_actor.SetVisibility(bool(manual_curves))
        self._spline_interp_actor.SetVisibility(bool(interp_curves))

        self._set_glyph_points(self._handle_poly, handles)
        self._handle_actor.GetProperty().SetColor(*_COL_HANDLE)
        self._handle_actor.SetVisibility(bool(handles))

    def _refresh_crosshair(self) -> None:
        if not self.state.show_crosshair:
            self._cross_u.VisibilityOff()
            self._cross_v.VisibilityOff()
            return
        c = self.state.center
        u, v = self.state.inplane_for(self.orientation)
        b = self.state.image_series.bounds
        L = max(b[1] - b[0], b[3] - b[2], b[5] - b[4])
        others = [i for i in range(3) if i != self.orientation.axis]
        # u-line represents the plane whose normal is the OTHER in-plane axis.
        self._set_cross(self._cross_u, c, u, L, _AXIS_COLOUR[others[1]])
        self._set_cross(self._cross_v, c, v, L, _AXIS_COLOUR[others[0]])
        self._cross_u.VisibilityOn()
        self._cross_v.VisibilityOn()

    @staticmethod
    def _set_cross(actor, center, direction, length, colour) -> None:
        src = actor._source
        p0 = np.asarray(center) - direction * length
        p1 = np.asarray(center) + direction * length
        src.SetPoint1(*p0)
        src.SetPoint2(*p1)
        actor.GetProperty().SetColor(*colour)

    def _refresh_annotation(self) -> None:
        if self.state.is_axis_aligned():
            idx = self.state.slice_for(self.orientation)
            lo, hi = self.state.image_series.slice_range(self.orientation.axis)
            txt = f"{self.orientation.label}  {idx}/{hi}"
        else:
            txt = f"{self.orientation.label}  (oblique)"
        if self.state.image_series.is_temporal:
            txt += f"   t={self.state.current_time_id}"
        self._annotation.SetText(2, txt)

    @staticmethod
    def _set_glyph_points(poly, points) -> None:
        vpts = vtk.vtkPoints()
        verts = vtk.vtkCellArray()
        for p in points:
            pid = vpts.InsertNextPoint(p[0], p[1], p[2])
            verts.InsertNextCell(1)
            verts.InsertCellPoint(pid)
        poly.SetPoints(vpts)
        poly.SetVerts(verts)
        poly.Modified()

    @staticmethod
    def _set_lines(poly, curves) -> None:
        vpts = vtk.vtkPoints()
        cells = vtk.vtkCellArray()
        for curve in curves:
            line = vtk.vtkPolyLine()
            line.GetPointIds().SetNumberOfIds(len(curve))
            for i, p in enumerate(curve):
                pid = vpts.InsertNextPoint(p[0], p[1], p[2])
                line.GetPointIds().SetId(i, pid)
            cells.InsertNextCell(line)
        poly.SetPoints(vpts)
        poly.SetLines(cells)
        poly.Modified()

    def note_cursor_display(self, x: int, y: int) -> None:
        """Remember the latest VTK display position (from the interactor)."""
        self._last_cursor_display = (int(x), int(y))
        tracker = getattr(self, "_cursor_tracker", None)
        if tracker is not None:
            tracker(self, int(x), int(y))

    def display_xy_at_global_cursor(self) -> Optional[Tuple[int, int]]:
        """Map the OS pointer to VTK display pixels when over this panel."""
        from PyQt5 import QtGui

        local = self._vtk_widget.mapFromGlobal(QtGui.QCursor.pos())
        if not self._vtk_widget.rect().contains(local):
            return None
        return self._qt_local_to_display(local.x(), local.y())

    def _qt_local_to_display(self, local_x: int, local_y: int) -> Tuple[int, int]:
        rw = self._render_window.GetSize()
        w, h = self._vtk_widget.width(), self._vtk_widget.height()
        if w < 1 or h < 1:
            return 0, 0
        x = int(local_x * rw[0] / w)
        y = int((h - 1 - local_y) * rw[1] / h)
        return x, y

    # ------------------------------------------------------- coordinate maps
    def display_to_world(self, x: int, y: int) -> Tuple[float, float, float]:
        """Display pixel -> world point projected onto the current slice plane."""
        self.renderer.SetDisplayPoint(float(x), float(y), 0.0)
        self.renderer.DisplayToWorld()
        w = list(self.renderer.GetWorldPoint())
        if w[3] != 0.0:
            w = [w[0] / w[3], w[1] / w[3], w[2] / w[3], 1.0]
        p = np.array(w[:3])
        n = self.state.normal_for(self.orientation)
        c = self.state.center
        p = p - np.dot(p - c, n) * n
        return tuple(float(v) for v in p)

    def _world_to_display(self, world) -> Tuple[float, float]:
        self.renderer.SetWorldPoint(world[0], world[1], world[2], 1.0)
        self.renderer.WorldToDisplay()
        d = self.renderer.GetDisplayPoint()
        return d[0], d[1]

    # ----------------------------------------------------------- interaction
    def handle_pick(self, *xyz) -> None:
        self.sigPointPicked.emit(self, tuple(xyz))

    def handle_paint(self, *args, erase: bool = False) -> None:
        self.sigPaint.emit(self, tuple(args), erase)

    def update_paint_region(self, mask: np.ndarray, box, render: bool = True) -> None:
        """Fast path during a paint drag: copy only the changed sub-box of the
        mask into the overlay and (optionally) redraw just this panel.

        Avoids the full-volume copy and four-panel refresh of ``refresh_all``,
        so painting tracks the cursor live.  ``box`` is ``(i0,i1,j0,j1,k0,k1)``.
        """
        if self._overlay_view is None:
            return
        i0, i1, j0, j1, k0, k1 = box
        self._overlay_view[i0:i1, j0:j1, k0:k1] = mask[i0:i1, j0:j1, k0:k1]
        self._overlay_img.Modified()
        self._overlay_key = (id(mask), self.state.markups.paint_revision)
        self._paint_slice.SetVisibility(self.state.show_markups)
        if render:
            self._render_window.Render()

    def end_paint_stroke(self) -> None:
        """Stroke finished -> full sync so the 3D and other panels catch up."""
        self.sigFrameChanged.emit()

    def step_slice(self, delta: int) -> None:
        self.state.step_along_normal(self.orientation, delta)
        self.sigResliceChanged.emit()

    # --- window / level --------------------------------------------------- #
    def window_level_begin(self, x: int, y: int) -> None:
        self._wl_anchor = (x, y, self.state.window, self.state.level)

    def window_level_drag(self, x: int, y: int) -> None:
        if self._wl_anchor is None:
            return
        x0, y0, win0, lev0 = self._wl_anchor
        lo, hi = self.state.image_series.scalar_range(self.state.array_name)
        rng = max(hi - lo, 1e-6)
        size = self._render_window.GetSize()
        w = max(int(size[0]), 1)
        h = max(int(size[1]), 1)
        # Absolute mapping from the drag start: horizontal = window,
        # vertical = level.  A full-screen drag spans the scalar range.
        self.state.window = max(rng * 1e-3, win0 + (x - x0) / w * rng)
        self.state.level = lev0 + (y - y0) / h * rng
        self.sigWindowLevel.emit()

    # --- crosshair -------------------------------------------------------- #
    def crosshair_grab(self, x: int, y: int):
        cd = self._world_to_display(self.state.center)
        if _dist2((x, y), cd) <= _GRAB_PX ** 2:
            return "center"
        u, v = self.state.inplane_for(self.orientation)
        c = self.state.center
        b = self.state.image_series.bounds
        L = max(b[1] - b[0], b[3] - b[2], b[5] - b[4])
        best, token = _LINE_PX ** 2, None
        for axis_vec, name in ((u, "u"), (v, "v")):
            p0 = self._world_to_display(c - axis_vec * L)
            p1 = self._world_to_display(c + axis_vec * L)
            d2 = _point_seg_dist2((x, y), p0, p1)
            if d2 < best:
                best, token = d2, name
        return token

    def crosshair_drag(self, x: int, y: int, token) -> None:
        world = np.array(self.display_to_world(x, y))
        c = self.state.center
        if token == "center":
            self.state.set_center(world)
        else:
            u, v = self.state.inplane_for(self.orientation)
            axis_vec = u if token == "u" else v
            d = world - c
            if np.linalg.norm(d) < 1e-9:
                return
            d = d / np.linalg.norm(d)
            n = self.state.normal_for(self.orientation)
            ang = np.arctan2(float(np.dot(np.cross(axis_vec, d), n)),
                             float(np.dot(axis_vec, d)))
            self.state.rotate_about(self.orientation, ang)
        self.sigResliceChanged.emit()

    # --- modify handles --------------------------------------------------- #
    def _near_plane_fn(self):
        n = self.state.normal_for(self.orientation)
        c = self.state.center
        tol = 1.5 * max(self.state.image_series.spacing)
        return lambda p: abs(float(np.dot(np.asarray(p) - c, n))) <= tol

    def _effective_handles(self):
        """Handles on the current plane addressed by container index.

        Uses the *effective* (manual-or-interpolated) markups so interpolated
        frames can be hit-tested before being promoted to a keyframe.  Each item
        is ``(kind, container_index, handle_index, world)`` where
        ``container_index`` is ``-1`` for the point set or the spline's index.
        """
        tid = self.state.current_time_id
        near = self._near_plane_fn()
        out = []
        ps = self.state.markups.effective_points(tid)
        out += [("point", -1, i, p) for i, p in enumerate(ps.points) if near(p)]
        for si, s in enumerate(self.state.markups.effective_splines(tid)):
            out += [("spline", si, i, p)
                    for i, p in enumerate(s.control_points) if near(p)]
        return out

    def _manual_container(self, kind: str, container_index: int):
        tid = self.state.current_time_id
        if kind == "point":
            return self.state.markups.manual_points(tid)
        splines = self.state.markups.manual_splines(tid)
        return splines[container_index] if container_index < len(splines) else None

    def _maybe_promote_frame(self) -> None:
        """Turn an interpolated frame into an editable keyframe before editing."""
        if self.state.markups.promote_to_manual(self.state.current_time_id):
            self.sigFrameChanged.emit()

    def modify_grab(self, x: int, y: int) -> bool:
        best, found = 14.0 ** 2, None
        for kind, ci, hi, world in self._effective_handles():
            d2 = _dist2((x, y), self._world_to_display(world))
            if d2 < best:
                best, found = d2, (kind, ci, hi)
        if found is None:
            self._grabbed = None
            return False
        # Confirmed hit -> promote (if needed) and bind to the manual object.
        self._maybe_promote_frame()
        kind, ci, hi = found
        obj = self._manual_container(kind, ci)
        if obj is None:
            self._grabbed = None
            return False
        self._grabbed = (kind, obj, hi)
        return True

    def modify_insert(self, x: int, y: int) -> bool:
        """Insert a new control point into the nearest spline at the click."""
        tid = self.state.current_time_id
        gate = 10.0 ** 2
        chosen = None  # (container_index, insert_index, curve_dist)
        for si, s in enumerate(self.state.markups.effective_splines(tid)):
            cps = s.control_points
            if len(cps) < 2:
                continue
            curve_disp = [self._world_to_display(p) for p in s.sampled(150)]
            dmin = min((_dist2((x, y), p) for p in curve_disp), default=1e18)
            if dmin > gate:
                continue
            m = len(cps)
            seg_d, seg_i = 1e18, 0
            for i in (range(m) if s.closed else range(m - 1)):
                a = self._world_to_display(cps[i])
                b = self._world_to_display(cps[(i + 1) % m])
                d = _point_seg_dist2((x, y), a, b)
                if d < seg_d:
                    seg_d, seg_i = d, i
            if chosen is None or dmin < chosen[2]:
                chosen = (si, seg_i + 1, dmin)
        if chosen is None:
            return False
        self._maybe_promote_frame()
        ci, idx, _ = chosen
        spline = self._manual_container("spline", ci)
        if spline is None:
            return False
        spline.control_points.insert(idx, tuple(self.display_to_world(x, y)))
        self._grabbed = ("spline", spline, idx)  # so the new node drags at once
        self.sigFrameChanged.emit()
        return True

    def modify_delete(self, x: int, y: int) -> bool:
        """Delete the nearest control point / point under the cursor."""
        best, found = 14.0 ** 2, None
        for kind, ci, hi, world in self._effective_handles():
            d2 = _dist2((x, y), self._world_to_display(world))
            if d2 < best:
                best, found = d2, (kind, ci, hi)
        if found is None:
            return False
        self._maybe_promote_frame()
        kind, ci, hi = found
        tid = self.state.current_time_id
        obj = self._manual_container(kind, ci)
        if obj is None:
            return False
        if kind == "point":
            if hi < len(obj.points):
                del obj.points[hi]
            if not obj.points:
                self.state.markups.clear_points(tid)
        else:
            if hi < len(obj.control_points):
                del obj.control_points[hi]
            if not obj.control_points:
                splines = self.state.markups.manual_splines(tid)
                if obj in splines:
                    splines.remove(obj)
                if not splines:
                    self.state.markups.clear_splines(tid)
        self._grabbed = None
        self.sigFrameChanged.emit()
        return True

    def modify_drag(self, x: int, y: int) -> None:
        if self._grabbed is None:
            return
        kind, obj, i = self._grabbed
        world = self.display_to_world(x, y)
        if kind == "point":
            if i < len(obj.points):
                obj.points[i] = world
        else:
            if i < len(obj.control_points):
                obj.control_points[i] = world
        self.sigFrameChanged.emit()

    def modify_release(self) -> None:
        self._grabbed = None

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        self.sigViewActivated.emit(self)
        super().mouseDoubleClickEvent(event)


# --------------------------------------------------------------------------- #
def _dist2(a, b) -> float:
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2


def _point_seg_dist2(p, a, b) -> float:
    ax, ay = a[0], a[1]
    bx, by = b[0], b[1]
    px, py = p[0], p[1]
    dx, dy = bx - ax, by - ay
    seg2 = dx * dx + dy * dy
    if seg2 < 1e-9:
        return _dist2(p, a)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / seg2))
    cx, cy = ax + t * dx, ay + t * dy
    return (px - cx) ** 2 + (py - cy) ** 2
