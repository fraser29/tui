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
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import vtk
from ngawari import fIO, vtkfilters

from ..core.image_series import ImageSeries
from ..core.markups import Markups, Spline

logger = logging.getLogger(__name__)

XYZ = Tuple[float, float, float]

# The markup kinds ``save_markups`` knows how to write.
MARKUP_KINDS = ("points", "splines", "paint")


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
                 prefix: str = "markup", include_interpolated: bool = True,
                 kinds: Sequence[str] = MARKUP_KINDS,
                 kind_suffix: bool = True) -> List[str]:
    """Write all markups to ``out_dir`` and return the list of files written.

    By default the markup at **every** time step is exported, including the
    interpolated frames between keyframes.  Set ``include_interpolated=False`` to
    export only the user-drawn manual keyframes.

    ``kinds`` selects which markup types to export: any of ``"points"``,
    ``"splines"`` (both written as ``.vtp`` polydata) and ``"paint"`` (written as
    ``.vti`` label maps).  Points and splines are the "polydata" markups; paint
    is the "labelmap" markup.

    ``kind_suffix`` controls whether the per-kind suffix (``_points`` /
    ``_splines`` / ``_paint``) is appended to ``prefix``.  Set it ``False`` to
    write ``prefix.ext`` verbatim - only safe when a single output file is
    produced (points and splines both use ``.vtp`` and would otherwise collide).
    """
    os.makedirs(out_dir, exist_ok=True)
    written: List[str] = []
    want_points = "points" in kinds
    want_splines = "splines" in kinds
    want_paint = "paint" in kinds

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

        if want_points:
            ps = markups.effective_points(tid) if include_interpolated \
                else markups.manual_points(tid)
            if ps and ps.points:
                poly = _points_to_polydata(ps.points)
                point_frames[t] = _transform_polydata(poly, world_matrix) \
                    if use_world else poly

        if want_splines:
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

        if want_paint:
            mask = markups.effective_paint(tid) if include_interpolated \
                else markups.paint_mask(tid, create=False)
            if mask is not None and mask.any():
                paint_frames[t] = build_mask_image(
                    mask, image_series.get_image(tid), direction=direction)

    pts_prefix = f"{prefix}_points" if kind_suffix else prefix
    spl_prefix = f"{prefix}_splines" if kind_suffix else prefix
    paint_prefix = f"{prefix}_paint" if kind_suffix else prefix
    written += _write_frames(point_frames, out_dir, pts_prefix, "vtp")
    written += _write_frames(spline_frames, out_dir, spl_prefix, "vtp")
    written += _write_frames(paint_frames, out_dir, paint_prefix, "vti")

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


# --------------------------------------------------------------------------- #
#  Loading markups from disk (the inverse of ``save_markups``)
# --------------------------------------------------------------------------- #
def _world_to_grid_matrix(image_series: ImageSeries) -> Optional[np.ndarray]:
    """Inverse of the patient transform: true world -> axis-aligned grid.

    Markups are exported in true world (patient) coordinates (the patient matrix
    baked in).  The viewer stores markups in the axis-aligned working grid, so
    loaded polydata/surfaces must be mapped back with the inverse transform.
    Returns ``None`` when the series is already axis-aligned.
    """
    m = getattr(image_series, "patient_matrix", None)
    if m is None or np.allclose(m, np.eye(4)):
        return None
    return np.linalg.inv(np.asarray(m, dtype=float))


def _read_polydata(path: str) -> vtk.vtkPolyData:
    obj = fIO.readVTKFile(path)
    if isinstance(obj, vtk.vtkPolyData):
        return obj
    if isinstance(obj, vtk.vtkDataSet):
        # e.g. an unstructured grid surface -> extract its polygonal surface.
        surf = vtk.vtkDataSetSurfaceFilter()
        surf.SetInputData(obj)
        surf.Update()
        return surf.GetOutput()
    raise IOError(f"{path} does not contain polydata (got {type(obj).__name__})")


def _cell_point_lists(cells: vtk.vtkCellArray, points: vtk.vtkPoints
                      ) -> List[List[XYZ]]:
    """Return each cell as an ordered list of its world-space points."""
    out: List[List[XYZ]] = []
    if cells is None or cells.GetNumberOfCells() == 0:
        return out
    cells.InitTraversal()
    ids = vtk.vtkIdList()
    while cells.GetNextCell(ids):
        out.append([tuple(points.GetPoint(ids.GetId(i)))
                    for i in range(ids.GetNumberOfIds())])
    return out


