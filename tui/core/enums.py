"""Enumerations shared across the model and presentation layers."""

from __future__ import annotations

from enum import Enum


class Orientation(Enum):
    """Anatomical slice orientation for a 2D view.

    The ``axis`` value is the index of the *out-of-plane* world axis and maps
    directly onto :class:`vtk.vtkImageSliceMapper` orientation values:

    * ``SAGITTAL`` slices along X (axis 0) -> shows the Y/Z plane
    * ``CORONAL``  slices along Y (axis 1) -> shows the X/Z plane
    * ``AXIAL``    slices along Z (axis 2) -> shows the X/Y plane
    """

    SAGITTAL = 0
    CORONAL = 1
    AXIAL = 2

    @property
    def axis(self) -> int:
        return self.value

    @property
    def label(self) -> str:
        return self.name.capitalize()


class ViewType(Enum):
    """The four panels of the viewer."""

    AXIAL = "axial"
    SAGITTAL = "sagittal"
    CORONAL = "coronal"
    VOLUME = "volume"

    @property
    def is_slice(self) -> bool:
        return self is not ViewType.VOLUME

    @property
    def orientation(self) -> "Orientation | None":
        return {
            ViewType.AXIAL: Orientation.AXIAL,
            ViewType.SAGITTAL: Orientation.SAGITTAL,
            ViewType.CORONAL: Orientation.CORONAL,
        }.get(self)

    @property
    def label(self) -> str:
        return "3D" if self is ViewType.VOLUME else self.value.capitalize()


class MarkupMode(Enum):
    """Active markup interaction mode."""

    NAVIGATE = "navigate"
    POINTS = "points"
    SPLINES = "splines"
    PAINT = "paint"
    MODIFY = "modify"

    @property
    def label(self) -> str:
        return {
            MarkupMode.NAVIGATE: "Navigate",
            MarkupMode.POINTS: "Add points",
            MarkupMode.SPLINES: "Add splines",
            MarkupMode.PAINT: "Paint",
            MarkupMode.MODIFY: "Modify",
        }[self]
