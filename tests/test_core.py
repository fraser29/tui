"""Headless tests for the data model and IO (no Qt/display required).

Run with::

    pytest tests/test_core.py
    # or
    python tests/test_core.py
"""

from __future__ import annotations

import os
import tempfile

import numpy as np
import vtk

from tui.core.image_series import ImageSeries
from tui.core.markups import Markups, Spline, _linear_resample
from tui.io import load_image_series, save_markups
from tui.state import ViewerState

HERE = os.path.dirname(os.path.abspath(__file__))
TEST_VTI = os.path.join(HERE, "..", "TEST_DATA", "test_data.vti")


def _make_volume(value: float, dims=(8, 8, 8)) -> vtk.vtkImageData:
    img = vtk.vtkImageData()
    img.SetDimensions(*dims)
    img.SetSpacing(1.0, 1.0, 1.0)
    img.SetOrigin(0.0, 0.0, 0.0)
    arr = vtk.vtkFloatArray()
    arr.SetName("PixelData")
    arr.SetNumberOfTuples(dims[0] * dims[1] * dims[2])
    arr.Fill(value)
    img.GetPointData().SetScalars(arr)
    return img


def _temporal_series(n=3) -> ImageSeries:
    return ImageSeries({float(t): _make_volume(float(t)) for t in range(n)})


# --------------------------------------------------------------------------- #
def test_fix_degenerate_spacing():
    """Single-slice series report zero spacing on the thin axis; it must be
    replaced with a non-zero value or the slice renders black (regression)."""
    from tui.io.loader import _fix_degenerate_spacing

    img = vtk.vtkImageData()
    img.SetDimensions(8, 8, 1)
    img.SetSpacing(0.5, 0.5, 0.0)   # zero z-spacing (single slice)
    _fix_degenerate_spacing(img)
    assert img.GetSpacing() == (0.5, 0.5, 0.5)   # filled with min in-plane
    # Healthy spacing is left untouched.
    img2 = vtk.vtkImageData()
    img2.SetSpacing(0.5, 0.6, 0.7)
    _fix_degenerate_spacing(img2)
    assert img2.GetSpacing() == (0.5, 0.6, 0.7)


def test_load_real_vti():
    series = load_image_series(TEST_VTI)
    assert series.n_times == 1
    assert not series.is_temporal
    assert series.dimensions == (288, 183, 226)
    assert "PixelData" in series.array_names
    assert series.default_array == "PixelData"
    lo, hi = series.scalar_range("PixelData")
    assert lo < hi


def test_as_image_series_path():
    from tui.io import as_image_series

    series = as_image_series(TEST_VTI)
    assert series.n_times == 1
    assert series.dimensions == (288, 183, 226)


def test_as_image_series_vtk_and_dict():
    from tui.io import as_image_series

    single = _make_volume(1.0)
    s1 = as_image_series(single)
    assert s1.n_times == 1
    assert s1.get_image(0) is single

    temporal = {0.0: _make_volume(0.0), 1.0: _make_volume(1.0)}
    s2 = as_image_series(temporal)
    assert s2.n_times == 2 and s2.is_temporal

    s3 = as_image_series([_make_volume(0.0), _make_volume(1.0)])
    assert s3.n_times == 2

    existing = ImageSeries({0.0: _make_volume(3.0)})
    assert as_image_series(existing) is existing


def test_image_series_geometry():
    s = _temporal_series(3)
    assert s.n_times == 3 and s.is_temporal
    assert s.dimensions == (8, 8, 8)
    assert s.middle_slice(2) == 3 or s.middle_slice(2) == 4
    assert s.slice_range(0) == (0, 7)


def test_points_interpolation_counts_equal():
    m = Markups(n_times=5)
    m.set_points(0, [(0, 0, 0), (10, 0, 0)])
    m.set_points(4, [(0, 0, 0), (10, 10, 0)])
    eff = m.effective_points(2)
    assert not eff.is_manual
    pts = eff.as_array()
    # Second point should be halfway in y between the two keyframes.
    assert np.isclose(pts[1][1], 5.0)


def test_points_interpolation_counts_differ_uses_nearest():
    m = Markups(n_times=5)
    m.set_points(0, [(0, 0, 0)])
    m.set_points(4, [(1, 1, 1), (2, 2, 2)])
    eff = m.effective_points(1)  # nearer to t=0
    assert len(eff.points) == 1


def test_spline_interpolation():
    m = Markups(n_times=5)
    s0 = m.add_spline(0)
    s0.control_points.extend([(0, 0, 0), (10, 0, 0), (10, 10, 0), (0, 10, 0)])
    s1 = m.add_spline(4)
    s1.control_points.extend([(0, 0, 5), (10, 0, 5), (10, 10, 5), (0, 10, 5)])
    eff = m.effective_splines(2)
    assert len(eff) == 1
    assert not eff[0].is_manual
    arr = np.asarray(eff[0].control_points)
    # All z should be ~2.5 (halfway between 0 and 5).
    assert np.allclose(arr[:, 2], 2.5, atol=0.5)


