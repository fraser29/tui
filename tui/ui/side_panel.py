"""Right-hand control panel: view buttons, array selector, markup modes, custom buttons."""

from __future__ import annotations

from typing import List

from PyQt5 import QtCore, QtWidgets

from ..core.enums import MarkupMode, ViewType

CUSTOM_ROWS = 6
CUSTOM_COLS = 2


class SidePanel(QtWidgets.QWidget):
    """Self-contained control panel emitting high-level signals for the app."""

    sigMaximise = QtCore.pyqtSignal(object)        # ViewType
    sigShowGrid = QtCore.pyqtSignal()
    sigArrayChanged = QtCore.pyqtSignal(str)
    sigModeChanged = QtCore.pyqtSignal(object)     # MarkupMode
    sigAction = QtCore.pyqtSignal(str)             # named markup action
    sigPaintRadius = QtCore.pyqtSignal(int)
    sigPaintLabel = QtCore.pyqtSignal(int)
    sigShowMarkups = QtCore.pyqtSignal(bool)
    sigShowCrosshair = QtCore.pyqtSignal(bool)
    sigResetFrame = QtCore.pyqtSignal()
    sigPeriodicChanged = QtCore.pyqtSignal(bool)
    sigHelp = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumWidth(260)
        self.setMaximumWidth(340)

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(6, 6, 6, 6)
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        outer.addWidget(scroll)
        container = QtWidgets.QWidget()
        scroll.setWidget(container)
        self._layout = QtWidgets.QVBoxLayout(container)
        self._layout.setSpacing(10)

        self._build_view_group()
        self._build_array_group()
        self._build_markup_group()
        self._build_custom_group()
        self._layout.addStretch(1)
        self._build_help_button()

    # ----------------------------------------------------------- help button
    def _build_help_button(self) -> None:
        help_btn = QtWidgets.QPushButton("Help")
        help_btn.setToolTip("Show usage help: modes, mouse actions and keyboard shortcuts")
        help_btn.clicked.connect(lambda: self.sigHelp.emit())
        self._layout.addWidget(help_btn)

    # ----------------------------------------------------------- view group
    def _build_view_group(self) -> None:
        box = QtWidgets.QGroupBox("Layout")
        grid = QtWidgets.QGridLayout(box)
        view_buttons = [
            (ViewType.AXIAL, "Axial"),
            (ViewType.SAGITTAL, "Sagittal"),
            (ViewType.CORONAL, "Coronal"),
            (ViewType.VOLUME, "3D"),
        ]
        for i, (vt, label) in enumerate(view_buttons):
            btn = QtWidgets.QPushButton(label)
            btn.setToolTip(f"Maximise the {label} view")
            btn.clicked.connect(lambda _=False, v=vt: self.sigMaximise.emit(v))
            grid.addWidget(btn, i // 2, i % 2)
        grid_btn = QtWidgets.QPushButton("Grid (2x2)")
        grid_btn.setToolTip("Return to the 2x2 grid layout")
        grid_btn.clicked.connect(lambda: self.sigShowGrid.emit())
        grid.addWidget(grid_btn, 2, 0, 1, 2)
        self._layout.addWidget(box)

    # ---------------------------------------------------------- array group
    def _build_array_group(self) -> None:
        box = QtWidgets.QGroupBox("Display array")
        v = QtWidgets.QVBoxLayout(box)
        self.array_combo = QtWidgets.QComboBox()
        self.array_combo.currentTextChanged.connect(self._on_array_changed)
        v.addWidget(self.array_combo)
        self._layout.addWidget(box)

    def _on_array_changed(self, text: str) -> None:
        if text:
            self.sigArrayChanged.emit(text)

    def set_arrays(self, names: List[str], current: str = "") -> None:
        self.array_combo.blockSignals(True)
        self.array_combo.clear()
        self.array_combo.addItems(names)
        if current and current in names:
            self.array_combo.setCurrentText(current)
        self.array_combo.blockSignals(False)

    # --------------------------------------------------------- markup group
    def _build_markup_group(self) -> None:
        box = QtWidgets.QGroupBox("Markup")
        v = QtWidgets.QVBoxLayout(box)

        self._mode_group = QtWidgets.QButtonGroup(self)
        self._mode_group.setExclusive(True)
        modes = [
            (MarkupMode.NAVIGATE, "Navigate"),
            (MarkupMode.POINTS, "Add points"),
            (MarkupMode.SPLINES, "Add splines"),
            (MarkupMode.PAINT, "Paint"),
            (MarkupMode.MODIFY, "Modify"),
        ]
        tooltips = {
            MarkupMode.MODIFY: (
                "Edit existing markups: drag a handle to move it, click on a "
                "spline to add a control point, right-click a handle to delete "
                "it. Editing an interpolated (cyan) frame makes it a keyframe."),
        }
        mode_grid = QtWidgets.QGridLayout()
        for i, (mode, label) in enumerate(modes):
            btn = QtWidgets.QPushButton(label)
            btn.setCheckable(True)
            if mode in tooltips:
                btn.setToolTip(tooltips[mode])
            if mode is MarkupMode.NAVIGATE:
                btn.setChecked(True)
            btn.clicked.connect(lambda _=False, m=mode: self.sigModeChanged.emit(m))
            self._mode_group.addButton(btn)
            mode_grid.addWidget(btn, i // 2, i % 2)
        v.addLayout(mode_grid)

        self.periodic_cb = QtWidgets.QCheckBox("Periodic interpolation")
        self.periodic_cb.setToolTip(
            "Treat time as cyclic: the last keyframe interpolates back to the "
            "first (e.g. for a cardiac/respiratory cycle).")
        self.periodic_cb.toggled.connect(self.sigPeriodicChanged.emit)
        v.addWidget(self.periodic_cb)

        # Spline actions.
        spline_row = QtWidgets.QHBoxLayout()
        for label, action in (("New spline", "new_spline"),
                              ("Close spline", "close_spline")):
            b = QtWidgets.QPushButton(label)
            b.clicked.connect(lambda _=False, a=action: self.sigAction.emit(a))
            spline_row.addWidget(b)
        v.addLayout(spline_row)

        # Paint controls.
        paint_row = QtWidgets.QHBoxLayout()
        paint_row.addWidget(QtWidgets.QLabel("Brush"))
        self.radius_spin = QtWidgets.QSpinBox()
        self.radius_spin.setRange(1, 50)
        self.radius_spin.setValue(3)
        self.radius_spin.valueChanged.connect(self.sigPaintRadius.emit)
        paint_row.addWidget(self.radius_spin)
        paint_row.addWidget(QtWidgets.QLabel("Label"))
        self.label_spin = QtWidgets.QSpinBox()
        self.label_spin.setRange(1, 15)
        self.label_spin.setValue(1)
        self.label_spin.valueChanged.connect(self.sigPaintLabel.emit)
        paint_row.addWidget(self.label_spin)
        v.addLayout(paint_row)

        # Edit actions.
        edit_row = QtWidgets.QHBoxLayout()
        edit_actions = (
            ("Undo", "undo", "Undo the last markup in this frame"),
            ("Clear frame", "clear_frame", "Remove all markups in the current time step"),
            ("Clear all", "clear_all", "Remove all markups in every time step"),
        )
        for label, action, tip in edit_actions:
            b = QtWidgets.QPushButton(label)
            b.setToolTip(tip)
            b.clicked.connect(lambda _=False, a=action: self.sigAction.emit(a))
            edit_row.addWidget(b)
        v.addLayout(edit_row)

        toggle_row = QtWidgets.QHBoxLayout()
        self.show_markups_cb = QtWidgets.QCheckBox("Show markups")
        self.show_markups_cb.setChecked(True)
        self.show_markups_cb.toggled.connect(self.sigShowMarkups.emit)
        toggle_row.addWidget(self.show_markups_cb)
        v.addLayout(toggle_row)

        cross_row = QtWidgets.QHBoxLayout()
        self.crosshair_cb = QtWidgets.QCheckBox("Crosshair")
        self.crosshair_cb.setChecked(True)
        self.crosshair_cb.setToolTip(
            "Show the reslice crosshair. In Navigate mode, drag the centre to "
            "move all planes or drag a line to rotate (double-oblique).")
        self.crosshair_cb.toggled.connect(self.sigShowCrosshair.emit)
        cross_row.addWidget(self.crosshair_cb)
        reset_btn = QtWidgets.QPushButton("Reset planes")
        reset_btn.setToolTip("Restore axis-aligned (orthogonal) planes and centre")
        reset_btn.clicked.connect(lambda: self.sigResetFrame.emit())
        cross_row.addWidget(reset_btn)
        v.addLayout(cross_row)

        save_btn = QtWidgets.QPushButton("Save markups...")
        save_btn.clicked.connect(lambda: self.sigAction.emit("save"))
        v.addWidget(save_btn)

        self._layout.addWidget(box)

    # --------------------------------------------------------- custom group
    def _build_custom_group(self) -> None:
        box = QtWidgets.QGroupBox("Custom actions")
        grid = QtWidgets.QGridLayout(box)
        self.custom_buttons: List[List[QtWidgets.QPushButton]] = []
        for r in range(CUSTOM_ROWS):
            row: List[QtWidgets.QPushButton] = []
            for c in range(CUSTOM_COLS):
                btn = QtWidgets.QPushButton("")
                btn.setEnabled(False)
                btn.setMinimumHeight(34)
                btn.setSizePolicy(QtWidgets.QSizePolicy.Expanding,
                                  QtWidgets.QSizePolicy.Fixed)
                grid.addWidget(btn, r, c)
                row.append(btn)
            self.custom_buttons.append(row)
        self._layout.addWidget(box)

    def set_mode(self, mode: MarkupMode) -> None:
        """Reflect a programmatic mode change in the toggle buttons."""
        label = {
            MarkupMode.NAVIGATE: "Navigate",
            MarkupMode.POINTS: "Add points",
            MarkupMode.SPLINES: "Add splines",
            MarkupMode.PAINT: "Paint",
            MarkupMode.MODIFY: "Modify",
        }[mode]
        for b in self._mode_group.buttons():
            b.setChecked(b.text() == label)
