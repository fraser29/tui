"""Shared, presentation-agnostic viewer state.

This object is the single source of truth the views read from and the app
mutates.  It deliberately depends only on :mod:`tui.core` (no Qt/VTK
widgets) so it can be inspected and unit-tested headlessly, and so user
subclasses can read/modify everything (data, markups, current selections)
through ``self.state``.

Reslice frame
-------------
Slicing is driven by a **reslice frame**: a world-space ``center`` plus three
orthonormal ``axes`` (rows ``e0, e1, e2``).  Each panel slices the volume with a
plane through ``center`` whose normal is one frame axis:

* AXIAL    -> normal ``e2``  (in-plane ``e0`` horizontal, ``e1`` vertical)
* SAGITTAL -> normal ``e0``  (in-plane ``e1`` horizontal, ``e2`` vertical)
* CORONAL  -> normal ``e1``  (in-plane ``e0`` horizontal, ``e2`` vertical)

With the default identity ``axes`` this is ordinary axis-aligned slicing.
Rotating the frame about a panel's normal keeps all three planes mutually
perpendicular, which is what enables double-oblique reslicing via the crosshair.
"""

from __future__ import annotations

import logging
import math
from typing import Optional, Tuple

import numpy as np

from .core.enums import MarkupMode, Orientation
from .core.image_series import ImageSeries
from .core.markups import Markups, Spline

logger = logging.getLogger(__name__)

XYZ = Tuple[float, float, float]
IJK = Tuple[int, int, int]

# Fixed world reference up per plane normal axis, used to keep each panel's
# on-screen orientation stable while the crosshair rotates.
_REF_UP = {0: (0.0, 0.0, 1.0), 1: (0.0, 0.0, 1.0), 2: (0.0, -1.0, 0.0)}


def rotation_matrix(axis: np.ndarray, theta: float) -> np.ndarray:
    """Rodrigues rotation matrix for ``theta`` radians about unit ``axis``."""
    a = np.asarray(axis, dtype=float)
    norm = np.linalg.norm(a)
    if norm < 1e-12:
        return np.eye(3)
    a = a / norm
    c, s = math.cos(theta), math.sin(theta)
    x, y, z = a
    return np.array([
        [c + x * x * (1 - c),     x * y * (1 - c) - z * s, x * z * (1 - c) + y * s],
        [y * x * (1 - c) + z * s, c + y * y * (1 - c),     y * z * (1 - c) - x * s],
        [z * x * (1 - c) - y * s, z * y * (1 - c) + x * s, c + z * z * (1 - c)],
    ])


def _orthonormalise(axes: np.ndarray) -> np.ndarray:
    """Gram-Schmidt to keep the frame clean against numerical drift."""
    e0 = axes[0] / np.linalg.norm(axes[0])
    e1 = axes[1] - np.dot(axes[1], e0) * e0
    e1 = e1 / np.linalg.norm(e1)
    e2 = np.cross(e0, e1)
    return np.vstack([e0, e1, e2])


