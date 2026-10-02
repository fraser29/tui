"""IO layer - all reading/writing goes through ngawari (``fIO``).

Nothing in the rest of the package reads or writes files directly; this module
is the single integration point with :mod:`ngawari.fIO` so that supported
formats and conventions live in one place.
"""

from .loader import (
    as_image_series,
    begin_image_series_load,
    load_image_series,
    load_pending_frames,
    merge_pending_frames,
    SUPPORTED_IMAGE_SUFFIXES,
    ImageInput,
)
from .markup_io import (
    build_mask_image,
    load_markup_labelmap,
    load_markup_labelmap_series,
    load_markup_polydata,
    load_markup_polydata_series,
    load_surface_as_labelmap,
    load_surface_as_labelmap_series,
    save_markups,
)

__all__ = [
    "as_image_series",
    "begin_image_series_load",
    "ImageInput",
    "load_image_series",
    "load_pending_frames",
    "merge_pending_frames",
    "save_markups",
    "build_mask_image",
    "load_markup_polydata",
    "load_markup_polydata_series",
    "load_markup_labelmap",
    "load_markup_labelmap_series",
    "load_surface_as_labelmap",
    "load_surface_as_labelmap_series",
    "SUPPORTED_IMAGE_SUFFIXES",
]
