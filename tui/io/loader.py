"""Load image data into an :class:`~tui.core.image_series.ImageSeries`.

All file reading is delegated to :mod:`ngawari.fIO`.  ``fIO.readImageFileToDict``
returns a ``{time: vtkImageData}`` dictionary for both single-volume files
(``{0.0: img}``) and PVD time series, which maps directly onto our temporal
container.

Use :func:`as_image_series` when you have in-memory VTK data (a single volume,
a ``{time: image}`` dict, or a list of frames) and need the same
:class:`ImageSeries` wrapper the viewer uses internally.
"""

from __future__ import annotations

import logging
import os
from typing import Dict, Mapping, Optional, Sequence, Union

import numpy as np
import vtk
from ngawari import fIO, vtkfilters

from ..core.image_series import ImageSeries

logger = logging.getLogger(__name__)

# Single-volume image formats ngawari can read directly.
SUPPORTED_IMAGE_SUFFIXES = (
    ".vti", ".nii", ".nii.gz", ".nrrd", ".mha", ".mhd", ".pvd",
)

# Anything :func:`as_image_series` accepts.
ImageInput = Union[
    str,
    vtk.vtkImageData,
    ImageSeries,
    Mapping[Union[int, float], vtk.vtkImageData],
    Sequence[vtk.vtkImageData],
]


def load_image_series(path: str) -> ImageSeries:
    """Load ``path`` into an :class:`ImageSeries`.

    Supports:

    * Any single-volume image ngawari can read (``.vti``, ``.nii``, ``.nrrd``,
      ``.mha`` ...).
    * ``.pvd`` time-series (temporal data -> multiple time points).
    * A directory of DICOM (requires the optional ``spydcmtk`` dependency).
    """
    path = os.path.expanduser(path)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Input path does not exist: {path}")

    is_dicom = os.path.isdir(path)
    if is_dicom:
        time_to_image = _load_dicom_dir(path)
    else:
        logger.info("Reading image data via ngawari.fIO: %s", path)
        time_to_image = fIO.readImageFileToDict(path)

    time_to_image = _validate_dict(time_to_image, path)
    # Capture the patient/world orientation as a transform while keeping the grid
    # axis-aligned (so the viewer's coordinate maths stay valid).  The transform
    # is reapplied when markups are exported so polydata lands in true world
    # (patient) coordinates.  DICOM orientation comes from the stored DICOM tags
    # (reliable); other formats use the image's own direction matrix.
    if is_dicom:
        patient_matrix = _dicom_patient_matrix(time_to_image)
    else:
        patient_matrix = _extract_and_normalise_orientation(time_to_image)
    series = ImageSeries(time_to_image, patient_matrix=patient_matrix)
    logger.info("Loaded %s%s", series,
                " (with patient transform)" if patient_matrix is not None else "")
    return series


def as_image_series(source: ImageInput, *,
                    patient_matrix: Optional[np.ndarray] = None,
                    source_label: str = "<memory>") -> ImageSeries:
    """Normalise common image sources to an :class:`ImageSeries`.

    Accepts:

    * :class:`ImageSeries` — returned unchanged.
    * ``str`` — file path (``.vti``, ``.nii``, ``.pvd``, …) or DICOM directory
      (same rules as :func:`load_image_series`).
    * :class:`vtk.vtkImageData` — wrapped as a single time point at ``t=0``.
    * ``{time: vtkImageData}`` mapping — temporal series (``time`` may be
      ``int`` or ``float``).
    * sequence of :class:`vtk.vtkImageData` — frames at ``t=0, 1, 2, …``.

    In-memory volumes are axis-normalised the same way as loaded files (patient
    direction matrix extracted and stored on the series).  Pass ``patient_matrix``
    to skip auto-detection when you already know the transform.
    """
    if isinstance(source, ImageSeries):
        return source

    if isinstance(source, str):
        return load_image_series(source)

    if isinstance(source, vtk.vtkImageData):
        time_to_image = {0.0: source}

    elif isinstance(source, Mapping):
        time_to_image = _mapping_to_time_dict(source, source_label)

    elif isinstance(source, (list, tuple)):
        if not source:
            raise ValueError("empty image sequence")
        time_to_image = {float(i): img for i, img in enumerate(source)}

    else:
        raise TypeError(
            f"cannot convert {type(source).__name__} to ImageSeries; "
            "expected a path, vtkImageData, {time: image} dict, image list, "
            "or ImageSeries")

    time_to_image = _validate_dict(time_to_image, source_label)
    if patient_matrix is None:
        patient_matrix = _extract_and_normalise_orientation(time_to_image)
    series = ImageSeries(time_to_image, patient_matrix=patient_matrix)
    logger.info("Built %s from %s", series, source_label)
    return series