class ViewerState:
    """Mutable state shared between the model and all views."""

    def __init__(self, image_series: ImageSeries):
        self.image_series = image_series
        self.markups = Markups(
            n_times=image_series.n_times,
            image_shape=image_series.dimensions,  # (nx, ny, nz), F-order
        )

        self.current_time_id: int = 0
        self.array_name: str = image_series.default_array or ""

        # Window/level for the active array (greyscale display).
        self.window: float = 1.0
        self.level: float = 0.5
        self.reset_window_level()

        # Reslice frame: world center + orthonormal axes (rows e0, e1, e2).
        self.center: np.ndarray = np.asarray(image_series.center, dtype=float)
        self.axes: np.ndarray = np.eye(3)

        self.mode: MarkupMode = MarkupMode.NAVIGATE
        self.active_spline: Optional[Spline] = None

        # Paint settings.
        self.paint_radius: int = 3      # voxels
        self.paint_label: int = 1
        self.show_markups: bool = True
        self.show_crosshair: bool = True

    # --------------------------------------------------------------- selection
    @property
    def current_image(self):
        return self.image_series.get_image(self.current_time_id)

    @property
    def current_time(self) -> float:
        return self.image_series.time_for_id(self.current_time_id)

    def reset_window_level(self) -> None:
        if not self.array_name:
            self.window, self.level = 1.0, 0.5
            return
        lo, hi = self.image_series.scalar_range(self.array_name)
        self.window = max(hi - lo, 1e-6)
        self.level = 0.5 * (lo + hi)

    def set_array(self, array_name: str) -> None:
        if array_name and self.image_series.has_array(array_name):
            self.array_name = array_name
            self.reset_window_level()

    def set_time_id(self, time_id: int) -> None:
        new_id = max(0, min(int(time_id), self.image_series.n_times - 1))
        if new_id != self.current_time_id:
            # A spline being drawn belongs to the frame it was started on; don't
            # carry it across time steps (else clicks on the new frame would
            # extend the previous frame's spline).
            self.active_spline = None
        self.current_time_id = new_id

    # ------------------------------------------------------------ reslice frame
    def normal_for(self, orientation: Orientation) -> np.ndarray:
        return self.axes[orientation.axis]

    def inplane_for(self, orientation: Orientation) -> Tuple[np.ndarray, np.ndarray]:
        """Return ``(u, v)`` in-plane axes: ``u`` horizontal, ``v`` vertical."""
        others = [i for i in range(3) if i != orientation.axis]
        return self.axes[others[0]], self.axes[others[1]]

    def viewup_for(self, orientation: Orientation) -> np.ndarray:
        return self.inplane_for(orientation)[1]

    def camera_up_for(self, orientation: Orientation) -> np.ndarray:
        """A screen-stable camera up for ``orientation``.

        Derived from a fixed world reference projected onto the slice plane, so
        it depends only on the plane *normal* - NOT on the in-plane axes.  This
        means rotating the crosshair (which spins the in-plane axes about this
        view's normal) leaves the displayed slice still: only the crosshair
        rotates, while the other panels reslice.
        """
        n = self.normal_for(orientation)
        ref = np.asarray(_REF_UP[orientation.axis], dtype=float)
        up = ref - np.dot(ref, n) * n
        if np.linalg.norm(up) < 1e-6:
            ref = np.array([1.0, 0.0, 0.0])
            up = ref - np.dot(ref, n) * n
        return up / np.linalg.norm(up)

    def is_axis_aligned(self) -> bool:
        return bool(np.allclose(self.axes, np.eye(3), atol=1e-6))

    def reset_frame(self) -> None:
        self.center = np.asarray(self.image_series.center, dtype=float)
        self.axes = np.eye(3)

    def set_center(self, world) -> None:
        b = self.image_series.bounds
        c = np.asarray(world, dtype=float)
        self.center = np.array([
            min(max(c[0], b[0]), b[1]),
            min(max(c[1], b[2]), b[3]),
            min(max(c[2], b[4]), b[5]),
        ])

    def step_along_normal(self, orientation: Orientation, delta: int) -> None:
        n = self.normal_for(orientation)
        sp = np.asarray(self.image_series.spacing, dtype=float)
        step = float(np.dot(np.abs(n), sp)) or float(min(sp))
        self.set_center(self.center + n * step * delta)

    def rotate_about(self, orientation: Orientation, theta: float) -> None:
        """Rotate the frame about a panel's normal (keeps planes perpendicular)."""
        n = self.normal_for(orientation)
        R = rotation_matrix(n, theta)
        self.axes = _orthonormalise((R @ self.axes.T).T)

    # ------------------------------------------------------- axis-aligned helpers
    def slice_for(self, orientation: Orientation) -> int:
        """Approximate voxel index of the current plane along its world axis."""
        axis = orientation.axis
        o = self.image_series.origin[axis]
        sp = self.image_series.spacing[axis]
        lo, hi = self.image_series.slice_range(axis)
        idx = int(round((self.center[axis] - o) / sp)) if sp else 0
        return max(lo, min(idx, hi))

    def set_slice(self, orientation: Orientation, index: int) -> None:
        """Move the center to a voxel index along the world axis (axis-aligned)."""
        axis = orientation.axis
        o = self.image_series.origin[axis]
        sp = self.image_series.spacing[axis]
        c = self.center.copy()
        c[axis] = o + index * sp
        self.set_center(c)

    def slice_world_coord(self, orientation: Orientation) -> float:
        """World coordinate of the plane center along its world axis."""
        return float(self.center[orientation.axis])

    # ----------------------------------------------------- coordinate mapping
    # NOTE: VTK images may have a non-zero starting extent.  The world position
    # of structured index ``i`` is ``Origin + i*Spacing`` where ``i`` runs over
    # ``extent[0]..extent[1]``, but the numpy mask is 0-based with array index 0
    # == ``extent[0]``.  We therefore subtract/add the extent start so paint
    # lands on the voxel under the cursor (not clamped to the volume edge).
    def world_to_voxel(self, xyz: XYZ) -> IJK:
        ox, oy, oz = self.image_series.origin
        sx, sy, sz = self.image_series.spacing
        nx, ny, nz = self.image_series.dimensions
        ex0, _, ey0, _, ez0, _ = self.image_series.extent
        i = (int(round((xyz[0] - ox) / sx)) - ex0) if sx else 0
        j = (int(round((xyz[1] - oy) / sy)) - ey0) if sy else 0
        k = (int(round((xyz[2] - oz) / sz)) - ez0) if sz else 0
        return (max(0, min(i, nx - 1)),
                max(0, min(j, ny - 1)),
                max(0, min(k, nz - 1)))

    def voxel_to_world(self, ijk: IJK) -> XYZ:
        ox, oy, oz = self.image_series.origin
        sx, sy, sz = self.image_series.spacing
        ex0, _, ey0, _, ez0, _ = self.image_series.extent
        return (ox + (ijk[0] + ex0) * sx,
                oy + (ijk[1] + ey0) * sy,
                oz + (ijk[2] + ez0) * sz)
