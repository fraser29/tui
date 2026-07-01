"""TUI - a customisable 4-panel medical image viewer.

The package is organised so that the heavy lifting (data model, IO and markup
logic) is decoupled from the Qt/VTK presentation layer.  This keeps the model
fully testable without a display and makes the viewer straightforward to extend.

Typical library use::

    from tui import launch, ViewerApp

    class MyViewer(ViewerApp):
        def customise(self):
            self.set_custom_button(0, 0, "Save ROI", self.save_roi)

        def save_roi(self):
            self.save_markups("/tmp/roi")

    launch("/path/to/data.vti", viewer_class=MyViewer)

The data model (:mod:`tui.core`) and IO (:mod:`tui.io`) can be imported
and used without ever importing Qt.
"""

from __future__ import annotations

import logging

__version__ = "0.1.0"
__author__ = "Fraser M. Callaghan"

# Library convention: never configure logging on import - host apps own it.
logging.getLogger(__name__).addHandler(logging.NullHandler())

# Lightweight, dependency-free exports (no Qt/VTK import side effects here).
from .core.enums import Orientation, ViewType, MarkupMode  # noqa: E402
from .core.image_series import ImageSeries  # noqa: E402
from .core.markups import Markups, PointSet, Spline  # noqa: E402
from .io.loader import as_image_series  # noqa: E402

__all__ = [
    "__version__",
    "Orientation",
    "ViewType",
    "MarkupMode",
    "ImageSeries",
    "Markups",
    "PointSet",
    "Spline",
    "configure_logging",
    "set_log_level",
    "as_image_series",
    # The following are imported lazily to avoid pulling in Qt/VTK unless needed.
    "ViewerApp",
    "launch",
    "launch_viewer",
]


def set_log_level(level):
    """Set the log level for all ``tui`` loggers."""
    logging.getLogger("tui").setLevel(level)


def configure_logging(level=logging.INFO, fmt=None):
    """Attach a :class:`logging.StreamHandler` to the ``tui`` logger.

    Idempotent: reuses an existing stream handler so a host application that
    configured DEBUG before importing submodules is not reset to INFO.
    """
    if isinstance(level, str):
        level = getattr(logging, level.upper())
    if fmt is None:
        fmt = "%(asctime)s  %(name)-28s  %(levelname)-8s  %(message)s"
    logger = logging.getLogger("tui")
    handler = None
    for h in logger.handlers:
        if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler):
            handler = h
            break
    if handler is None:
        handler = logging.StreamHandler()
        logger.addHandler(handler)
    handler.setFormatter(logging.Formatter(fmt))
    logger.setLevel(level)


def __getattr__(name):
    """Lazily expose the Qt-dependent entry points.

    Importing :data:`ViewerApp` or :func:`launch` only pulls in Qt/VTK on
    first access, keeping ``import tui`` cheap and headless-friendly.
    """
    if name in ("ViewerApp", "launch", "launch_viewer"):
        from .app import ViewerApp, launch, launch_viewer

        return {"ViewerApp": ViewerApp, "launch": launch,
                "launch_viewer": launch_viewer}[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
