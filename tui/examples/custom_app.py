"""Example of extending :class:`tui.ViewerApp` with custom buttons.

Run with::

    tui -in TEST_DATA/test_data.vti --example

or from Python::

    from tui import launch
    from tui.examples.custom_app import ExampleViewer
    launch("TEST_DATA/test_data.vti", viewer_class=ExampleViewer)

Each custom callback has full access to the data and markups through
``self.state`` / the convenience properties, so this is the recommended place to
add study-specific workflows (saving ROIs, exporting measurements, etc.).
"""

from __future__ import annotations

import logging
import os
import tempfile

from PyQt5 import QtWidgets

from ..app import ViewerApp

logger = logging.getLogger(__name__)


class ExampleViewer(ViewerApp):
    """A viewer wired with a handful of demonstration custom buttons."""

    def customise(self) -> None:
        # Custom buttons are laid out in the 6x2 grid (row, col).
        self.set_custom_button(0, 0, "Info", self.show_info)
        self.set_custom_button(0, 1, "Centre pt", self.add_centre_point)
        self.set_custom_button(1, 0, "Box ROI", self.add_box_spline)
        self.set_custom_button(1, 1, "Interp \u2192 disk", self.export_interpolated)
        self.set_custom_button(2, 0, "Clear all", self.clear_all_markups)

    # ----------------------------------------------------------- callbacks
    def show_info(self) -> None:
        s = self.state
        summary = self.markups.summary()
        msg = (
            f"Image: {s.image_series.dimensions}  "
            f"({s.image_series.n_times} time point(s))\n"
            f"Array: {self.current_array}\n"
            f"Time id: {self.current_time_id}\n"
            f"Markup keyframes:\n"
            f"  points : {summary['points']}\n"
            f"  splines: {summary['splines']}\n"
            f"  paint  : {summary['paint']}"
        )
        QtWidgets.QMessageBox.information(self, "Viewer info", msg)

    def add_centre_point(self) -> None:
        """Drop a point at the volume centre for the current time step."""
        self.markups.add_point(self.current_time_id, self.image_series.center)

    def add_box_spline(self) -> None:
        """Add a closed rectangular spline on the current axial slice."""
        from ..core.enums import Orientation

        b = self.image_series.bounds
        z = self.state.slice_world_coord(Orientation.AXIAL)
        dx = 0.25 * (b[1] - b[0]); dy = 0.25 * (b[3] - b[2])
        cx = 0.5 * (b[0] + b[1]); cy = 0.5 * (b[2] + b[3])
        corners = [
            (cx - dx, cy - dy, z), (cx + dx, cy - dy, z),
            (cx + dx, cy + dy, z), (cx - dx, cy + dy, z),
        ]
        spline = self.markups.add_spline(self.current_time_id, closed=True)
        spline.control_points.extend(corners)

    def export_interpolated(self) -> None:
        """Export markups (including interpolated frames) to a temp directory."""
        out_dir = tempfile.mkdtemp(prefix="tui_markups_")
        files = self.save_markups(out_dir, include_interpolated=True)
        QtWidgets.QMessageBox.information(
            self, "Exported",
            f"Wrote {len(files)} file(s) to:\n{out_dir}\n\n" + "\n".join(
                os.path.basename(f) for f in files))

    def clear_all_markups(self) -> None:
        self.markups.clear_all()
        self.state.active_spline = None
