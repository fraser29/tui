"""Headless data model for TUI (no Qt/VTK widget dependencies).

Importing this subpackage is safe in any environment - it only depends on
``vtk``/``numpy``/``ngawari``, never on a display or the Qt event loop.
"""

from .enums import Orientation, ViewType, MarkupMode
from .image_series import ImageSeries
from .markups import Markups, PointSet, Spline

__all__ = [
    "Orientation",
    "ViewType",
    "MarkupMode",
    "ImageSeries",
    "Markups",
    "PointSet",
    "Spline",
]
