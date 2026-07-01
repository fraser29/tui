"""Persist markups to disk via ngawari.

* Points  -> ``vtkPolyData`` vertices (``.vtp``)
* Splines -> ``vtkPolyData`` polylines, densely sampled (``.vtp``)
* Paint   -> label ``vtkImageData`` matching the source geometry (``.vti``)

Temporal markups are written as a per-key file set, and a ``.pvd`` index is
emitted (via ``fIO.writeVTK_PVD_Dict``) so the time series can be reloaded.
"""

from __future__ import annotations

import logging
import os
from typing import Dict, List

import numpy as np
import vtk
from ngawari import fIO, vtkfilters

from ..core.image_series import ImageSeries
from ..core.markups import Markups, Spline

logger = logging.getLogger(__name__)


def build_mask_image(mask: np.ndarray, reference: vtk.vtkImageData,
                     array_name: str = "paint",
                     direction: "np.ndarray | None" = None) -> vtk.vtkImageData:
    """Wrap a numpy paint ``mask`` (shape == image dims, F-order) as image data.

    The geometry (dimensions/spacing/origin) is copied from ``reference`` so the
    label map overlays the source volume exactly.  ``direction`` (a 3x3
    direction-cosine matrix) places the mask in true world/patient coordinates.
    """
    img = vtk.vtkImageData()
    img.SetExtent(reference.GetExtent())  # preserve non-zero starting extent
    img.SetSpacing(reference.GetSpacing())
    img.SetOrigin(reference.GetOrigin())
    if direction is not None and hasattr(img, "SetDirectionMatrix"):
        dm = vtk.vtkMatrix3x3()
        for r in range(3):
            for c in range(3):
                dm.SetElement(r, c, float(direction[r, c]))
        img.SetDirectionMatrix(dm)
    vtkfilters.setArrayFromNumpy(
        img, mask.astype(np.uint8), array_name, SET_SCALAR=True, IS_3D=True
    )
    return img


def _transform_polydata(poly: vtk.vtkPolyData,
                        matrix: np.ndarray) -> vtk.vtkPolyData:
    """Return ``poly`` with the 4x4 ``matrix`` applied to its points."""
    m = vtk.vtkMatrix4x4()
    for i in range(4):
        for j in range(4):
            m.SetElement(i, j, float(matrix[i, j]))
    transform = vtk.vtkTransform()
    transform.SetMatrix(m)
    f = vtk.vtkTransformPolyDataFilter()
    f.SetTransform(transform)
    f.SetInputData(poly)
    f.Update()
    return f.GetOutput()


def _points_to_polydata(points: List) -> vtk.vtkPolyData:
    return vtkfilters.buildPolydataFromXYZ(np.asarray(points, dtype=float))


def _spline_to_polydata(spline: Spline, n_points: int = 200) -> vtk.vtkPolyData:
    pts = spline.sampled(n_points)
    return vtkfilters.buildPolyLineFromXYZ(pts, LOOP=spline.closed)


def save_markups(markups: Markups, image_series: ImageSeries, out_dir: str,
                 prefix: str = "markup", include_interpolated: bool = True) -> List[str]:
    """Write all markups to ``out_dir`` and return the list of files written.

    By default the markup at **every** time step is exported, including the
    interpolated frames between keyframes.  Set ``include_interpolated=False`` to
    export only the user-drawn manual keyframes.
    """
    os.makedirs(out_dir, exist_ok=True)
    written: List[str] = []

    point_frames: Dict[float, vtk.vtkPolyData] = {}
    spline_frames: Dict[float, vtk.vtkPolyData] = {}
    paint_frames: Dict[float, vtk.vtkImageData] = {}

    # Map the axis-aligned working grid back to true world (patient) coordinates.
    world_matrix = getattr(image_series, "patient_matrix", None)
    use_world = world_matrix is not None and not np.allclose(world_matrix, np.eye(4))
    direction = world_matrix[:3, :3] if use_world else None

    time_ids = range(image_series.n_times) if include_interpolated \
        else markups.manual_time_ids()

    for tid in time_ids:
        t = image_series.time_for_id(tid)

        ps = markups.effective_points(tid) if include_interpolated \
            else markups.manual_points(tid)
        if ps and ps.points:
            poly = _points_to_polydata(ps.points)
            point_frames[t] = _transform_polydata(poly, world_matrix) \
                if use_world else poly

        splines = markups.effective_splines(tid) if include_interpolated \
            else markups.manual_splines(tid)
        if splines:
            append = vtk.vtkAppendPolyData()
            for s in splines:
                if len(s.control_points) >= 2:
                    append.AddInputData(_spline_to_polydata(s))
            if append.GetNumberOfInputConnections(0) > 0:
                append.Update()
                poly = append.GetOutput()
                spline_frames[t] = _transform_polydata(poly, world_matrix) \
                    if use_world else poly

        mask = markups.effective_paint(tid) if include_interpolated \
            else markups.paint_mask(tid, create=False)
        if mask is not None and mask.any():
            paint_frames[t] = build_mask_image(
                mask, image_series.get_image(tid), direction=direction)

    written += _write_frames(point_frames, out_dir, f"{prefix}_points", "vtp")
    written += _write_frames(spline_frames, out_dir, f"{prefix}_splines", "vtp")
    written += _write_frames(paint_frames, out_dir, f"{prefix}_paint", "vti")

    logger.info("Saved %d markup file(s) to %s", len(written), out_dir)
    return written


def _write_frames(frames: Dict[float, vtk.vtkDataObject], out_dir: str,
                  prefix: str, ext: str) -> List[str]:
    if not frames:
        return []
    if len(frames) == 1:
        # Single frame -> write a plain file (no need for a time index).
        t, data = next(iter(frames.items()))
        path = os.path.join(out_dir, f"{prefix}.{ext}")
        fIO.writeVTKFile(data, path)
        return [path]
    # Temporal -> let ngawari emit the per-time files plus a .pvd index.
    fIO.writeVTK_PVD_Dict(frames, out_dir, prefix, ext, BUILD_SUBDIR=False)
    pvd = os.path.join(out_dir, f"{prefix}.pvd")
    return [pvd]
