"""Interactor style for the 2D slice panels.

Behaviour by mode:

* NAVIGATE  - left-drag rotates/translates the crosshair when grabbed,
  otherwise adjusts window/level.  Mouse wheel always scrolls slices.
* POINTS / SPLINES - left-click drops a point / spline handle.
* PAINT     - left-drag paints, right-click erases.
* MODIFY    - left-drag moves the nearest handle; left-click on a spline line
  inserts a new control point; right-click deletes the nearest handle.  Editing
  an interpolated (cyan) frame promotes it to an editable keyframe.
"""

from __future__ import annotations

import vtk

from ..core.enums import MarkupMode


class SliceInteractorStyle(vtk.vtkInteractorStyleImage):
    """Image interactor that delegates markup / crosshair actions to its view."""

    def __init__(self, slice_view):
        super().__init__()
        self._view = slice_view
        self._drag = None          # None | "paint" | "modify" | ("crosshair", token)
        self.AddObserver("LeftButtonPressEvent", self._on_left_down)
        self.AddObserver("LeftButtonReleaseEvent", self._on_left_up)
        self.AddObserver("MouseMoveEvent", self._on_move)
        self.AddObserver("MouseWheelForwardEvent", self._on_wheel_forward)
        self.AddObserver("MouseWheelBackwardEvent", self._on_wheel_backward)
        self.AddObserver("RightButtonPressEvent", self._on_right_down)

    @property
    def _mode(self) -> MarkupMode:
        return self._view.state.mode

    def _pos(self):
        return self.GetInteractor().GetEventPosition()

    def _track_cursor(self) -> None:
        x, y = self._pos()
        self._view.note_cursor_display(x, y)

    # ------------------------------------------------------------ left button
    def _on_left_down(self, obj, event):
        self._track_cursor()
        mode = self._mode
        x, y = self._pos()
        if mode in (MarkupMode.POINTS, MarkupMode.SPLINES):
            self._view.handle_pick(*self._view.display_to_world(x, y))
            return
        if mode is MarkupMode.PAINT:
            self._drag = "paint"
            self._view.handle_paint(*self._view.display_to_world(x, y), erase=False)
            return
        if mode is MarkupMode.MODIFY:
            # Grab an existing handle, otherwise insert a node on a spline line.
            if self._view.modify_grab(x, y) or self._view.modify_insert(x, y):
                self._drag = "modify"
            return
        # NAVIGATE: try to grab the crosshair, else adjust window/level.
        if self._view.state.show_crosshair:
            token = self._view.crosshair_grab(x, y)
            if token is not None:
                self._drag = ("crosshair", token)
                return
        self._drag = "window"
        self._view.window_level_begin(x, y)

    def _on_left_up(self, obj, event):
        if self._drag is not None:
            drag, self._drag = self._drag, None
            if drag == "modify":
                self._view.modify_release()
            elif drag == "paint":
                self._view.end_paint_stroke()
            return
        self.OnLeftButtonUp()

    def _on_move(self, obj, event):
        self._track_cursor()
        x, y = self._pos()
        if self._drag == "paint":
            self._view.handle_paint(*self._view.display_to_world(x, y), erase=False)
            return
        if self._drag == "modify":
            self._view.modify_drag(x, y)
            return
        if self._drag == "window":
            self._view.window_level_drag(x, y)
            return
        if isinstance(self._drag, tuple) and self._drag[0] == "crosshair":
            self._view.crosshair_drag(x, y, self._drag[1])
            return
        self.OnMouseMove()

    # ----------------------------------------------------------- right button
    def _on_right_down(self, obj, event):
        self._track_cursor()
        if self._mode is MarkupMode.PAINT:
            x, y = self._pos()
            self._view.handle_paint(*self._view.display_to_world(x, y), erase=True)
            return
        if self._mode is MarkupMode.MODIFY:
            x, y = self._pos()
            self._view.modify_delete(x, y)
            return
        self.OnRightButtonDown()

    # ------------------------------------------------------------------ wheel
    def _on_wheel_forward(self, obj, event):
        self._view.step_slice(+1)

    def _on_wheel_backward(self, obj, event):
        self._view.step_slice(-1)
