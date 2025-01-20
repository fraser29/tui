# -*- coding: utf-8 -*-

# WAS ORIGINALLY - Form implementation generated from reading ui file 'tuimarkupui.ui'
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
        # 3D Cursor
        self.cursor3DCheck = QtWidgets.QCheckBox(self.centralwidget)
        self.cursor3DCheck.setObjectName("cursor3DCheck")
        self.rightPanelLayout.addWidget(self.cursor3DCheck, 1, 0, 1, 1)
        #
        #
        # Select Array
        self.selectArrayComboBox = QtWidgets.QComboBox(self.centralwidget)
        self.selectArrayComboBox.setObjectName("selectArrayComboBox")
        self.rightPanelLayout.addWidget(self.selectArrayComboBox, 2, 0, 1, 1)
        #
        #
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
        self.button1 = QtWidgets.QPushButton(self.centralwidget)
        self.button1.setObjectName("button1")
        self.pushButtonsLayout.addWidget(self.button1, 0, 0, 1, 1)
        self.button7 = QtWidgets.QPushButton(self.centralwidget)
        self.button7.setObjectName("button7")
        self.pushButtonsLayout.addWidget(self.button7, 0, 1, 1, 1)
        self.button2 = QtWidgets.QPushButton(self.centralwidget)
        self.button2.setObjectName("button2")
        self.pushButtonsLayout.addWidget(self.button2, 1, 0, 1, 1)
        self.button8 = QtWidgets.QPushButton(self.centralwidget)
        self.button8.setObjectName("button8")
        self.pushButtonsLayout.addWidget(self.button8, 1, 1, 1, 1)
        self.button3 = QtWidgets.QPushButton(self.centralwidget)
        self.button3.setObjectName("button3")
        self.pushButtonsLayout.addWidget(self.button3, 2, 0, 1, 1)
        self.button9 = QtWidgets.QPushButton(self.centralwidget)
        self.button9.setObjectName("button9")
        self.pushButtonsLayout.addWidget(self.button9, 2, 1, 1, 1)
        self.button4 = QtWidgets.QPushButton(self.centralwidget)
        self.button4.setObjectName("button4")
        self.pushButtonsLayout.addWidget(self.button4, 3, 0, 1, 1)
        self.button10 = QtWidgets.QPushButton(self.centralwidget)
        self.button10.setObjectName("button10")
        self.pushButtonsLayout.addWidget(self.button10, 3, 1, 1, 1)
        self.button5 = QtWidgets.QPushButton(self.centralwidget)
        self.button5.setObjectName("button5")
        self.pushButtonsLayout.addWidget(self.button5, 4, 0, 1, 1)
        self.button11 = QtWidgets.QPushButton(self.centralwidget)
        self.button11.setObjectName("button11")
        self.pushButtonsLayout.addWidget(self.button11, 4, 1, 1, 1)
        self.button6 = QtWidgets.QPushButton(self.centralwidget)
        self.button6.setObjectName("button6")
        self.pushButtonsLayout.addWidget(self.button6, 5, 0, 1, 1)
        self.button12 = QtWidgets.QPushButton(self.centralwidget)
        self.button12.setObjectName("button12")
        self.pushButtonsLayout.addWidget(self.button12, 5, 1, 1, 1)
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
        BASEUI.setWindowTitle(_translate("BASEUI", "BASE UI"))
        self.label_3.setText(_translate("BASEUI", "Time"))
        self.timeLabel.setText(_translate("BASEUI", "0/0 [0.0]"))
        #
        self.imageManipulationGroupBox.setTitle(_translate("BASEUI", "Image manipulation"))
        self.imManip_A.setText(_translate("BASEUI", "Nothing"))
        self.imManip_B.setText(_translate("BASEUI", "Nothing"))
        #
        self.markupGroupBox.setTitle(_translate("BASEUI", "Image markup"))
        self.imMarkupButton_A.setText(_translate("BASEUI", "Nothing"))
        self.imMarkupButton_B.setText(_translate("BASEUI", "Nothing"))
        #
        # self.freehandInteractorButton.setText(_translate("BASEUI", "FREEHAND DRAW"))
        # self.label_7.setText(_translate("BASEUI", "Contour"))
        #
        self.axialButton.setText(_translate("BASEUI", "Ax"))
        self.threeDButton.setText(_translate("BASEUI", "3D"))
        self.saggitalButton.setText(_translate("BASEUI", "Sag"))
        self.coronalButton.setText(_translate("BASEUI", "Cor"))
        self.gridViewButton.setText(_translate("BASEUI", "Grid"))
        self.button1.setText(_translate("BASEUI", "PushButton"))
        self.button7.setText(_translate("BASEUI", "PushButton"))
        self.button2.setText(_translate("BASEUI", "PushButton"))
        self.button8.setText(_translate("BASEUI", "PushButton"))
        self.button3.setText(_translate("BASEUI", "PushButton"))
        self.button9.setText(_translate("BASEUI", "PushButton"))
        self.button4.setText(_translate("BASEUI", "PushButton"))
        self.button10.setText(_translate("BASEUI", "PushButton"))
        self.button5.setText(_translate("BASEUI", "PushButton"))
        self.button11.setText(_translate("BASEUI", "PushButton"))
        self.button6.setText(_translate("BASEUI", "PushButton"))
        self.button12.setText(_translate("BASEUI", "PushButton"))
        self.cursor3DCheck.setText(_translate("BASEUI", "Show 3D Cursor"))
        self.label_5.setText(_translate("BASEUI", "Working directroy"))
        self.workingDirToolButton.setText(_translate("BASEUI", "..."))
        self.menuFile.setTitle(_translate("BASEUI", "File"))
        self.menuLoad.setTitle(_translate("BASEUI", "Load"))
        self.actionDicom.setText(_translate("BASEUI", "Dicom"))
        self.actionVTK_Image.setText(_translate("BASEUI", "VTK Image"))
        self.actionQuit.setText(_translate("BASEUI", "Quit"))
        self.actionQuit.setShortcut(_translate("BASEUI", "Q"))
        self.customButtonsLabel.setText(_translate("BASEUI", "Customised Buttons"))
        self.customSlidersLabel.setText(_translate("BASEUI", "Customised Sliders"))
        for i, label in enumerate(self.sliderLabels):
            label.setText(_translate("BASEUI", f"Slider{i+1}"))

