# -*- coding: utf-8 -*-

# Base class for common UI layout and setup functionality
# Extracted from tuimarkupui.py and piwakawakamarkupui.py

from PyQt5 import QtCore, QtGui, QtWidgets
import os
import site

# Get the site-packages directory
site_packages = site.getsitepackages()[0]
qt_plugins_path = os.path.join(site_packages, 'PyQt5', 'Qt5', 'plugins')
os.environ['QT_QPA_PLATFORM_PLUGIN_PATH'] = qt_plugins_path


class BaseMarkupUI(object):
    """Base class containing common UI layout and setup functionality."""
    
    def setupUi(self, BASEUI):
        """Setup the common UI components."""
        BASEUI.setObjectName("BASEUI")
        BASEUI.resize(1260, 1027)
        
        # Setup central widget and main layout
        self.centralwidget = QtWidgets.QWidget(BASEUI)
        self.centralwidget.setObjectName("centralwidget")
        self.mainLayout = QtWidgets.QGridLayout(self.centralwidget)
        self.mainLayout.setObjectName("gridLayout_5")
        
        # Setup left panel with graphics view and time controls
        self._setupLeftPanel()
        
        # Setup right panel with controls
        self._setupRightPanel()
        
        # Setup working directory controls
        self._setupWorkingDirectory()
        
        # Setup menu bar and status bar
        self._setupMenuAndStatusBar(BASEUI)
        
        # Setup connections
        self._setupConnections()
        
        # Call subclass-specific setup
        self._setupSubclassSpecific(BASEUI)
        
        # Translate UI
        self.retranslateUi(BASEUI)
        QtCore.QMetaObject.connectSlotsByName(BASEUI)
    
    def _setupLeftPanel(self):
        """Setup the left panel with graphics view and time controls."""
        self.leftPanelLayout = QtWidgets.QVBoxLayout()
        self.leftPanelLayout.setObjectName("verticalLayout_2")
        
        # Graphics view layout
        self.graphicsViewLayout = QtWidgets.QHBoxLayout()
        self.graphicsViewLayout.setObjectName("horizontalLayout_3")
        
        # Graphics view
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
        
        # Subclass-specific graphics view additions
        self._addGraphicsViewControls()
        
        # Label layout
        self.verticalLayout = QtWidgets.QVBoxLayout()
        self.verticalLayout.setObjectName("verticalLayout")
        self.label_4 = QtWidgets.QLabel(self.centralwidget)
        self.label_4.setObjectName("label_4")
        self.verticalLayout.addWidget(self.label_4)
        self.graphicsViewLayout.addLayout(self.verticalLayout)
        
        self.leftPanelLayout.addLayout(self.graphicsViewLayout)
        
        # Time control layout
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
    
    def _setupRightPanel(self):
        """Setup the right panel with all control groups."""
        # Create a container widget for the right panel
        self.rightPanelWidget = QtWidgets.QWidget(self.centralwidget)
        self.rightPanelWidget.setMaximumWidth(300)
        
        # Create the right panel layout
        self.rightPanelLayout = QtWidgets.QGridLayout(self.rightPanelWidget)
        self.rightPanelLayout.setObjectName("gridLayout_4")
        
        # Setup control groups
        self._setupImageManipulationGroup()
        self._setupAdditionalControls()
        self._setupMarkupGroup()
        self._setupHelpButton()
        self._setupSpacer()
        self._setupCustomButtons()
        self._setupAnimationControls()
        
        # Add the right panel widget to the main layout
        self.mainLayout.addWidget(self.rightPanelWidget, 0, 1, 1, 1)
    
    def _setupImageManipulationGroup(self):
        """Setup the image manipulation group box."""
        self.imageManipulationGroupBox = QtWidgets.QGroupBox(self.centralwidget)
        self.imageManipulationGroupBox.setObjectName("imageManipulationGroupBox")
        self.imageManipulationControlLayout = QtWidgets.QGridLayout(self.imageManipulationGroupBox)
        self.imageManipulationControlLayout.setObjectName("gridLayout_2")
        self.imageManipulationButtonsLayout = QtWidgets.QVBoxLayout()
        self.imageManipulationButtonsLayout.setObjectName("verticalLayout_4")
        
        # Subclass-specific image manipulation controls
        self._addImageManipulationControls()
        
        self.imageManipulationControlLayout.addLayout(self.imageManipulationButtonsLayout, 0, 0, 1, 1)
        self.rightPanelLayout.addWidget(self.imageManipulationGroupBox, 0, 0, 1, 1)
    
    def _setupAdditionalControls(self):
        """Setup additional controls between image manipulation and markup."""
        # Subclass-specific additional controls
        self._addAdditionalControls()
    
    def _setupMarkupGroup(self):
        """Setup the markup group box."""
        self.markupGroupBox = QtWidgets.QGroupBox(self.centralwidget)
        self.markupGroupBox.setObjectName("imageMarkupGroupBox")
        self.imageMarkupControlLayout = QtWidgets.QGridLayout(self.markupGroupBox)
        self.imageMarkupControlLayout.setObjectName("gridLayout_2")
        self.imageMarkupButtonsLayout = QtWidgets.QVBoxLayout()
        self.imageMarkupButtonsLayout.setObjectName("verticalLayout_4")
        
        # Markup buttons
        self.imMarkupButton_A = QtWidgets.QPushButton(self.markupGroupBox)
        self.imMarkupButton_A.setObjectName("imMarkupButton_A")
        self.imageMarkupButtonsLayout.addWidget(self.imMarkupButton_A)
        self.imMarkupButton_A.setEnabled(False) # STILL IN BETA
        
        self.imMarkupButton_B = QtWidgets.QPushButton(self.markupGroupBox)
        self.imMarkupButton_B.setObjectName("imMarkupButton_B")
        self.imageMarkupButtonsLayout.addWidget(self.imMarkupButton_B)
        self.imMarkupButton_B.setEnabled(False) # STILL IN BETA
        
        # Markup mode controls
        self.markupModeLayout = QtWidgets.QVBoxLayout()
        self.markupModeLayout.setObjectName("markupModeLayout")
        
        self.markupModeLabel = QtWidgets.QLabel(self.markupGroupBox)
        self.markupModeLabel.setObjectName("markupModeLabel")
        self.markupModeLayout.addWidget(self.markupModeLabel)
        
        self.markupModeComboBox = QtWidgets.QComboBox(self.markupGroupBox)
        self.markupModeComboBox.setObjectName("markupModeComboBox")
        self.markupModeComboBox.addItem("Point")
        # Subclass can add more items via _addMarkupModeItems()
        self._addMarkupModeItems()
        self.markupModeLayout.addWidget(self.markupModeComboBox)
        
        self.closedSplineCheck = QtWidgets.QCheckBox(self.markupGroupBox)
        self.closedSplineCheck.setObjectName("closedSplineCheck")
        self.closedSplineCheck.setChecked(True)
        self.markupModeLayout.addWidget(self.closedSplineCheck)
        
        self.imageMarkupButtonsLayout.addLayout(self.markupModeLayout)
        self.imageMarkupControlLayout.addLayout(self.imageMarkupButtonsLayout, 0, 0, 1, 1)
        self.rightPanelLayout.addWidget(self.markupGroupBox, 4, 0, 1, 1)
    
    def _setupHelpButton(self):
        """Setup the help button."""
        self.helpButton = QtWidgets.QPushButton(self.centralwidget)
        self.helpButton.setObjectName("helpButton")
        self.rightPanelLayout.addWidget(self.helpButton, 5, 0, 1, 1)
    
    def _setupSpacer(self):
        """Setup spacer item."""
        spacerItem1 = QtWidgets.QSpacerItem(20, 40, QtWidgets.QSizePolicy.Minimum, QtWidgets.QSizePolicy.Expanding)
        self.rightPanelLayout.addItem(spacerItem1, 6, 0, 1, 1)
    
    def _setupCustomButtons(self):
        """Setup custom buttons section."""
        self.customButtonsLabel = QtWidgets.QLabel(self.centralwidget)
        self.customButtonsLabel.setObjectName("customButtonsLabel")
        self.rightPanelLayout.addWidget(self.customButtonsLabel, 7, 0, 1, 1)
        
        self.pushButtonsLayout = QtWidgets.QGridLayout()
        self.pushButtonsLayout.setObjectName("gridLayout_3")
        self.modPushButtons = []
        for i in range(12):
            button = QtWidgets.QPushButton(self.centralwidget)
            button.setObjectName(f"button{i+1}")
            self.pushButtonsLayout.addWidget(button, i//2, i%2, 1, 1)
            self.modPushButtons.append(button)
        self.rightPanelLayout.addLayout(self.pushButtonsLayout, 8, 0, 1, 1)
    
    def _setupAnimationControls(self):
        """Setup animation controls."""
        self.animationControlsLabel = QtWidgets.QLabel(self.centralwidget)
        self.animationControlsLabel.setObjectName("animationControlsLabel")
        self.rightPanelLayout.addWidget(self.animationControlsLabel, 9, 0, 1, 1)
        
        self.animationLayout = QtWidgets.QVBoxLayout()
        self.animationLayout.setObjectName("animationLayout")
        
        self.playPauseButton = QtWidgets.QPushButton(self.centralwidget)
        self.playPauseButton.setObjectName("playPauseButton")
        self.playPauseButton.setCheckable(True)
        self.animationLayout.addWidget(self.playPauseButton)
        
        # Subclass-specific animation controls
        self._addAnimationControls()
        
        self.rightPanelLayout.addLayout(self.animationLayout, 10, 0, 1, 1)
    
    def _setupWorkingDirectory(self):
        """Setup working directory controls."""
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
    
    def _setupMenuAndStatusBar(self, BASEUI):
        """Setup menu bar and status bar."""
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
    
    def _setupConnections(self):
        """Setup common connections."""
        self.workingDirToolButton.clicked.connect(self.selectWorkingDirectory)
    
    def _setupSubclassSpecific(self, BASEUI):
        """Override in subclasses for specific setup."""
        pass
    
    # Methods to be overridden by subclasses
    def _addGraphicsViewControls(self):
        """Override in subclasses to add graphics view specific controls."""
        pass
    
    def _addImageManipulationControls(self):
        """Override in subclasses to add image manipulation specific controls."""
        pass
    
    def _addAdditionalControls(self):
        """Override in subclasses to add additional controls."""
        pass
    
    def _addAnimationControls(self):
        """Override in subclasses to add animation specific controls."""
        pass
    
    def _addMarkupModeItems(self):
        """Override in subclasses to add markup mode items."""
        pass
    
    def retranslateUi(self, BASEUI):
        """Override in subclasses to set specific text."""
        _translate = QtCore.QCoreApplication.translate
        
        # Common translations
        self.label_3.setText(_translate("BASEUI", "Time"))
        self.timeLabel.setText(_translate("BASEUI", "0/0 [0.0]"))
        self.imageManipulationGroupBox.setTitle(_translate("BASEUI", "Image manipulation"))
        self.markupGroupBox.setTitle(_translate("BASEUI", "Image markup"))
        self.markupModeLabel.setText(_translate("BASEUI", "Markup Mode:"))
        self.helpButton.setText(_translate("BASEUI", "Help"))
        self.label_5.setText(_translate("BASEUI", "Working directroy"))
        self.workingDirToolButton.setText(_translate("BASEUI", "..."))
        self.menuFile.setTitle(_translate("BASEUI", "File"))
        self.menuLoad.setTitle(_translate("BASEUI", "Load"))
        self.actionDicom.setText(_translate("BASEUI", "Dicom"))
        self.actionVTK_Image.setText(_translate("BASEUI", "VTK Image"))
        self.actionQuit.setText(_translate("BASEUI", "Quit"))
        self.actionQuit.setShortcut(_translate("BASEUI", "Q"))
        self.customButtonsLabel.setText(_translate("BASEUI", "Customised Buttons"))
        for iButton in self.modPushButtons:
            iButton.setText(_translate("BASEUI", "PushButton"))
        self.animationControlsLabel.setText(_translate("BASEUI", "Animation Controls"))
        self.playPauseButton.setText(_translate("BASEUI", "Play"))
        
        # Subclass-specific translations
        self._retranslateSubclassSpecific(BASEUI)
    
    def _retranslateSubclassSpecific(self, BASEUI):
        """Override in subclasses for specific translations."""
        pass
    
    def selectWorkingDirectory(self):
        """Override in subclasses to implement directory selection."""
        pass
