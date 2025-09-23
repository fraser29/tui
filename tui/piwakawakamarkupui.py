# -*- coding: utf-8 -*-

# WAS ORIGINALLY - Form implementation generated from reading ui file 'piwakawakamarkupui.ui'
# Created by: PyQt5 UI code generator 5.9.2
# 
# NOW - managed by CURSOR

from PyQt5 import QtCore, QtGui, QtWidgets
import os
import site
# Get the site-packages directory
site_packages = site.getsitepackages()[0]
qt_plugins_path = os.path.join(site_packages, 'PyQt5', 'Qt5', 'plugins')
os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = qt_plugins_path


class Ui_BASEUI(object):
    def setupUi(self, BASEUI):
        BASEUI.setObjectName("BASEUI")
        BASEUI.resize(1260, 1027)
        self.centralwidget = QtWidgets.QWidget(BASEUI)
        self.centralwidget.setObjectName("centralwidget")
        self.mainLayout = QtWidgets.QGridLayout(self.centralwidget)
        self.mainLayout.setObjectName("gridLayout_5")
        self.leftPanelLayout = QtWidgets.QVBoxLayout()
        self.leftPanelLayout.setObjectName("verticalLayout_2")
        self.graphicsViewLayout = QtWidgets.QHBoxLayout()
        self.graphicsViewLayout.setObjectName("horizontalLayout_3")
        self.graphicsView = QtWidgets.QGraphicsView(self.centralwidget)
        sizePolicy = QtWidgets.QSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.graphicsView.sizePolicy().hasHeightForWidth())
        self.graphicsView.setSizePolicy(sizePolicy)
        self.graphicsView.setMinimumSize(QtCore.QSize(900, 900))
        self.graphicsView.setAutoFillBackground(True)
        self.graphicsView.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.graphicsView.setFrameShadow(QtWidgets.QFrame.Plain)
        brush = QtGui.QBrush(QtGui.QColor(0, 0, 0))
        brush.setStyle(QtCore.Qt.SolidPattern)
        self.graphicsView.setBackgroundBrush(brush)
        self.graphicsView.setObjectName("graphicsView")
        self.graphicsViewLayout.addWidget(self.graphicsView)
        
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
        
        self.verticalLayout = QtWidgets.QVBoxLayout()
        self.verticalLayout.setObjectName("verticalLayout")
        self.label_4 = QtWidgets.QLabel(self.centralwidget)
        self.label_4.setObjectName("label_4")
        self.verticalLayout.addWidget(self.label_4)
        self.graphicsViewLayout.addLayout(self.verticalLayout)
        self.leftPanelLayout.addLayout(self.graphicsViewLayout)
        self.timeControlLayout = QtWidgets.QHBoxLayout()
        self.timeControlLayout.setObjectName("horizontalLayout")
        self.label_3 = QtWidgets.QLabel(self.centralwidget)
        self.label_3.setObjectName("label_3")
        self.timeControlLayout.addWidget(self.label_3)
        self.timeSlider = QtWidgets.QSlider(self.centralwidget)
        self.timeSlider.setOrientation(QtCore.Qt.Horizontal)
        self.timeSlider.setObjectName("timeSlider")
        self.timeControlLayout.addWidget(self.timeSlider)
        self.timeLabel = QtWidgets.QLabel(self.centralwidget)
        self.timeLabel.setObjectName("timeLabel")
        self.timeControlLayout.addWidget(self.timeLabel)
        self.leftPanelLayout.addLayout(self.timeControlLayout)
        self.mainLayout.addLayout(self.leftPanelLayout, 0, 0, 1, 1)

        # Create a container widget for the right panel
        self.rightPanelWidget = QtWidgets.QWidget(self.centralwidget)
        self.rightPanelWidget.setMaximumWidth(300)  # Set the desired maximum width here

        # Create the right panel layout
        self.rightPanelLayout = QtWidgets.QGridLayout(self.rightPanelWidget)
        self.rightPanelLayout.setObjectName("gridLayout_4")
        #
        #
        #
        # IMAGE MANIPULATION
        self.imageManipulationGroupBox = QtWidgets.QGroupBox(self.centralwidget)
        self.imageManipulationGroupBox.setObjectName("imageManipulationGroupBox")
        self.imageManipulationControlLayout = QtWidgets.QGridLayout(self.imageManipulationGroupBox)
        self.imageManipulationControlLayout.setObjectName("gridLayout_2")
        self.imageManipulationButtonsLayout = QtWidgets.QVBoxLayout()
        self.imageManipulationButtonsLayout.setObjectName("verticalLayout_4")
        self.imManip_A = QtWidgets.QPushButton(self.imageManipulationGroupBox)
        self.imManip_A.setObjectName("Does nothing")
        self.imageManipulationButtonsLayout.addWidget(self.imManip_A)
        #
        self.imManip_B = QtWidgets.QPushButton(self.imageManipulationGroupBox)
        self.imManip_B.setObjectName("Does nothing")
        self.imageManipulationButtonsLayout.addWidget(self.imManip_B)
        self.imageManipulationControlLayout.addLayout(self.imageManipulationButtonsLayout, 0, 0, 1, 1)
        self.rightPanelLayout.addWidget(self.imageManipulationGroupBox, 0, 0, 1, 1)
        #
        #
        #
        #
        # Select Array
        self.selectArrayComboBox = QtWidgets.QComboBox(self.centralwidget)
        self.selectArrayComboBox.setObjectName("selectArrayComboBox")
        self.rightPanelLayout.addWidget(self.selectArrayComboBox, 2, 0, 1, 1)
        #
        #
        #
        #
        # IMAGE MARKUP
        self.markupGroupBox = QtWidgets.QGroupBox(self.centralwidget)
        self.markupGroupBox.setObjectName("imageMarkupGroupBox")
        self.imageMarkupControlLayout = QtWidgets.QGridLayout(self.markupGroupBox)
        self.imageMarkupControlLayout.setObjectName("gridLayout_2")
        self.imageMarkupButtonsLayout = QtWidgets.QVBoxLayout()
        self.imageMarkupButtonsLayout.setObjectName("verticalLayout_4")
        self.imMarkupButton_A = QtWidgets.QPushButton(self.markupGroupBox)
        self.imMarkupButton_A.setObjectName("Does nothing")
        self.imageMarkupButtonsLayout.addWidget(self.imMarkupButton_A)
        #
        self.imMarkupButton_B = QtWidgets.QPushButton(self.markupGroupBox)
        self.imMarkupButton_B.setObjectName("Does nothing")
        self.imageMarkupButtonsLayout.addWidget(self.imMarkupButton_B)
        
        # Add markup mode controls
        self.markupModeLayout = QtWidgets.QVBoxLayout()
        self.markupModeLayout.setObjectName("markupModeLayout")
        
        # Point/Spline mode toggle
        self.markupModeLabel = QtWidgets.QLabel(self.markupGroupBox)
        self.markupModeLabel.setObjectName("markupModeLabel")
        self.markupModeLayout.addWidget(self.markupModeLabel)
        
        self.markupModeComboBox = QtWidgets.QComboBox(self.markupGroupBox)
        self.markupModeComboBox.setObjectName("markupModeComboBox")
        self.markupModeComboBox.addItem("Point")
        self.markupModeComboBox.addItem("Spline")
        self.markupModeLayout.addWidget(self.markupModeComboBox)
        
        # Closed spline checkbox
        self.closedSplineCheck = QtWidgets.QCheckBox(self.markupGroupBox)
        self.closedSplineCheck.setObjectName("closedSplineCheck")
        self.closedSplineCheck.setChecked(True)  # Default to closed
        self.markupModeLayout.addWidget(self.closedSplineCheck)
        
        self.imageMarkupButtonsLayout.addLayout(self.markupModeLayout)
        self.imageMarkupControlLayout.addLayout(self.imageMarkupButtonsLayout, 0, 0, 1, 1)
        self.rightPanelLayout.addWidget(self.markupGroupBox, 4, 0, 1, 1)
        #
        #
        # 
        spacerItem1 = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.rightPanelLayout.addItem(spacerItem1, 5, 0, 1, 1)
        #
        #
        # Add Customised Buttons Label
        self.customButtonsLabel = QtWidgets.QLabel(self.centralwidget)
        self.customButtonsLabel.setObjectName("customButtonsLabel")
        self.rightPanelLayout.addWidget(self.customButtonsLabel, 6, 0, 1, 1)

        # CUSTOMISABLE BUTTONS
        self.pushButtonsLayout = QtWidgets.QGridLayout()
        self.pushButtonsLayout.setObjectName("gridLayout_3")
        self.modPushButtons = []
        for i in range(12):
            button = QtWidgets.QPushButton(self.centralwidget)
            button.setObjectName(f"button{i+1}")
            self.pushButtonsLayout.addWidget(button, i//2, i%2, 1, 1)
            self.modPushButtons.append(button)
        self.rightPanelLayout.addLayout(self.pushButtonsLayout, 7, 0, 1, 1)

        # Add Customised Sliders Label
        self.customSlidersLabel = QtWidgets.QLabel(self.centralwidget)
        self.customSlidersLabel.setObjectName("customSlidersLabel")
        self.rightPanelLayout.addWidget(self.customSlidersLabel, 8, 0, 1, 1)

        # CUSTOMISABLE SLIDERS
        self.slidersLayout = QtWidgets.QVBoxLayout()
        self.slidersLayout.setObjectName("slidersLayout")

        # Create 4 sliders with labels
        self.sliders = []
        self.sliderLabels = []
        for i in range(2):
            # Create horizontal layout for each slider+label pair
            sliderHLayout = QtWidgets.QHBoxLayout()
            
            # Create and add label
            label = QtWidgets.QLabel(self.centralwidget)
            label.setObjectName(f"sliderLabel_{i+1}")
            sliderHLayout.addWidget(label)
            self.sliderLabels.append(label)
            
            # Create and add slider
            slider = QtWidgets.QSlider(self.centralwidget)
            slider.setOrientation(QtCore.Qt.Horizontal)
            slider.setObjectName(f"slider_{i+1}")
            slider.setMinimum(0)
            slider.setMaximum(100)
            sliderHLayout.addWidget(slider)
            self.sliders.append(slider)
            
            # Add the horizontal layout to the main sliders layout
            self.slidersLayout.addLayout(sliderHLayout)

        self.rightPanelLayout.addLayout(self.slidersLayout, 9, 0, 1, 1)

        # Add the right panel widget to the main layout
        self.mainLayout.addWidget(self.rightPanelWidget, 0, 1, 1, 1)

        self.workingDirLayout = QtWidgets.QHBoxLayout()
        self.workingDirLayout.setObjectName("horizontalLayout_7")
        self.label_5 = QtWidgets.QLabel(self.centralwidget)
        self.label_5.setObjectName("label_5")
        self.workingDirLayout.addWidget(self.label_5)
        self.workingDirLineEdit = QtWidgets.QLineEdit(self.centralwidget)
        self.workingDirLineEdit.setObjectName("workingDirLineEdit")
        self.workingDirLayout.addWidget(self.workingDirLineEdit)
        self.workingDirToolButton = QtWidgets.QToolButton(self.centralwidget)
        self.workingDirToolButton.setObjectName("workingDirToolButton")
        self.workingDirLayout.addWidget(self.workingDirToolButton)
        self.mainLayout.addLayout(self.workingDirLayout, 1, 0, 1, 1)
        BASEUI.setCentralWidget(self.centralwidget)
        self.menubar = QtWidgets.QMenuBar(BASEUI)
        self.menubar.setGeometry(QtCore.QRect(0, 0, 1260, 22))
        self.menubar.setObjectName("menubar")
        self.menuFile = QtWidgets.QMenu(self.menubar)
        self.menuFile.setObjectName("menuFile")
        self.menuLoad = QtWidgets.QMenu(self.menuFile)
        self.menuLoad.setObjectName("menuLoad")
        BASEUI.setMenuBar(self.menubar)
        self.statusbar = QtWidgets.QStatusBar(BASEUI)
        self.statusbar.setObjectName("statusbar")
        BASEUI.setStatusBar(self.statusbar)
        self.actionDicom = QtWidgets.QAction(BASEUI)
        self.actionDicom.setObjectName("actionDicom")
        self.actionVTK_Image = QtWidgets.QAction(BASEUI)
        self.actionVTK_Image.setObjectName("actionVTK_Image")
        self.actionQuit = QtWidgets.QAction(BASEUI)
        self.actionQuit.setObjectName("actionQuit")
        self.menuLoad.addAction(self.actionDicom)
        self.menuLoad.addAction(self.actionVTK_Image)
        self.menuFile.addAction(self.menuLoad.menuAction())
        self.menuFile.addAction(self.actionQuit)
        self.menubar.addAction(self.menuFile.menuAction())

        self.retranslateUi(BASEUI)
        QtCore.QMetaObject.connectSlotsByName(BASEUI)

    def retranslateUi(self, BASEUI):
        _translate = QtCore.QCoreApplication.translate
        BASEUI.setWindowTitle("PIWAKAWAKA")
        self.label_3.setText(_translate("BASEUI", "Time"))
        self.timeLabel.setText(_translate("BASEUI", "0/0 [0.0]"))
        self.sliceSliderLabel.setText(_translate("BASEUI", "Slice"))
        #
        self.imageManipulationGroupBox.setTitle(_translate("BASEUI", "Image manipulation"))
        self.imManip_A.setText(_translate("BASEUI", "Nothing"))
        self.imManip_B.setText(_translate("BASEUI", "Nothing"))
        #
        self.markupGroupBox.setTitle(_translate("BASEUI", "Image markup"))
        self.imMarkupButton_A.setText(_translate("BASEUI", "Nothing"))
        self.imMarkupButton_B.setText(_translate("BASEUI", "Nothing"))
        self.markupModeLabel.setText(_translate("BASEUI", "Markup Mode:"))
        self.closedSplineCheck.setText(_translate("BASEUI", "Closed Spline"))
        #
        # self.freehandInteractorButton.setText(_translate("BASEUI", "FREEHAND DRAW"))
        # self.label_7.setText(_translate("BASEUI", "Contour"))
        #
        self.label_5.setText(_translate("BASEUI", "Working directroy"))
        self.workingDirToolButton.setText(_translate("BASEUI", "..."))
        self.menuFile.setTitle(_translate("BASEUI", "File"))
        self.menuLoad.setTitle(_translate("BASEUI", "Load"))
        self.actionDicom.setText(_translate("BASEUI", "Dicom"))
        self.actionVTK_Image.setText(_translate("BASEUI", "VTK Image"))
        self.actionQuit.setText(_translate("BASEUI", "Quit"))
        self.actionQuit.setShortcut(_translate("BASEUI", "Q"))
        #
        self.customButtonsLabel.setText(_translate("BASEUI", "Customised Buttons"))
        for iButton in self.modPushButtons:
            iButton.setText(_translate("BASEUI", "PushButton"))
        #
        self.customSlidersLabel.setText(_translate("BASEUI", "Customised Sliders"))
        for i, label in enumerate(self.sliderLabels):
            label.setText(_translate("BASEUI", f"Slider{i+1}"))