def _mapping_to_time_dict(mapping: Mapping, label: str
                          ) -> Dict[float, vtk.vtkImageData]:
    out: Dict[float, vtk.vtkImageData] = {}
    for key, img in mapping.items():
        try:
            t = float(key)
        except (TypeError, ValueError) as exc:
            raise TypeError(
                f"time keys in {label} must be numeric (got {key!r})"
            ) from exc
        out[t] = img
    return out


def _field_vector(img: vtk.vtkImageData, name: str) -> Optional[np.ndarray]:
    """Read a numeric field-data array off ``img`` (or None if absent)."""
    fd = img.GetFieldData()
    if fd is None or fd.GetArray(name) is None:
        return None
    try:
        return np.asarray(vtkfilters.getFieldData(img, name), dtype=float).ravel()
    except Exception:  # noqa: BLE001 - tolerate non-numeric / missing field data
        return None


def _dicom_patient_matrix(
        time_to_image: Dict[float, vtk.vtkImageData]) -> Optional[np.ndarray]:
    """Build the axis-aligned-grid -> patient transform for a DICOM volume.

    ``spydcmtk`` stores the DICOM ``ImageOrientationPatient`` (row + column
    direction cosines) and the through-plane ``SliceVector`` as field data on the
    VTI.  These define the patient direction matrix ``D = [row | col | slice]``
    (columns).  Because the working grid shares the same origin ``O``, spacing
    and extent and differs only by ``D``, world coordinates map back to the
    patient frame via ``world = O + D·(world_aligned - O)``, i.e. the 4x4
    ``M = T(O)·D·T(-O)``.

    Note: we intentionally do *not* use ``buildVTIDict(DIRECTION_VECTORS=True)``
    - its matrix is transposed and its slice vector is unreliable for
    single-slice series.
    """
    ref = time_to_image[sorted(time_to_image.keys())[0]]
    iop = _field_vector(ref, "ImageOrientationPatient")
    sv = _field_vector(ref, "SliceVector")
    if iop is None or iop.size < 6:
        return None

    row = iop[0:3]
    col = iop[3:6]
    if sv is None or sv.size < 3 or np.linalg.norm(sv) < 1e-9:
        sv = np.cross(row, col)  # fall back to the IOP normal (single slice)

    def _unit(v: np.ndarray) -> np.ndarray:
        n = np.linalg.norm(v)
        return v / n if n > 1e-12 else v

    D = np.column_stack([_unit(row), _unit(col), _unit(sv)])
    if np.allclose(D, np.eye(3), atol=1e-9):
        return None

    O = np.asarray(ref.GetOrigin(), dtype=float)
    M = np.eye(4)
    M[:3, :3] = D
    M[:3, 3] = O - D @ O
    return M


def _direction_matrix(img: vtk.vtkImageData) -> Optional[np.ndarray]:
    """Return the image's 3x3 direction (orientation) matrix, if any."""
    getter = getattr(img, "GetDirectionMatrix", None)
    if getter is None:  # pragma: no cover - very old VTK
        return None
    dm = getter()
    if dm is None:
        return None
    return np.array([[dm.GetElement(r, c) for c in range(3)] for r in range(3)],
                    dtype=float)


def _set_identity_direction(img: vtk.vtkImageData) -> None:
    setter = getattr(img, "SetDirectionMatrix", None)
    if setter is None:  # pragma: no cover - very old VTK
        return
    setter(vtk.vtkMatrix3x3())  # default-constructed = identity


def _extract_and_normalise_orientation(
        time_to_image: Dict[float, vtk.vtkImageData]) -> Optional[np.ndarray]:
    """Pull the patient orientation out of the loaded grid.

    DICOM (and some NIfTI/NRRD) volumes carry a direction-cosine matrix ``D``
    that rotates the voxel grid into the patient frame.  This viewer works in an
    axis-aligned grid, so we:

    1. read ``D`` (and origin ``O``) from the first volume,
    2. build the aligned-grid -> patient transform ``M = T(O)·D·T(-O)``
       (world coordinates only differ from the axis-aligned grid by ``D`` about
       ``O``, since origin/spacing/extent are unchanged),
    3. reset every volume's direction matrix to identity so rendering and the
       coordinate maths run on an axis-aligned grid.

    Returns the 4x4 matrix, or ``None`` when the data is already axis-aligned.
    """
    ref = time_to_image[sorted(time_to_image.keys())[0]]
    D = _direction_matrix(ref)
    if D is None or np.allclose(D, np.eye(3)):
        return None

    O = np.asarray(ref.GetOrigin(), dtype=float)
    M = np.eye(4)
    M[:3, :3] = D
    M[:3, 3] = O - D @ O

    for img in time_to_image.values():
        _set_identity_direction(img)
    return M


