"""The 3D panel - orthogonal slice planes, outline and 3D markups.

This renders the three current slice planes in 3D (a classic MPR layout) plus
the markups for the current time step.
"""

from __future__ import annotations

import logging
from typing import List, Tuple

import vtk
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
from PyQt5 import QtCore, QtWidgets

from ..core.enums import Orientation, ViewType
from ..state import ViewerState

logger = logging.getLogger(__name__)

_COL_MANUAL_POINT = (1.0, 0.85, 0.1)
_COL_INTERP_POINT = (0.2, 0.9, 0.9)
_COL_MANUAL_SPLINE = (1.0, 0.55, 0.0)
_COL_INTERP_SPLINE = (0.2, 0.9, 0.9)

# Marker size in screen pixels (constant under zoom).
_POINT_PX = 6.0


class VolumeView(QtWidgets.QFrame):
    """3D MPR + markup panel."""

    sigViewActivated = QtCore.pyqtSignal(object)

    def __init__(self, state: ViewerState, parent=None):
        super().__init__(parent)
        self.view_type = ViewType.VOLUME
        self.state = state

        self.setFrameStyle(QtWidgets.QFrame.Box | QtWidgets.QFrame.Plain)
        self.setLineWidth(1)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(1, 1, 1, 1)

        self._vtk_widget = QVTKRenderWindowInteractor(self)
        layout.addWidget(self._vtk_widget)
        self._render_window = self._vtk_widget.GetRenderWindow()
        self._interactor = self._render_window.GetInteractor()

        self.renderer = vtk.vtkRenderer()
        self.renderer.SetBackground(0.08, 0.08, 0.11)
        self._render_window.AddRenderer(self.renderer)
        self._interactor.SetInteractorStyle(vtk.vtkInteractorStyleTrackballCamera())

        self._camera_initialised = False
        self._build_pipeline()
        # Wire inputs immediately to avoid unconnected-port warnings on the
        # first render (before refresh() runs).
        img = self.state.current_image
        self._outline.SetInputData(img)
        for orient, (mapper, actor, plane) in self._slice_actors.items():
            mapper.SetInputData(img)

    def start(self) -> None:
        self._interactor.Initialize()

    def close_view(self) -> None:
        self._vtk_widget.close()

    # ------------------------------------------------------------- pipeline
    def _build_pipeline(self) -> None:
        self._slice_actors = {}
        for orient in Orientation:
            plane = vtk.vtkPlane()
            mapper = vtk.vtkImageResliceMapper()
            mapper.SetSlicePlane(plane)
            mapper.SliceFacesCameraOff()
            mapper.SliceAtFocalPointOff()
            actor = vtk.vtkImageSlice()
            actor.SetMapper(mapper)
            actor.GetProperty().SetInterpolationTypeToLinear()
            self.renderer.AddViewProp(actor)
            self._slice_actors[orient] = (mapper, actor, plane)

        self._outline_actor, self._outline = self._make_outline()
        self.renderer.AddActor(self._outline_actor)

        self._point_actor, self._point_poly = self._make_glyph_actor()
        self._spline_manual_actor, self._spline_manual_poly = self._make_line_actor()
        self._spline_interp_actor, self._spline_interp_poly = self._make_line_actor()
        for a in (self._point_actor, self._spline_manual_actor, self._spline_interp_actor):
            self.renderer.AddActor(a)

    def _make_outline(self):
        outline = vtk.vtkOutlineFilter()
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(outline.GetOutputPort())
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(0.6, 0.6, 0.7)
        return actor, outline

    def _make_glyph_actor(self):
        poly = vtk.vtkPolyData()
        poly.SetPoints(vtk.vtkPoints())
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputData(poly)
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        prop = actor.GetProperty()
        prop.SetColor(*_COL_MANUAL_POINT)
        prop.SetPointSize(_POINT_PX)
        prop.RenderPointsAsSpheresOn()
        return actor, poly

    def _make_line_actor(self):
        poly = vtk.vtkPolyData()
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputData(poly)
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetLineWidth(3.0)
        return actor, poly

    # ----------------------------------------------------------------- render
    def refresh(self) -> None:
        img = self.state.current_image
        if self.state.array_name:
            img.GetPointData().SetActiveScalars(self.state.array_name)
        self._outline.SetInputData(img)
        for orient, (mapper, actor, plane) in self._slice_actors.items():
            mapper.SetInputData(img)
            plane.SetOrigin(*self.state.center)
            plane.SetNormal(*self.state.normal_for(orient))
            prop = actor.GetProperty()
            prop.SetColorWindow(self.state.window)
            prop.SetColorLevel(self.state.level)
        self._refresh_markups()
        if not self._camera_initialised:
            self.renderer.ResetCamera()
            self._camera_initialised = True
        self.renderer.ResetCameraClippingRange()
        self._render_window.Render()

    def apply_window_level(self) -> None:
        """Re-apply the shared window/level to the MPR slices and redraw."""
        for _orient, (_mapper, actor, _plane) in self._slice_actors.items():
            prop = actor.GetProperty()
            prop.SetColorWindow(self.state.window)
            prop.SetColorLevel(self.state.level)
        self._render_window.Render()

    def _refresh_markups(self) -> None:
        show = self.state.show_markups
        tid = self.state.current_time_id

        ps = self.state.markups.effective_points(tid) if show else None
        pts = list(ps.points) if ps else []
        self._set_glyph_points(self._point_poly, pts)
        self._point_actor.GetProperty().SetColor(
            *(_COL_MANUAL_POINT if (ps and ps.is_manual) else _COL_INTERP_POINT))
        self._point_actor.SetVisibility(bool(pts))

        manual_curves, interp_curves = [], []
        if show:
            for s in self.state.markups.effective_splines(tid):
                if len(s.control_points) >= 2:
                    (manual_curves if s.is_manual else interp_curves).append(
                        s.sampled(150))
        self._set_lines(self._spline_manual_poly, manual_curves)
        self._set_lines(self._spline_interp_poly, interp_curves)
        self._spline_manual_actor.GetProperty().SetColor(*_COL_MANUAL_SPLINE)
        self._spline_interp_actor.GetProperty().SetColor(*_COL_INTERP_SPLINE)
        self._spline_manual_actor.SetVisibility(bool(manual_curves))
        self._spline_interp_actor.SetVisibility(bool(interp_curves))

    # --------------------------------------------------------------- helpers
    @staticmethod
    def _set_glyph_points(poly: vtk.vtkPolyData, points) -> None:
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
    def _set_lines(poly: vtk.vtkPolyData, curves: List) -> None:
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

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        self.sigViewActivated.emit(self)
        super().mouseDoubleClickEvent(event)
