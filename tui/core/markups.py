"""Markup model: per-time-step points, splines and paint, with interpolation.

Design notes
------------
* Markups are **unique to a time step** (keyed by integer ``time_id``).
* A time step that the user has actually drawn on is a *manual keyframe*.
* For a time step without a manual keyframe the model can **interpolate**
  between the nearest bracketing keyframes so that sparsely annotated 4D data
  yields a smooth markup at every frame.

Coordinates
-----------
Points and spline control points are stored in **world** coordinates (the same
space as the image), so they are independent of the current slice/array and can
be exported directly to polydata.  Paint is stored as a label **mask** in image
(voxel) space, one per keyframe.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

XYZ = Tuple[float, float, float]


# --------------------------------------------------------------------------- #
#  Value types
# --------------------------------------------------------------------------- #
@dataclass
class PointSet:
    """A set of world-space points belonging to one time step."""

    points: List[XYZ] = field(default_factory=list)
    is_manual: bool = True

    def copy(self) -> "PointSet":
        return PointSet(points=[tuple(p) for p in self.points], is_manual=self.is_manual)

    def as_array(self) -> np.ndarray:
        if not self.points:
            return np.empty((0, 3), dtype=float)
        return np.asarray(self.points, dtype=float)


@dataclass
class Spline:
    """A spline defined by ordered world-space control points."""

    control_points: List[XYZ] = field(default_factory=list)
    closed: bool = False
    is_manual: bool = True
    label: str = ""

    def copy(self) -> "Spline":
        return Spline(
            control_points=[tuple(p) for p in self.control_points],
            closed=self.closed,
            is_manual=self.is_manual,
            label=self.label,
        )

    def as_array(self) -> np.ndarray:
        if not self.control_points:
            return np.empty((0, 3), dtype=float)
        return np.asarray(self.control_points, dtype=float)

    def sampled(self, n_points: int = 100) -> np.ndarray:
        """Return a dense curve through the control points."""
        return _resample_polyline(self.as_array(), n_points, self.closed)


# --------------------------------------------------------------------------- #
#  Resampling / interpolation helpers
# --------------------------------------------------------------------------- #
def _resample_polyline(pts: np.ndarray, n: int, closed: bool) -> np.ndarray:
    """Resample an ordered point list to ``n`` points.

    Tries a smooth parametric spline whose degree adapts to the number of
    control points (cubic for >=4, quadratic for 3), so even sparse splines
    render as actual curves rather than straight handle-to-handle segments.
    Falls back to linear arc-length resampling for 2 points or on any error.
    """
    pts = np.asarray(pts, dtype=float)
    if len(pts) == 0:
        return np.empty((0, 3), dtype=float)
    if len(pts) == 1 or n <= 1:
        return np.repeat(pts[:1], n, axis=0)
    if len(pts) >= 3:
        try:
            return _smooth_spline(pts, n, closed)
        except Exception as exc:  # noqa: BLE001 - robust fallback for sparse handles
            logger.debug("spline resample fell back to linear: %s", exc)
    return _linear_resample(pts, n, closed)


def _smooth_spline(pts: np.ndarray, n: int, closed: bool) -> np.ndarray:
    """Parametric B-spline through ``pts`` with a degree-adaptive fit.

    Uses ``scipy.interpolate.splprep`` directly (rather than the fixed-cubic
    ngawari helper) so 3-point splines fit a quadratic curve instead of failing
    and dropping to straight lines.
    """
    from scipy import interpolate

    if closed:
        pts = np.vstack([pts, pts[:1]])           # close the loop for periodicity
    k = min(3, len(pts) - 1)                       # cubic, else quadratic/linear
    tck, u = interpolate.splprep(
        pts.T, s=0.0, k=k, per=1 if closed else 0)
    uu = np.linspace(u.min(), u.max(), n)
    out = interpolate.splev(uu, tck)
    return np.asarray(out, dtype=float).T


def _linear_resample(pts: np.ndarray, n: int, closed: bool) -> np.ndarray:
    work = np.vstack([pts, pts[:1]]) if closed else pts
    deltas = np.diff(work, axis=0)
    seg = np.sqrt((deltas ** 2).sum(axis=1))
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    total = cum[-1]
    if total <= 0:
        return np.repeat(work[:1], n, axis=0)
    targets = np.linspace(0.0, total, n)
    out = np.empty((n, 3), dtype=float)
    for d in range(3):
        out[:, d] = np.interp(targets, cum, work[:, d])
    return out


def _lerp_arrays(a: np.ndarray, b: np.ndarray, frac: float) -> np.ndarray:
    return a * (1.0 - frac) + b * frac


# --------------------------------------------------------------------------- #
#  Markup model
# --------------------------------------------------------------------------- #
class Markups:
    """Holds all markups for every time step and serves interpolated results."""

    def __init__(self, n_times: int = 1, image_shape: Optional[Tuple[int, int, int]] = None):
        """``image_shape`` is the numpy (k, j, i) shape used for paint masks."""
        self.n_times = max(1, int(n_times))
        self.image_shape = image_shape  # (nz, ny, nx) numpy order, or None
        self.periodic = False  # cyclic time: last keyframe interpolates to first
        self._points: Dict[int, PointSet] = {}
        self._splines: Dict[int, List[Spline]] = {}
        self._paint: Dict[int, np.ndarray] = {}
        self._spline_sample_n = 80  # density used when interpolating splines

    # ------------------------------------------------------------- bookkeeping
    def set_n_times(self, n_times: int) -> None:
        self.n_times = max(1, int(n_times))

    def clear_all(self) -> None:
        self._points.clear()
        self._splines.clear()
        self._paint.clear()

    def clear_time(self, time_id: int) -> None:
        self._points.pop(time_id, None)
        self._splines.pop(time_id, None)
        self._paint.pop(time_id, None)

    def manual_time_ids(self) -> List[int]:
        ids = set(self._points) | set(self._splines) | set(self._paint)
        return sorted(ids)

    def point_keyframes(self) -> List[int]:
        return sorted(self._points)

    def spline_keyframes(self) -> List[int]:
        return sorted(self._splines)

    def paint_keyframes(self) -> List[int]:
        return sorted(self._paint)

    # ------------------------------------------------------------------ points
    def add_point(self, time_id: int, xyz: XYZ) -> None:
        ps = self._points.setdefault(time_id, PointSet(is_manual=True))
        ps.points.append(tuple(float(c) for c in xyz))
        ps.is_manual = True

    def set_points(self, time_id: int, points: List[XYZ]) -> None:
        self._points[time_id] = PointSet(
            points=[tuple(float(c) for c in p) for p in points], is_manual=True
        )

    def remove_last_point(self, time_id: int) -> None:
        ps = self._points.get(time_id)
        if ps and ps.points:
            ps.points.pop()
            if not ps.points:
                self._points.pop(time_id, None)

    def clear_points(self, time_id: int) -> None:
        self._points.pop(time_id, None)

    def manual_points(self, time_id: int) -> Optional[PointSet]:
        return self._points.get(time_id)

    def _bracket_frac(self, keys: List[int], t: int
                      ) -> Tuple[Optional[int], Optional[int], float]:
        """Return ``(lo, hi, frac)`` for interpolating at ``t``.

        ``frac`` runs 0->1 from ``lo`` to ``hi``.  ``lo == hi`` means "use that
        keyframe verbatim" (nearest).  When :attr:`periodic` is set and ``t``
        falls outside ``[keys[0], keys[-1]]`` the bracket wraps across the
        timeline boundary (last keyframe -> first keyframe).
        """
        if not keys:
            return None, None, 0.0
        lo, hi = _bracket(keys, t)
        if lo is not None and hi is not None:
            return lo, hi, (t - lo) / (hi - lo)
        if not self.periodic or len(keys) == 1:
            # Extend with the nearest available endpoint (no wrap).
            nearest = hi if lo is None else lo
            return nearest, nearest, 0.0
        # Periodic wrap: interpolate from the last keyframe to the first.
        last, first = keys[-1], keys[0]
        period = max(self.n_times, last + 1)
        gap = (first - last) % period
        if gap == 0:
            return last, last, 0.0
        return last, first, ((t - last) % period) / gap

    def effective_points(self, time_id: int) -> PointSet:
        """Points for ``time_id`` - manual if present, else interpolated."""
        if time_id in self._points:
            return self._points[time_id]
        lo, hi, frac = self._bracket_frac(sorted(self._points), time_id)
        if lo is None:
            return PointSet(is_manual=False)
        if lo == hi:
            return PointSet(points=list(self._points[lo].points), is_manual=False)
        a, b = self._points[lo].as_array(), self._points[hi].as_array()
        if len(a) == len(b) and len(a) > 0:
            blended = _lerp_arrays(a, b, frac)
            return PointSet(points=[tuple(p) for p in blended], is_manual=False)
        # Counts differ -> snap to nearest keyframe (no sensible correspondence).
        nearest = lo if frac <= 0.5 else hi
        return PointSet(points=list(self._points[nearest].points), is_manual=False)

    # ----------------------------------------------------------------- splines
    def add_spline(self, time_id: int, spline: Optional[Spline] = None,
                   closed: bool = False) -> Spline:
        """Append (and return) a spline for ``time_id``.

        The returned object is mutable: callers may append control points to it
        directly while the user is drawing.
        """
        spline = spline or Spline(closed=closed, is_manual=True)
        spline.is_manual = True
        self._splines.setdefault(time_id, []).append(spline)
        return spline

    def manual_splines(self, time_id: int) -> List[Spline]:
        return self._splines.get(time_id, [])

    def remove_last_spline(self, time_id: int) -> None:
        lst = self._splines.get(time_id)
        if lst:
            lst.pop()
            if not lst:
                self._splines.pop(time_id, None)

    def clear_splines(self, time_id: int) -> None:
        self._splines.pop(time_id, None)

    def effective_splines(self, time_id: int) -> List[Spline]:
        """Splines for ``time_id`` - manual if present, else interpolated.

        Splines are matched across keyframes by list index.  Matched pairs are
        resampled to a common density and linearly interpolated; unmatched
        splines fall back to the nearest keyframe.
        """
        if time_id in self._splines:
            return self._splines[time_id]
        lo, hi, frac = self._bracket_frac(sorted(self._splines), time_id)
        if lo is None:
            return []
        if lo == hi:
            return [s.copy() for s in _as_interp(self._splines[lo])]
        a_list, b_list = self._splines[lo], self._splines[hi]
        out: List[Spline] = []
        n = self._spline_sample_n
        for idx in range(max(len(a_list), len(b_list))):
            if idx < len(a_list) and idx < len(b_list):
                sa, sb = a_list[idx], b_list[idx]
                ca, cb = sa.as_array(), sb.as_array()
                if len(ca) == len(cb) and len(ca) > 0:
                    # Matching control-point counts: blend the control points
                    # directly so the result keeps a small, editable handle set.
                    blended = _lerp_arrays(ca, cb, frac)
                else:
                    # Counts differ: resample to a common density and blend.
                    pa = _resample_polyline(ca, n, sa.closed)
                    pb = _resample_polyline(cb, n, sb.closed)
                    if len(pa) == 0 or len(pb) == 0:
                        continue
                    blended = _lerp_arrays(pa, pb, frac)
                out.append(Spline(
                    control_points=[tuple(p) for p in blended],
                    closed=sa.closed and sb.closed,
                    is_manual=False,
                ))
            else:
                src = a_list[idx] if idx < len(a_list) else b_list[idx]
                c = src.copy()
                c.is_manual = False
                out.append(c)
        return out

    # ----------------------------------------------------- promote / bake
    def promote_to_manual(self, time_id: int) -> bool:
        """Materialise the *interpolated* markups at ``time_id`` as a keyframe.

        Used when the user starts editing an interpolated (cyan) frame: the
        interpolated points/splines are copied into an editable manual keyframe
        so subsequent edits stick (and stop being recomputed each refresh).
        Returns ``True`` if anything was promoted.
        """
        changed = False
        if time_id not in self._points:
            ps = self.effective_points(time_id)
            if ps.points:
                self._points[time_id] = PointSet(
                    points=[tuple(p) for p in ps.points], is_manual=True)
                changed = True
        if time_id not in self._splines:
            sl = self.effective_splines(time_id)
            if sl:
                # Reduce the (possibly dense) interpolated handles to the mean
                # control-point count of the user-drawn splines, so an activated
                # cyan spline is as easy to edit as a hand-drawn one.
                target_n = self._mean_manual_handle_count()
                self._splines[time_id] = [
                    _resample_spline(_as_manual_copy(s), target_n) for s in sl]
                changed = True
        return changed

    def bake_interpolation(self) -> int:
        """Convert interpolated frames between keyframes into manual keyframes.

        For both points and splines, every time step lying *between* the first
        and last keyframe that is not already a manual keyframe is filled with a
        concrete (editable) copy of its interpolated result.  Returns the number
        of frames filled.  Paint masks are not baked (label blends are
        meaningless and copying volumes per frame is expensive).

        Newly created splines are resampled to the *mean* control-point count of
        the user-drawn (manual) splines, so every baked frame has a consistent,
        editable handle count.
        """
        filled = 0
        pk = self.point_keyframes()
        if len(pk) >= 2:
            for t in self._bake_range(pk):
                if t not in self._points:
                    ps = self.effective_points(t)
                    if ps.points:
                        self._points[t] = PointSet(
                            points=[tuple(p) for p in ps.points], is_manual=True)
                        filled += 1
        sk = self.spline_keyframes()
        if len(sk) >= 2:
            target_n = self._mean_manual_handle_count()  # before adding baked frames
            for t in self._bake_range(sk):
                if t not in self._splines:
                    sl = self.effective_splines(t)
                    if sl:
                        self._splines[t] = [
                            _resample_spline(_as_manual_copy(s), target_n) for s in sl]
                        filled += 1
        return filled

    def _bake_range(self, keys: List[int]) -> range:
        """Frames to fill: the whole timeline if periodic, else between keys."""
        if self.periodic:
            return range(max(self.n_times, keys[-1] + 1))
        return range(keys[0], keys[-1] + 1)

    def _mean_manual_handle_count(self) -> int:
        """Mean number of control points across all user-drawn splines."""
        counts = [len(s.control_points)
                  for splines in self._splines.values() for s in splines
                  if s.control_points]
        if not counts:
            return 0
        return int(round(sum(counts) / len(counts)))

    # ------------------------------------------------------------------- paint
    def paint_mask(self, time_id: int, create: bool = True) -> Optional[np.ndarray]:
        """Return the manual paint mask for ``time_id`` (numpy k,j,i, uint8)."""
        if time_id in self._paint:
            return self._paint[time_id]
        if not create:
            return None
        if self.image_shape is None:
            raise RuntimeError("Markups.image_shape must be set before painting")
        mask = np.zeros(self.image_shape, dtype=np.uint8)
        self._paint[time_id] = mask
        return mask

    def set_paint_mask(self, time_id: int, mask: np.ndarray) -> None:
        self._paint[time_id] = mask.astype(np.uint8)

    def clear_paint(self, time_id: int) -> None:
        self._paint.pop(time_id, None)

    def has_paint(self, time_id: int) -> bool:
        m = self._paint.get(time_id)
        return m is not None and bool(m.any())

    def effective_paint(self, time_id: int) -> Optional[np.ndarray]:
        """Paint mask for ``time_id`` - manual if present, else nearest keyframe.

        Masks are not blended (a half-blended label is meaningless); the nearest
        annotated frame is used instead.
        """
        if time_id in self._paint:
            return self._paint[time_id]
        keys = sorted(self._paint)
        if not keys:
            return None
        nearest = min(keys, key=lambda k: abs(k - time_id))
        return self._paint[nearest]

    # ------------------------------------------------------------------- query
    def is_empty(self, time_id: Optional[int] = None) -> bool:
        if time_id is None:
            return not (self._points or self._splines or self._paint)
        return not (
            time_id in self._points
            or time_id in self._splines
            or self.has_paint(time_id)
        )

    def summary(self) -> Dict[str, List[int]]:
        return {
            "points": self.point_keyframes(),
            "splines": self.spline_keyframes(),
            "paint": self.paint_keyframes(),
        }


# --------------------------------------------------------------------------- #
#  module helpers
# --------------------------------------------------------------------------- #
def _bracket(sorted_keys: List[int], t: int) -> Tuple[Optional[int], Optional[int]]:
    """Return the (lower, upper) keyframes bracketing ``t`` (exclusive)."""
    lo = hi = None
    for k in sorted_keys:
        if k < t:
            lo = k
        elif k > t:
            hi = k
            break
    return lo, hi


def _as_interp(splines: List[Spline]) -> List[Spline]:
    out = []
    for s in splines:
        c = s.copy()
        c.is_manual = False
        out.append(c)
    return out


def _as_manual_copy(spline: Spline) -> Spline:
    c = spline.copy()
    c.is_manual = True
    return c


def _resample_spline(spline: Spline, n: int) -> Spline:
    """Return ``spline`` with its control points resampled to ``n`` (if useful)."""
    if n >= 2 and len(spline.control_points) >= 2 and len(spline.control_points) != n:
        pts = _resample_polyline(spline.as_array(), n, spline.closed)
        spline.control_points = [tuple(p) for p in pts]
    return spline
