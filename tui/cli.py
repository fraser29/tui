"""Command-line entry point: ``tui -in <path>``."""

from __future__ import annotations

import argparse
import logging
import sys

from . import configure_logging


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="TUI",
        description="Customisable 4-panel medical image viewer (axial / sagittal / "
                    "coronal / 3D) with temporal data and markup.",
    )
    p.add_argument("-in", "--input", dest="input", required=True,
                   help="Input image: .vti/.nii/.nrrd/.mha, a .pvd time series, "
                        "or a DICOM directory.")
    p.add_argument("-a", "--array", default=None,
                   help="Point-data array to display initially.")
    p.add_argument("--example", action="store_true",
                   help="Launch the bundled ExampleViewer (demo custom buttons).")
    p.add_argument("-l", "--log-level", default="INFO",
                   help="Logging level (DEBUG, INFO, WARNING, ...). Default INFO.")
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    configure_logging(level=args.log_level)

    # Import here so ``--help`` and arg parsing stay fast/headless.
    from .app import launch, ViewerApp

    viewer_class = ViewerApp
    if args.example:
        from .examples.custom_app import ExampleViewer
        viewer_class = ExampleViewer

    try:
        return launch(args.input, viewer_class=viewer_class, array=args.array)
    except (FileNotFoundError, IOError) as exc:
        logging.getLogger("tui").error("%s", exc)
        return 2


if __name__ == "__main__":
    sys.exit(main())