def test_spline_interpolation_matched_counts_keeps_handles():
    """Matched control-point counts blend directly (small editable handle set)."""
    m = Markups(n_times=11)
    m.add_spline(0, Spline(control_points=[(0, 0, 0), (1, 1, 0), (2, 0, 0)]))
    m.add_spline(10, Spline(control_points=[(0, 0, 0), (1, 3, 0), (2, 0, 0)]))
    eff = m.effective_splines(5)
    assert len(eff[0].control_points) == 3       # not resampled to the dense N
    assert np.isclose(eff[0].control_points[1][1], 2.0)  # halfway y


def test_promote_to_manual_makes_interpolated_editable():
    m = Markups(n_times=11)
    m.add_spline(0, Spline(control_points=[(0, 0, 0), (1, 1, 0), (2, 0, 0)]))
    m.add_spline(10, Spline(control_points=[(0, 0, 0), (1, 3, 0), (2, 0, 0)]))
    m.set_points(0, [(0, 0, 0)])
    m.set_points(10, [(0, 2, 0)])
    assert 5 not in m.spline_keyframes()
    assert m.promote_to_manual(5) is True
    assert 5 in m.spline_keyframes() and 5 in m.point_keyframes()
    assert m.manual_splines(5)[0].is_manual
    # Edits to the promoted frame stick (no longer recomputed each call).
    m.manual_splines(5)[0].control_points[1] = (9, 9, 0)
    assert m.effective_splines(5)[0].control_points[1] == (9, 9, 0)
    assert m.promote_to_manual(5) is False        # idempotent


def test_promote_reduces_handles_to_mean():
    """Activating a cyan spline reduces its (dense) handles to the mean manual
    control-point count."""
    m = Markups(n_times=11)
    m.add_spline(0, Spline(control_points=[(0, 0, 0), (1, 1, 0), (2, 0, 0)]))   # 3
    m.add_spline(10, Spline(control_points=[
        (0, 0, 0), (1, 3, 0), (2, 0, 0), (3, 1, 0), (4, 0, 0)]))                 # 5
    # Mismatched counts -> interpolated frame is densely resampled...
    assert len(m.effective_splines(5)[0].control_points) > 5
    # ...but promotion brings it down to the mean (4).
    assert m.promote_to_manual(5) is True
    assert len(m.manual_splines(5)[0].control_points) == 4


def test_bake_interpolation_fills_between_keyframes():
    m = Markups(n_times=11)
    m.add_spline(0, Spline(control_points=[(0, 0, 0), (1, 1, 0), (2, 0, 0)]))
    m.add_spline(10, Spline(control_points=[(0, 0, 0), (1, 3, 0), (2, 0, 0)]))
    filled = m.bake_interpolation()
    assert filled == 9                            # t=1..9
    assert m.spline_keyframes() == list(range(11))
    assert all(m.manual_splines(t)[0].is_manual for t in range(11))


def test_bake_resamples_to_mean_handle_count():
    """Baked splines take the mean handle count of the manual splines."""
    m = Markups(n_times=11)
    m.add_spline(0, Spline(control_points=[(0, 0, 0), (1, 1, 0), (2, 0, 0)]))   # 3
    m.add_spline(10, Spline(control_points=[
        (0, 0, 0), (1, 3, 0), (2, 0, 0), (3, 1, 0), (4, 0, 0)]))                 # 5
    assert m._mean_manual_handle_count() == 4
    m.bake_interpolation()
    assert len(m.manual_splines(0)[0].control_points) == 3   # manual unchanged
    assert len(m.manual_splines(10)[0].control_points) == 5
    for t in range(1, 10):                                    # baked -> mean
        assert len(m.manual_splines(t)[0].control_points) == 4


def test_periodic_interpolation_wraps():
    m = Markups(n_times=20)
    m.set_points(0, [(0, 0, 0)])
    m.set_points(10, [(0, 10, 0)])
    # Non-periodic: frames past the last keyframe snap to the nearest.
    assert m.effective_points(15).points[0][1] == 10.0
    # Periodic: t15 interpolates from t10 back to t0 (halfway -> y=5).
    m.periodic = True
    assert np.isclose(m.effective_points(15).points[0][1], 5.0)
    assert np.isclose(m.effective_points(18).points[0][1], 2.0)
    # Interior frames are unaffected by periodicity.
    assert np.isclose(m.effective_points(5).points[0][1], 5.0)