def _validate_dict(time_to_image: Dict[float, vtk.vtkDataObject], path: str
                   ) -> Dict[float, vtk.vtkImageData]:
    if not time_to_image:
        raise IOError(f"No image data found in {path}")
    cleaned: Dict[float, vtk.vtkImageData] = {}
    for t, img in time_to_image.items():
        if img is None or not isinstance(img, vtk.vtkImageData):
            raise IOError(
                f"{path} (t={t}) is not vtkImageData (got {type(img).__name__}); "
                "this viewer requires image (volume) data."
            )
        if img.GetPointData().GetNumberOfArrays() == 0:
            raise IOError(f"{path} (t={t}) contains no point-data arrays")
        cleaned[float(t)] = img
    return cleaned


def _load_dicom_dir(path: str) -> Dict[float, vtk.vtkImageData]:
    try:
        from spydcmtk import dcmTK
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise ImportError(
            "Reading a DICOM directory requires the optional 'spydcmtk' "
            "dependency. Install with: pip install spydcmtk"
        ) from exc

    logger.info("Reading DICOM directory: %s", path)
    studies = dcmTK.ListOfDicomStudies.setFromDirectory(path, HIDE_PROGRESSBAR=True)
    if not studies:
        raise IOError(f"No DICOM studies found under {path}")

    series = _pick_series(studies[0])
    logger.info("Selected DICOM series %s (%d files)",
                series.getTag("SeriesNumber", ifNotFound="?"), len(series))

    # buildVTIDict returns {triggerTime: vtkImageData}; one entry per volume,
    # several entries for a 4D/cine acquisition (-> temporal ImageSeries).
    # TRUE_ORIENTATION=False keeps the native voxel grid (correct origin and
    # spacing, axis-aligned) which matches this viewer's coordinate maths and
    # avoids the slow resample-to-image (and its extra vtkValidPointMask array).
    # The patient orientation is recovered from the DICOM tags stored as field
    # data (ImageOrientationPatient / SliceVector) in _dicom_patient_matrix.
    vti_dict = series.buildVTIDict(TRUE_ORIENTATION=False)

    time_to_image: Dict[float, vtk.vtkImageData] = {}
    for index, (key, img) in enumerate(sorted(vti_dict.items(), key=_time_key)):
        try:
            t = float(key)
        except (TypeError, ValueError):
            t = float(index)
        _fix_degenerate_spacing(img)
        time_to_image[t] = img
    return time_to_image


def _fix_degenerate_spacing(img: vtk.vtkImageData) -> None:
    """Replace any zero spacing with a sensible non-zero value.

    A single-slice (or single-row/column) series has no spacing along its thin
    axis, which spydcmtk reports as 0.0.  Zero spacing gives the slice zero
    thickness, so the reslice samples nothing and the panel renders black.  We
    substitute the smallest positive in-plane spacing (or 1.0) so the slice has
    a finite thickness and displays.
    """
    sx, sy, sz = img.GetSpacing()
    positive = [s for s in (sx, sy, sz) if s > 0.0]
    fallback = min(positive) if positive else 1.0
    fixed = tuple(s if s > 0.0 else fallback for s in (sx, sy, sz))
    if fixed != (sx, sy, sz):
        img.SetSpacing(*fixed)
        logger.info("Patched degenerate spacing %s -> %s", (sx, sy, sz), fixed)


def _pick_series(study) -> "object":
    """Choose the most volume-like series in a study (most slices, prefer 3D)."""
    best = None
    best_score = -1
    for series in study:
        try:
            slices = series.getNumberOfSlicesPerVolume()
        except Exception:  # noqa: BLE001 - tolerate odd/secondary-capture series
            slices = len(series)
        score = slices + (10_000 if _safe_is3d(series) else 0)
        if score > best_score:
            best, best_score = series, score
    if best is None:
        raise IOError("Study contains no readable DICOM series")
    return best


def _safe_is3d(series) -> bool:
    try:
        return bool(series.is3D())
    except Exception:  # noqa: BLE001
        return False


def _time_key(item):
    try:
        return float(item[0])
    except (TypeError, ValueError):
        return 0.0
