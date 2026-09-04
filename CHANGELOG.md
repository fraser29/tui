# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.2]

### Feature

- improved interaction when paint/mask is shown. 

## [0.2.1]

### Changed

- `spydcmtk` is a required dependency (the optional `[dicom]` extra is removed).

## [0.2.0] - 2026-07-01

Clean-room rewrite of the viewer. All APIs and behaviour from 0.1.x are breaking.

### Added

- Four-panel PyQt5 + VTK viewer (axial / sagittal / coronal / 3D) with a time slider for 4D data.
- Double-oblique reslice frame: crosshair translate and rotate, planes stay mutually perpendicular.
- Point, spline, and 3D spherical-brush paint markups, unique per time step, with interpolation between keyframes.
- Modify mode, periodic interpolation, and markup export in true patient / world coordinates.
- Subclassable `ViewerApp` with a 6×2 custom button grid.
- DICOM directory loading via `spydcmtk`.
- File-menu load and export of markups; load polydata and labelmaps from PVD; PVD export.
- Keyboard shortcuts for markup modes, save, undo, reset planes, and clear frames.
- Help / shortcuts dialog, cursor-value overlay, and paint threshold limits.
- Work-directory setting in the side panel.

### Changed

- Headless model (`tui.core`, `tui.state`) separated from Qt/VTK views; all file IO goes through `ngawari.fIO`.

## [0.1.1] - 2025-10-28

Last release of the pre-rewrite viewer.
