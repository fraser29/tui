# -*- coding: utf-8 -*-

# WAS ORIGINALLY - Form implementation generated from reading ui file 'tuimarkupui.ui'
# Created by: PyQt5 UI code generator 5.9.2
# 
# NOW - managed by CURSOR

from PyQt5 import QtCore, QtGui, QtWidgets
from .baseMarkupUI import BaseMarkupUI


class Ui_BASEUI(BaseMarkupUI):
    def setupUi(self, BASEUI):
        """Setup TUI-specific UI components."""
        # Call parent setup
        super().setupUi(BASEUI)
    
    def _addImageManipulationControls(self):
        """Add TUI-specific image manipulation controls."""
        self.imManip_A = QtWidgets.QPushButton(self.imageManipulationGroupBox)
        self.imManip_A.setObjectName("imManip_A")
        self.imManip_A.setEnabled(True)
        self.imManip_A.setCheckable(True)
        self.imageManipulationButtonsLayout.addWidget(self.imManip_A)
        
        self.imManip_B = QtWidgets.QPushButton(self.imageManipulationGroupBox)
        self.imManip_B.setObjectName("imManip_B")
        self.imManip_B.setEnabled(False)
        self.imageManipulationButtonsLayout.addWidget(self.imManip_B)
    
    def _addAdditionalControls(self):
        """Add TUI-specific additional controls."""
        # 3D Cursor
        self.cursor3DCheck = QtWidgets.QCheckBox(self.centralwidget)
        self.cursor3DCheck.setObjectName("cursor3DCheck")
        self.rightPanelLayout.addWidget(self.cursor3DCheck, 1, 0, 1, 1)
        
        # Select Array
        self.selectArrayComboBox = QtWidgets.QComboBox(self.centralwidget)
        self.selectArrayComboBox.setObjectName("selectArrayComboBox")
        self.rightPanelLayout.addWidget(self.selectArrayComboBox, 2, 0, 1, 1)
        
        # View Buttons
        self.viewButtonsLayout = QtWidgets.QHBoxLayout()
        self.viewButtonsLayout.setSizeConstraint(QtWidgets.QLayout.SetFixedSize)
        self.viewButtonsLayout.setObjectName("horizontalLayout_6")
        
        self.axialButton = QtWidgets.QPushButton(self.centralwidget)
        self.axialButton.setMaximumSize(QtCore.QSize(40, 40))
        self.axialButton.setCheckable(True)
        self.axialButton.setObjectName("axialButton")
        self.viewButtonsLayout.addWidget(self.axialButton)
        
        self.threeDButton = QtWidgets.QPushButton(self.centralwidget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.threeDButton.sizePolicy().hasHeightForWidth())
        self.threeDButton.setSizePolicy(sizePolicy)
        self.threeDButton.setMaximumSize(QtCore.QSize(40, 40))
        self.threeDButton.setCheckable(True)
        self.threeDButton.setObjectName("threeDButton")
        self.viewButtonsLayout.addWidget(self.threeDButton)
        
        self.saggitalButton = QtWidgets.QPushButton(self.centralwidget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.saggitalButton.sizePolicy().hasHeightForWidth())
        self.saggitalButton.setSizePolicy(sizePolicy)
        self.saggitalButton.setMaximumSize(QtCore.QSize(40, 40))
        self.saggitalButton.setCheckable(True)
        self.saggitalButton.setObjectName("saggitalButton")
        self.viewButtonsLayout.addWidget(self.saggitalButton)
        
        self.coronalButton = QtWidgets.QPushButton(self.centralwidget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.coronalButton.sizePolicy().hasHeightForWidth())
        self.coronalButton.setSizePolicy(sizePolicy)
        self.coronalButton.setMaximumSize(QtCore.QSize(40, 40))
        self.coronalButton.setCheckable(True)
        self.coronalButton.setObjectName("coronalButton")
        self.viewButtonsLayout.addWidget(self.coronalButton)
        
        self.gridViewButton = QtWidgets.QPushButton(self.centralwidget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.gridViewButton.sizePolicy().hasHeightForWidth())
        self.gridViewButton.setSizePolicy(sizePolicy)
        self.gridViewButton.setMaximumSize(QtCore.QSize(40, 40))
        self.gridViewButton.setCheckable(True)
        self.gridViewButton.setObjectName("gridButton")
        self.viewButtonsLayout.addWidget(self.gridViewButton)
        
        self.rightPanelLayout.addLayout(self.viewButtonsLayout, 3, 0, 1, 1)
    
    def _addAnimationControls(self):
        """Add TUI-specific animation controls."""
        # Speed control
        self.speedLabel = QtWidgets.QLabel(self.centralwidget)
        self.speedLabel.setObjectName("speedLabel")
        self.animationLayout.addWidget(self.speedLabel)

        self.speedSlider = QtWidgets.QSlider(self.centralwidget)
        self.speedSlider.setOrientation(QtCore.Qt.Horizontal)
        self.speedSlider.setObjectName("speedSlider")
        self.speedSlider.setMinimum(0)
        self.speedSlider.setMaximum(3)
        self.speedSlider.setTickInterval(1)
        self.speedSlider.setTickPosition(QtWidgets.QSlider.TicksBelow)
        self.animationLayout.addWidget(self.speedSlider)

    def _retranslateSubclassSpecific(self, BASEUI):
        """TUI-specific translations."""
        _translate = QtCore.QCoreApplication.translate
        BASEUI.setWindowTitle("TUI")
        
        # Image manipulation controls
        self.imManip_A.setText(_translate("BASEUI", "Toggle crosshairs"))
        self.imManip_B.setText(_translate("BASEUI", "Rotate 90°"))
        
        # Markup controls
        self.imMarkupButton_A.setText(_translate("BASEUI", "Spline markup"))
        self.imMarkupButton_B.setText(_translate("BASEUI", "Nothing"))  # TODO
        self.closedSplineCheck.setText(_translate("BASEUI", "Closed loop"))
        
        # Additional controls
        self.axialButton.setText(_translate("BASEUI", "Ax"))
        self.threeDButton.setText(_translate("BASEUI", "3D"))
        self.saggitalButton.setText(_translate("BASEUI", "Sag"))
        self.coronalButton.setText(_translate("BASEUI", "Cor"))
        self.gridViewButton.setText(_translate("BASEUI", "Grid"))
        self.cursor3DCheck.setText(_translate("BASEUI", "Show 3D Cursor"))
        
        # Animation controls
        self.speedLabel.setText(_translate("BASEUI", "Speed"))