def test_periodic_bake_fills_whole_timeline():
    m = Markups(n_times=8)
    m.periodic = True
    m.add_spline(0, Spline(control_points=[(0, 0, 0), (1, 1, 0), (2, 0, 0)]))
    m.add_spline(4, Spline(control_points=[(0, 0, 0), (1, 3, 0), (2, 0, 0)]))
    m.bake_interpolation()
    assert m.spline_keyframes() == list(range(8))   # includes wrap region 5..7


def test_clear_all():
    m = Markups(n_times=3, image_shape=(4, 4, 4))
    m.set_points(0, [(1, 1, 1)])
    m.add_spline(1, Spline(control_points=[(0, 0, 0), (1, 1, 1)]))
    m.paint_mask(2)[0, 0, 0] = 1
    assert not m.is_empty()
    m.clear_all()
    assert m.is_empty()
    assert m.spline_keyframes() == [] and m.point_keyframes() == []


def test_paint_nearest_keyframe():
    shape = (8, 8, 8)
    m = Markups(n_times=5, image_shape=shape)
    mask = m.paint_mask(0)
    mask[2, 2, 2] = 1
    assert m.effective_paint(1) is not None      # nearest -> t=0 mask
    assert m.effective_paint(1)[2, 2, 2] == 1
    assert m.effective_paint(4) is not None       # still nearest available


