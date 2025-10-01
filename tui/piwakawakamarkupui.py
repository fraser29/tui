# -*- coding: utf-8 -*-

# WAS ORIGINALLY - Form implementation generated from reading ui file 'piwakawakamarkupui.ui'
# Created by: PyQt5 UI code generator 5.9.2
# 
# NOW - managed by CURSOR

from PyQt5 import QtCore, QtGui, QtWidgets
from .baseMarkupUI import BaseMarkupUI


class Ui_BASEUI(BaseMarkupUI):
    def setupUi(self, BASEUI):
        """Setup Piwakawaka-specific UI components."""
        # Call parent setup
        super().setupUi(BASEUI)
    
    def _addGraphicsViewControls(self):
        """Add Piwakawaka-specific graphics view controls."""
        # Add vertical slice slider
        self.sliceSliderLayout = QtWidgets.QVBoxLayout()
        self.sliceSliderLayout.setObjectName("sliceSliderLayout")
        
        self.sliceSliderLabel = QtWidgets.QLabel(self.centralwidget)
        self.sliceSliderLabel.setObjectName("sliceSliderLabel")
        self.sliceSliderLabel.setAlignment(QtCore.Qt.AlignCenter)
        self.sliceSliderLayout.addWidget(self.sliceSliderLabel)
        
        self.sliceSlider = QtWidgets.QSlider(self.centralwidget)
        self.sliceSlider.setOrientation(QtCore.Qt.Vertical)
        self.sliceSlider.setObjectName("sliceSlider")
        self.sliceSlider.setMinimum(0)
        self.sliceSlider.setMaximum(100)
        self.sliceSlider.setValue(50)
        self.sliceSliderLayout.addWidget(self.sliceSlider)
        
        self.sliceSliderLayout.addStretch()  # Add stretch to center the slider
        self.graphicsViewLayout.addLayout(self.sliceSliderLayout)
    
    def _addImageManipulationControls(self):
        """Add Piwakawaka-specific image manipulation controls."""
        # Orientation selector
        self.orientationLabel = QtWidgets.QLabel(self.imageManipulationGroupBox)
        self.orientationLabel.setObjectName("orientationLabel")
        self.imageManipulationButtonsLayout.addWidget(self.orientationLabel)
        
        self.orientationComboBox = QtWidgets.QComboBox(self.imageManipulationGroupBox)
        self.orientationComboBox.setObjectName("orientationComboBox")
        self.orientationComboBox.addItem("Axial")
        self.orientationComboBox.addItem("Sagittal")
        self.orientationComboBox.addItem("Coronal")
        self.orientationComboBox.addItem("Custom")
        self.imageManipulationButtonsLayout.addWidget(self.orientationComboBox)
        
        self.imManip_A = QtWidgets.QPushButton(self.imageManipulationGroupBox)
        self.imManip_A.setObjectName("imManip_A")
        self.imManip_A.setEnabled(False)
        self.imageManipulationButtonsLayout.addWidget(self.imManip_A)
        
        self.imManip_B = QtWidgets.QPushButton(self.imageManipulationGroupBox)  # rotate 90
        self.imManip_B.setObjectName("imManip_B")
        self.imageManipulationButtonsLayout.addWidget(self.imManip_B)
    
    def _addAdditionalControls(self):
        """Add Piwakawaka-specific additional controls."""
        # Select Array
        self.selectArrayComboBox = QtWidgets.QComboBox(self.centralwidget)
        self.selectArrayComboBox.setObjectName("selectArrayComboBox")
        self.rightPanelLayout.addWidget(self.selectArrayComboBox, 2, 0, 1, 1)
    
    def _addAnimationControls(self):
        """Add Piwakawaka-specific animation controls."""
        # Speed control layout
        self.speedControlLayout = QtWidgets.QHBoxLayout()
        self.speedControlLayout.setObjectName("speedControlLayout")
        
        # Speed label
        self.speedLabel = QtWidgets.QLabel(self.centralwidget)
        self.speedLabel.setObjectName("speedLabel")
        self.speedControlLayout.addWidget(self.speedLabel)
        
        # Speed slider (4 settings: 0, 1, 2, 3)
        self.speedSlider = QtWidgets.QSlider(self.centralwidget)
        self.speedSlider.setOrientation(QtCore.Qt.Horizontal)
        self.speedSlider.setObjectName("speedSlider")
        self.speedSlider.setMinimum(0)
        self.speedSlider.setMaximum(3)
        self.speedSlider.setValue(1)  # Default to medium speed
        self.speedSlider.setTickPosition(QtWidgets.QSlider.TicksBelow)
        self.speedSlider.setTickInterval(1)
        self.speedControlLayout.addWidget(self.speedSlider)
        
        self.animationLayout.addLayout(self.speedControlLayout)
    
    def _addMarkupModeItems(self):
        """Add Piwakawaka-specific markup mode items."""
        self.markupModeComboBox.addItem("Spline")

    def _retranslateSubclassSpecific(self, BASEUI):
        """Piwakawaka-specific translations."""
        _translate = QtCore.QCoreApplication.translate
        BASEUI.setWindowTitle("PIWAKAWAKA")
        
        # Slice slider
        self.sliceSliderLabel.setText(_translate("BASEUI", "Slice"))
        
        # Image manipulation controls
        self.orientationLabel.setText(_translate("BASEUI", "Slice Orientation:"))
        self.imManip_A.setText(_translate("BASEUI", "Flip Camera"))
        self.imManip_B.setText(_translate("BASEUI", "Rotate 90°"))
        
        # Markup controls
        self.imMarkupButton_A.setText(_translate("BASEUI", "Nothing"))
        self.imMarkupButton_B.setText(_translate("BASEUI", "Nothing"))
        self.closedSplineCheck.setText(_translate("BASEUI", "Closed Spline"))
        
        # Animation controls
        self.speedLabel.setText(_translate("BASEUI", "Speed:"))