def load_markup_polydata(path: str, image_series: ImageSeries
                         ) -> Tuple[List[XYZ], List[Spline]]:
    """Read a polydata markup file into ``(points, splines)``.

    Vertex cells become landmark points; polyline cells become splines whose
    control points are the polyline vertices (a closed loop is detected when the
    first and last vertex coincide).  A file with only bare points (no cells) is
    treated as a set of landmarks.  Coordinates are mapped from true world back
    into the viewer's axis-aligned working grid.
    """
    poly = _read_polydata(path)
    grid_matrix = _world_to_grid_matrix(image_series)
    if grid_matrix is not None:
        poly = _transform_polydata(poly, grid_matrix)

    vtk_pts = poly.GetPoints()
    points: List[XYZ] = []
    splines: List[Spline] = []
    if vtk_pts is None or vtk_pts.GetNumberOfPoints() == 0:
        return points, splines

    for cp in _cell_point_lists(poly.GetLines(), vtk_pts):
        if len(cp) < 2:
            continue
        closed = len(cp) > 2 and np.allclose(cp[0], cp[-1])
        if closed:
            cp = cp[:-1]
        splines.append(Spline(control_points=[tuple(p) for p in cp],
                              closed=closed, is_manual=True))

    vert_cells = _cell_point_lists(poly.GetVerts(), vtk_pts)
    if vert_cells:
        for cell in vert_cells:
            points.extend(cell)
    elif poly.GetNumberOfLines() == 0:
        # No cells at all -> every stored point is a landmark.
        points = [tuple(vtk_pts.GetPoint(i))
                  for i in range(vtk_pts.GetNumberOfPoints())]

    logger.info("Loaded %d point(s) and %d spline(s) from %s",
                len(points), len(splines), path)
    return points, splines


def _labelmap_to_mask(img: vtk.vtkImageData, image_series: ImageSeries,
                      path: str) -> np.ndarray:
    dims = tuple(int(d) for d in image_series.dimensions)
    if tuple(img.GetDimensions()) != dims:
        raise ValueError(
            f"Label map dimensions {img.GetDimensions()} do not match the "
            f"image dimensions {dims} in {path}")
    mask = vtkfilters.getScalarsAsNumpy(img, RETURN_3D=True)
    return np.ascontiguousarray(mask.astype(np.uint8))


def load_markup_labelmap(path: str, image_series: ImageSeries) -> np.ndarray:
    """Read a label-map image file into an ``(nx, ny, nz)`` uint8 paint mask.

    The label map must share the source volume's geometry (same dimensions); its
    scalars are returned as a mask aligned with the viewer's paint arrays.
    """
    obj = fIO.readVTKFile(path)
    if not isinstance(obj, vtk.vtkImageData):
        raise IOError(
            f"{path} is not label-map image data (got {type(obj).__name__})")
    mask = _labelmap_to_mask(obj, image_series, path)
    logger.info("Loaded label map %s (%d set voxel(s))", path, int((mask > 0).sum()))
    return mask


def load_surface_as_labelmap(path: str, image_series: ImageSeries,
                             time_id: int = 0, fill_value: int = 1) -> np.ndarray:
    """Convert a closed surface to an ``(nx, ny, nz)`` uint8 paint mask.

    The surface is mapped from true world into the axis-aligned working grid and
    voxelised against the reference volume with ``fill_value`` inside the
    surface (via ngawari's ``filterSurfaceToImageStencil``).
    """
    surf = _read_polydata(path)
    grid_matrix = _world_to_grid_matrix(image_series)
    if grid_matrix is not None:
        surf = _transform_polydata(surf, grid_matrix)
    ref = image_series.get_image(time_id)
    stencil = vtkfilters.filterSurfaceToImageStencil(
        ref, surf, fill_value=int(fill_value))
    mask = _labelmap_to_mask(stencil, image_series, path)
    logger.info("Voxelised surface %s -> %d voxel(s)", path, int((mask > 0).sum()))
    return mask