def test_three_point_spline_is_curved_not_straight():
    """Sparse (3-point) splines must render as a real curve, not straight lines
    (regression: cubic-only fit failed for <4 points and dropped to linear)."""
    from tui.core.markups import _resample_polyline

    pts = np.array([[0, 0, 0], [1, 1, 0], [2, 0, 0]], dtype=float)
    curve = _resample_polyline(pts, 50, closed=False)
    mid = curve[len(curve) // 2]
    # The straight chord midpoint has y=0; a real spline bows toward y~1.
    assert mid[1] > 0.5, mid


def test_linear_resample():
    pts = np.array([[0, 0, 0], [10, 0, 0]], dtype=float)
    out = _linear_resample(pts, 11, closed=False)
    assert out.shape == (11, 3)
    assert np.isclose(out[5, 0], 5.0)


def test_state_voxel_roundtrip():
    s = _temporal_series(2)
    st = ViewerState(s)
    ijk = (3, 4, 5)
    world = st.voxel_to_world(ijk)
    assert st.world_to_voxel(world) == ijk


def _volume_with_extent(ext=(10, 17, 20, 27, 30, 37)) -> vtk.vtkImageData:
    img = vtk.vtkImageData()
    img.SetExtent(*ext)
    img.SetSpacing(1.0, 1.0, 1.0)
    img.SetOrigin(0.0, 0.0, 0.0)
    n = ((ext[1] - ext[0] + 1) * (ext[3] - ext[2] + 1) * (ext[5] - ext[4] + 1))
    arr = vtk.vtkFloatArray()
    arr.SetName("PixelData")
    arr.SetNumberOfTuples(n)
    arr.Fill(1.0)
    img.GetPointData().SetScalars(arr)
    return img


def test_voxel_mapping_respects_nonzero_extent():
    """World<->voxel must offset by the extent start (regression: paint landed
    at the volume edge for images whose extent did not start at 0)."""
    s = ImageSeries({0.0: _volume_with_extent()})
    st = ViewerState(s)
    # Centre of an 8^3 volume starting at extent index 10 -> array index ~3-4.
    centre_voxel = st.world_to_voxel(st.center)
    assert all(2 <= c <= 5 for c in centre_voxel), centre_voxel
    # Round-trip through the extent offset.
    assert st.world_to_voxel(st.voxel_to_world((2, 3, 4))) == (2, 3, 4)


def test_save_markups_single_and_temporal():
    s = _temporal_series(3)
    m = Markups(n_times=3, image_shape=s.dimensions)
    m.set_points(0, [(1, 1, 1), (2, 2, 2)])
    sp = m.add_spline(0)
    sp.control_points.extend([(0, 0, 0), (3, 0, 0), (3, 3, 0)])
    mask = m.paint_mask(0)
    mask[1, 1, 1] = 1
    with tempfile.TemporaryDirectory() as d:
        files = save_markups(m, s, d, prefix="test")
        assert len(files) == 3
        for f in files:
            assert os.path.exists(f)

    # Temporal: two point keyframes -> a .pvd index.
    m.set_points(2, [(5, 5, 5), (6, 6, 6)])
    with tempfile.TemporaryDirectory() as d:
        files = save_markups(m, s, d, prefix="test")
        pvds = [f for f in files if f.endswith(".pvd")]
        assert pvds, "expected a .pvd index for temporal point markups"


def _rot_z_90() -> np.ndarray:
    """90-degree rotation about z: maps (x,y,z) -> (-y, x, z)."""
    return np.array([[0.0, -1.0, 0.0],
                     [1.0, 0.0, 0.0],
                     [0.0, 0.0, 1.0]])


def test_extract_patient_orientation_builds_transform_and_flattens_grid():
    from tui.io.loader import _extract_and_normalise_orientation

    img = _make_volume(1.0)
    img.SetOrigin(0.0, 0.0, 0.0)
    D = _rot_z_90()
    dm = vtk.vtkMatrix3x3()
    for r in range(3):
        for c in range(3):
            dm.SetElement(r, c, D[r, c])
    img.SetDirectionMatrix(dm)

    M = _extract_and_normalise_orientation({0.0: img})
    assert M is not None
    assert np.allclose(M[:3, :3], D)
    # Grid is flattened back to axis-aligned so the viewer maths stay valid.
    back = img.GetDirectionMatrix()
    assert np.allclose(
        [[back.GetElement(r, c) for c in range(3)] for r in range(3)], np.eye(3))
    # Axis-aligned data returns no transform.
    assert _extract_and_normalise_orientation({0.0: _make_volume(1.0)}) is None


def test_dicom_patient_matrix_from_field_data():
    """The DICOM transform is built from ImageOrientationPatient + SliceVector
    field data (NOT the unreliable buildVTIDict direction matrix)."""
    from tui.io.loader import _dicom_patient_matrix
    from vtk.util import numpy_support

    img = _make_volume(1.0)
    img.SetOrigin(0.0, 0.0, 0.0)
    # 90-deg rotation about z: row=+x, col=+y rotated -> row=(0,1,0)? Use a clean
    # orientation whose columns are [row|col|slice].
    iop = np.array([0.0, 1.0, 0.0, -1.0, 0.0, 0.0], dtype=float)  # row, col
    sv = np.array([0.0, 0.0, 1.0], dtype=float)                   # slice normal
    for name, vec in (("ImageOrientationPatient", iop), ("SliceVector", sv)):
        arr = numpy_support.numpy_to_vtk(vec, deep=1)
        arr.SetName(name)
        img.GetFieldData().AddArray(arr)

    M = _dicom_patient_matrix({0.0: img})
    assert M is not None
    expected_D = np.column_stack([iop[0:3], iop[3:6], sv])
    assert np.allclose(M[:3, :3], expected_D)
    # A point on +x maps along the row direction (+y).
    p = np.array([1.0, 0.0, 0.0, 1.0])
    assert np.allclose((M @ p)[:3], (0.0, 1.0, 0.0), atol=1e-9)
    # Axis-aligned DICOM (identity orientation) yields no transform.
    plain = _make_volume(1.0)
    for name, vec in (("ImageOrientationPatient",
                       np.array([1.0, 0, 0, 0, 1.0, 0])),
                      ("SliceVector", np.array([0.0, 0, 1.0]))):
        arr = numpy_support.numpy_to_vtk(vec, deep=1)
        arr.SetName(name)
        plain.GetFieldData().AddArray(arr)
    assert _dicom_patient_matrix({0.0: plain}) is None


def test_markups_saved_in_true_world_coordinates():
    """A patient transform on the series must be baked into exported polydata."""
    M = np.eye(4)
    M[:3, :3] = _rot_z_90()
    s = ImageSeries({0.0: _make_volume(1.0)}, patient_matrix=M)
    assert s.has_patient_transform

    m = Markups(n_times=1, image_shape=s.dimensions)
    m.set_points(0, [(1.0, 0.0, 0.0)])

    with tempfile.TemporaryDirectory() as d:
        files = save_markups(m, s, d, prefix="world")
        vtp = next(f for f in files if f.endswith(".vtp"))
        reader = vtk.vtkXMLPolyDataReader()
        reader.SetFileName(vtp)
        reader.Update()
        out = reader.GetOutput()
        assert out.GetNumberOfPoints() == 1
        # (1,0,0) rotated 90 deg about z -> (0,1,0) in true world coordinates.
        assert np.allclose(out.GetPoint(0), (0.0, 1.0, 0.0), atol=1e-6)


def test_markups_saved_axis_aligned_when_no_transform():
    s = ImageSeries({0.0: _make_volume(1.0)})
    assert not s.has_patient_transform
    m = Markups(n_times=1, image_shape=s.dimensions)
    m.set_points(0, [(1.0, 2.0, 3.0)])
    with tempfile.TemporaryDirectory() as d:
        files = save_markups(m, s, d, prefix="plain")
        vtp = next(f for f in files if f.endswith(".vtp"))
        reader = vtk.vtkXMLPolyDataReader()
        reader.SetFileName(vtp)
        reader.Update()
        assert np.allclose(reader.GetOutput().GetPoint(0), (1.0, 2.0, 3.0), atol=1e-6)


if __name__ == "__main__":
    import traceback

    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
        except Exception:  # noqa: BLE001
            failed += 1
            print(f"FAIL  {fn.__name__}")
            traceback.print_exc()
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    raise SystemExit(1 if failed else 0)
