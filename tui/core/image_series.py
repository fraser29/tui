"""Temporal image container - an ordered set of ``vtkImageData`` keyed by time."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np
import vtk
from ngawari import vtkfilters

logger = logging.getLogger(__name__)


class ImageSeries:
    """An ordered collection of ``vtkImageData`` volumes over time.

    A non-temporal image is simply a series with a single time point.  All
    access is by integer ``time_id`` (0-based, ordered by ascending time).

    The class assumes every time point shares the same geometry (dimensions,
    spacing, origin) and the same set of point-data arrays - the usual case for
    a 4D acquisition.  Geometry/array metadata is therefore read from the first
    volume.

    ``patient_matrix`` is the 4x4 transform that maps the (axis-aligned) grid
    used internally back into true world/patient coordinates.  It is identity
    for data that is already axis-aligned, and the DICOM direction-cosine
    transform for oriented acquisitions; markup export applies it so polydata is
    saved in true world coordinates.
    """

    def __init__(self, time_to_image: Dict[float, vtk.vtkImageData],
                 patient_matrix: Optional[np.ndarray] = None):
        if not time_to_image:
            raise ValueError("ImageSeries requires at least one image")
        self._times: List[float] = sorted(time_to_image.keys())
        self._images: List[vtk.vtkImageData] = [time_to_image[t] for t in self._times]
        self._scalar_range_cache: Dict[str, Tuple[float, float]] = {}
        self.patient_matrix: np.ndarray = (
            np.eye(4) if patient_matrix is None
            else np.asarray(patient_matrix, dtype=float))
        self._validate()

    @property
    def has_patient_transform(self) -> bool:
        """True when the grid is rotated relative to true world coordinates."""
        return not np.allclose(self.patient_matrix, np.eye(4))

    def _validate(self) -> None:
        ref_dims = self._images[0].GetDimensions()
        for tid, img in enumerate(self._images):
            if img.GetDimensions() != ref_dims:
                logger.warning(
                    "Time point %d dims %s differ from reference %s",
                    tid, img.GetDimensions(), ref_dims,
                )

    # ------------------------------------------------------------------ time
    @property
    def n_times(self) -> int:
        return len(self._images)

    @property
    def is_temporal(self) -> bool:
        return self.n_times > 1

    @property
    def times(self) -> List[float]:
        return list(self._times)

    def time_for_id(self, time_id: int) -> float:
        return self._times[self._clamp(time_id)]

    def _clamp(self, time_id: int) -> int:
        if time_id < 0:
            return 0
        if time_id >= self.n_times:
            return self.n_times - 1
        return time_id

    def get_image(self, time_id: int = 0) -> vtk.vtkImageData:
        return self._images[self._clamp(time_id)]

    # -------------------------------------------------------------- geometry
    @property
    def reference(self) -> vtk.vtkImageData:
        return self._images[0]

    @property
    def dimensions(self) -> Tuple[int, int, int]:
        return self.reference.GetDimensions()

    @property
    def spacing(self) -> Tuple[float, float, float]:
        return self.reference.GetSpacing()

    @property
    def origin(self) -> Tuple[float, float, float]:
        return self.reference.GetOrigin()

    @property
    def bounds(self) -> Tuple[float, float, float, float, float, float]:
        return self.reference.GetBounds()

    @property
    def center(self) -> Tuple[float, float, float]:
        b = self.bounds
        return ((b[0] + b[1]) / 2.0, (b[2] + b[3]) / 2.0, (b[4] + b[5]) / 2.0)

    @property
    def extent(self) -> Tuple[int, int, int, int, int, int]:
        return self.reference.GetExtent()

    def middle_slice(self, axis: int) -> int:
        e = self.extent
        return (e[axis * 2] + e[axis * 2 + 1]) // 2

    def slice_range(self, axis: int) -> Tuple[int, int]:
        e = self.extent
        return e[axis * 2], e[axis * 2 + 1]

    # ----------------------------------------------------------------- arrays
    @property
    def array_names(self) -> List[str]:
        names = vtkfilters.getArrayNames(self.reference, pointData=True)
        return [n for n in names if n]

    @property
    def default_array(self) -> Optional[str]:
        scalar = vtkfilters.getScalarsArrayName(self.reference, pointData=True)
        if scalar:
            return scalar
        names = self.array_names
        return names[0] if names else None

    def scalar_range(self, array_name: str) -> Tuple[float, float]:
        """Global (over all time points) data range for ``array_name``."""
        if array_name in self._scalar_range_cache:
            return self._scalar_range_cache[array_name]
        lo, hi = float("inf"), float("-inf")
        for img in self._images:
            arr = vtkfilters.getArray(img, array_name, pointData=True)
            if arr is None:
                continue
            r = arr.GetRange(-1)  # magnitude range for multi-component arrays
            lo, hi = min(lo, r[0]), max(hi, r[1])
        if lo > hi:  # array missing everywhere
            lo, hi = 0.0, 1.0
        self._scalar_range_cache[array_name] = (lo, hi)
        return lo, hi

    def has_array(self, array_name: str) -> bool:
        return array_name in self.array_names

    def __len__(self) -> int:
        return self.n_times

    def __repr__(self) -> str:
        return (
            f"ImageSeries(n_times={self.n_times}, dims={self.dimensions}, "
            f"arrays={self.array_names})"
        )
