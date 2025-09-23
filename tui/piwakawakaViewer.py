#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Created on 13 March 2019

Basic viewer for advanced image processing:


@author: Fraser M. Callaghan
@email: callaghan.fm@gmail.com
"""


# import argparse
import vtk
import os
import numpy as np
from ngawari import fIO
from ngawari import vtkfilters, ftk
import spydcmtk
from tui import tuiMarkups, tuiStyles, tuiUtils, piwakawakamarkupui

from vtk.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor # type: ignore

INDEX_OFFSET = 1

outputWindow = vtk.vtkOutputWindow()
outputWindow.SetGlobalWarningDisplay(0)
vtk.vtkObject.SetGlobalWarningDisplay(0)
vtk.vtkLogger.SetStderrVerbosity(vtk.vtkLogger.VERBOSITY_ERROR)



# ======================================================================================================================
#   -- HELPERS --
# ======================================================================================================================

def _defineReslice(vtiObj, ORIENTATION, center, normalVector=None, guidingVector=None, slabNumberOfSlices=2):
    # Extract a slice in the desired orientation
    vtkfilters.ensureScalarsSet(vtiObj, possibleName='MRA')
    reslice = vtk.vtkImageReslice()
    reslice.SetInputData(vtiObj)
    reslice.SetOutputDimensionality(2)
    if normalVector is not None:
        if guidingVector is None:
            if (abs(normalVector[0]) >= abs(normalVector[1])):
                factor = 1.0 / np.sqrt(normalVector[0] * normalVector[0] + normalVector[2] * normalVector[2])
                u0 = -normalVector[2] * factor
                u1 = 0.0
                u2 = normalVector[0] * factor
            else:
                factor = 1.0 / np.sqrt(normalVector[1] * normalVector[1] + normalVector[2] * normalVector[2])
                u0 = 0.0
                u1 = normalVector[2] * factor
                u2 = -normalVector[1] * factor
            u = np.array([u0, u1, u2])
        else:
            u = ftk.getVectorComponentNormalToRefVec(guidingVector, normalVector)
            if np.isnan(u[0]):
                u = guidingVector
            u = u / np.linalg.norm(u)
        v = np.cross(normalVector, u)
        reslice.SetResliceAxesDirectionCosines(u, v, normalVector)
        reslice.SetResliceAxesOrigin(center)
    else:
        reslice.SetResliceAxes(_getOrientationMatrix(ORIENTATION, center))

    # reslice.SetInterpolationModeToLinear()
    reslice.SetInterpolationModeToNearestNeighbor()
    # reslice.SetInterpolationModeToCubic()
    reslice.SetSlabNumberOfSlices(slabNumberOfSlices)
    reslice.SetSlabModeToMax()
    reslice.Update()
    return reslice


def _getOrientationMatrix(ORIENTATION, center):
    ''' Matrices for axial, coronal, sagittal
    '''
    if ORIENTATION == 'AXIAL':
        mat = vtk.vtkMatrix4x4()
        mat.DeepCopy((1, 0, 0, center[0],
                        0, 1, 0, center[1],
                        0, 0, 1, center[2],
                        0, 0, 0, 1))
        # mat.DeepCopy((-1, 0, 0, center[0],
        #                 0, -1, 0, center[1],
        #                 0, 0, 1, center[2],
        #                 0, 0, 0, 1))
    elif ORIENTATION == 'CORONAL':
        mat = vtk.vtkMatrix4x4()
        mat.DeepCopy((1, 0, 0, center[0],
                          0, 0, 1, center[1],
                          0, -1, 0, center[2],
                          0, 0, 0, 1))
    elif ORIENTATION == 'SAGITTAL':
        mat = vtk.vtkMatrix4x4()
        mat.DeepCopy((0, 0,-1, center[0],
                           1, 0, 0, center[1],
                           0, -1, 0, center[2],
                           0, 0, 0, 1))
    return mat

# ======================================================================================================================
#   -- MAIN CLASS --
# ======================================================================================================================
# noinspection PyUnresolvedReferences
class PIWAKAWAKAMarkupViewer(piwakawakamarkupui.QtWidgets.QMainWindow, piwakawakamarkupui.Ui_BASEUI):
    """
    UI for control of NMRViewer:
    Displays GUI
    Connects GUI buttons to source
    """
    def __init__(self, VERBOSE=False):
        super(PIWAKAWAKAMarkupViewer, self).__init__()
        self.setupUi(self)
        # Defaults
        self.vtiDict = None
        self.patientMeta = spydcmtk.dcmVTKTK.PatientMeta()
        self.currentTimeID = 0
        self.currentSliceID = 0
        self.currentArray = ''
        self.times = []
        self.maxSliceID = 0
        self.sliceOrientation = 'AXIAL'  # 'AXIAL', 'CORONAL', 'SAGITTAL'
        self.resliceDict = {}  # Dictionary: {timestep: [list of reslices]}
        self.sliceCenters = []  # List of center points for slices
        self.sliceNormals = []  # List of normal vectors for slices
        self.scalarRange = {'Default':[0,255]}
        self.boundingDist = 0.0
        self.multiPointFactor = 0.0001
        # Markup mode settings
        self.markupMode = 'Point'  # 'Point' or 'Spline'
        self.splineClosed = True  # Whether splines should be closed
        ##
        self.nModPushButtons = 12
        self.modPushButtonDict = dict(zip(range(self.nModPushButtons),
                                          [['Mod-Button%d'%(i),dummyModButtonAction] for i in range(1,self.nModPushButtons+1)]))
        self.sliderDict = {}
        self.USE_FIELD_DATA = False
        self.VERBOSE = VERBOSE
        #
        # GRAPHICS VIEW SETUP
        try:
            self.graphicsViewVTK = QVTKRenderWindowInteractor(self.graphicsView)
        except AttributeError:
            self.graphicsViewVTK = QVTKRenderWindowInteractor(self.widget) # vtkRenderWindowInteractor
        self.graphicsViewVTK.setObjectName("graphicsView")
        self.graphicsViewVTK.RemoveObservers("KeyPressEvent")
        self.graphicsViewVTK.RemoveObservers("CharEvent")
        layout = piwakawakamarkupui.QtWidgets.QVBoxLayout(self.graphicsView)
        layout.addWidget(self.graphicsViewVTK)
        self.graphicsView.setLayout(layout)
        ##
        # print(self.graphicsViewVTK) # vtkRenderWindowInteractor
        # print(self.graphicsViewVTK.GetRenderWindow())
        # print(self.graphicsViewVTK.GetInteractorStyle()) # vtkInteractorStyleSwitch
        ##
        self.renderWindow = self.graphicsViewVTK.GetRenderWindow()
        self.renderer = vtk.vtkRenderer()
        self.renderWindow.AddRenderer(self.renderer)
        self.renderWindow.SetMultiSamples(0)
        #
        self.interactionState = None
        self.graphicsViewVTK.Initialize()
        self.graphicsViewVTK.Start()
        self.graphicsViewVTK.picker = vtk.vtkPropPicker()
        #
        self.connections()
        self.Markups = tuiMarkups.Markups(self)
        self.markupActorList = []
        self.interactorStyleDict = {'Image': tuiStyles.SinglePaneImageInteractor(self),
                                    'ImageTracer': tuiStyles.ImageTracerInteractorStyle(self),
                                    'Trackball': vtk.vtkInteractorStyleTrackballCamera()}
        self.graphicsViewVTK.SetInteractorStyle(self.interactorStyleDict['Image'])
        self.show()

    # ==========================================================
    #   CONNECTIONS
    def connections(self):
        self.timeSlider.valueChanged.connect(self.moveTimeSlider)
        self.timeSlider.setSingleStep(1)
        self.timeSlider.setPageStep(5)
        #
        self.sliceSlider.valueChanged.connect(self.moveSliceSlider)
        self.sliceSlider.setSingleStep(1)
        self.sliceSlider.setPageStep(5)
        #
        #
        # IMAGE MANIPULATION ## Don't want to do flipping etc - should just rotate other view until as desired
        # self.flipHorButton.clicked.connect(self.flipHorAction)
        # self.flipVertButton.clicked.connect(self.flipVertAction)
        #
        # MARKUP
        # self.pointInteractorButton.clicked.connect(self.pointInteractorAction)
        # self.freehandInteractorButton.clicked.connect(self.freehandInteractorAction)
        #
        #
        self.selectArrayComboBox.activated[str].connect(self.selectArrayComboBoxActivated)
        #
        self.actionDicom.triggered.connect(self._loadDicom)
        self.actionVTK_Image.triggered.connect(self.loadVTI_or_PVD)
        #
        self.actionQuit.triggered.connect(self.exit)
        #
        # Markup mode controls
        self.markupModeComboBox.currentTextChanged.connect(self.markupModeChanged)
        self.closedSplineCheck.stateChanged.connect(self.splineClosedChanged)
        ##
        self.updatePushButtonDict()
        self.updateSliderDict()

    def updatePushButtonDict(self, newPushButtonDict=None):
        """
        Update the modifiable push buttons with new actions and labels.

        This method allows customised buttons to be applied for the UI. 
        It updates the dictionary of modifiable push buttons with new
        actions and labels. It then applies these changes to the UI, enabling
        or disabling buttons as necessary.

        Args:
            newPushButtonDict (dict, optional): A dictionary containing new button
                configurations. The keys are button indices (0-11), and the values
                are lists containing the button label and the action to be performed
                when clicked. If None, the existing modPushButtonDict is used.

        Example:
            newDict = {
                0: ['Do Action A', action_function_A],
                1: ['Do Action B', action_function_B]
            }
            self.updatePushButtonDict(newDict)
        """
        if type(newPushButtonDict) == dict:
            self.modPushButtonDict = newPushButtonDict
        ### Modifiable push buttons
        for k1 in range(self.nModPushButtons):
            try:
                self.modPushButtons[k1].setText(self.modPushButtonDict[k1][0])
            except KeyError:
                self.modPushButtons[k1].setEnabled(False)
                continue
            try:
                self.modPushButtons[k1].clicked.disconnect()
            except (TypeError, RuntimeError):
                pass
            self.modPushButtons[k1].clicked.connect(self.modPushButtonDict[k1][1])
            self.modPushButtons[k1].setEnabled(True)
            if self.modPushButtonDict[k1][1] == dummyModButtonAction:
                self.modPushButtons[k1].setEnabled(False)

    def updateSliderDict(self, newSliderDict=None):
        """
        Update the slider labels with new labels.

        This method allows customised sliders to be applied for the UI. 
        It updates the dictionary of sliders with new labels. It then applies these changes to the UI, enabling
        or disabling buttons as necessary.

        Args:
            newSliderDict (dict, optional): A dictionary containing new slider configurations. The keys are slider indices (0-3), and the values
                are dicts as per example below. 

        Example:
            newDict = {
                0: {"label": 'Slider 1 label', "action": action_function_A, "min": 0, "max": 100, "value": 50, "singleStep": 1, "pageStep": 5},
                1: {"label": 'Slider 2 label', "action": action_function_B, "min": 0, "max": 100, "value": 50, "singleStep": 1, "pageStep": 5},
            }
            self.updateSliderDict(newDict)
        """
        if type(newSliderDict) == dict:
            self.sliderDict = newSliderDict
        for k1 in range(2):
            try:
                self.sliderLabels[k1].setText(self.sliderDict[k1]["label"])
                self.sliders[k1].setMinimum(self.sliderDict[k1]["min"])
                self.sliders[k1].setMaximum(self.sliderDict[k1]["max"])
                self.sliders[k1].setValue(self.sliderDict[k1]["value"])
                self.sliders[k1].valueChanged.connect(self.sliderDict[k1]["action"])
                self.sliders[k1].setSingleStep(self.sliderDict[k1]["singleStep"])
                self.sliders[k1].setPageStep(self.sliderDict[k1]["pageStep"])
                self.sliders[k1].setEnabled(True)
            except KeyError:
                self._sliderDummySetup(k1)
    
    def _sliderDummySetup(self, k1):
        self.sliderLabels[k1].setText(f'Slider {k1+1}')
        self.sliders[k1].setEnabled(False)

    def setUserDefinedKeyPress(self, newKeyPressDict=None):
        self.interactorStyleDict['Image'].setUserDefinedKeyCallbackDict(newKeyPressDict)

    def getCurrentInteractorStyle(self):
        return self.graphicsViewVTK.GetInteractorStyle()

    #TIME SLIDER
    def setupTimeSlider(self):
        self.timeSlider.setMinimum(0)
        self.timeSlider.setMaximum(len(self.times)-1)
        self.updateTimeLabel()

    def updateTimeLabel(self):
        try:
            self.timeLabel.setText("%d/%d [%3.2f]"%(self.currentTimeID+INDEX_OFFSET,
                                                          self.timeSlider.maximum()+INDEX_OFFSET,
                                                          self.getCurrentTime()))
        except IndexError:
            self.timeLabel.setText("%d/%d [%3.2f]"%(self.currentTimeID+INDEX_OFFSET,
                                                          self.timeSlider.maximum(),
                                                          0.0))

    def moveTimeSlider(self, val):
        self.currentTimeID = val
        self.updateTimeLabel()
        self.updateViewAfterTimeChange()
        self.timeSlider.setValue(self.currentTimeID)
        self.__updateMarkups()

    def timeAdvance1(self):
        if self.currentTimeID < (self.timeSlider.maximum()):
            self.currentTimeID += 1
        self.moveTimeSlider(self.currentTimeID)

    def timeReverse1(self):
        if self.currentTimeID > (self.timeSlider.minimum()):
            self.currentTimeID -= 1
        self.moveTimeSlider(self.currentTimeID)

    # SLICE SLIDER
    def setupSliceSlider(self):
        self.sliceSlider.setMinimum(0)
        self.sliceSlider.setMaximum(self.maxSliceID)
        if self.VERBOSE:
            print(f"Slice slider range: 0 to {self.maxSliceID}")
        self.updateSliceLabel()

    def updateSliceLabel(self):
        try:
            self.sliceSliderLabel.setText("%d/%d"%(self.currentSliceID+INDEX_OFFSET,
                                                          self.sliceSlider.maximum()+INDEX_OFFSET))
        except IndexError:
            self.sliceSliderLabel.setText("%d/%d"%(self.currentSliceID+INDEX_OFFSET,
                                                          self.sliceSlider.maximum()))

    def moveSliceSlider(self, val):
        self.currentSliceID = val
        self.updateSliceLabel()
        self.updateImageSlice()
        self.updateViewAfterSliceChange()
        self.sliceSlider.setValue(self.currentSliceID)
        self.__updateMarkups()

    # SLICE SLIDER
    def _getDeltaX(self):
        return np.mean(self.getCurrentVTIObject().GetSpacing())#[self.interactionView] # ?? is this best, or mean ??

    def scrollForwardCurrentSlice1(self):
        # Move to next slice
        if self.currentSliceID < self.maxSliceID:
            self.currentSliceID += 1
            self.moveSliceSlider(self.currentSliceID)

    def scrollBackwardCurrentSlice1(self):
        # Move to previous slice
        if self.currentSliceID > 0:
            self.currentSliceID -= 1
            self.moveSliceSlider(self.currentSliceID)

    # BUTTONS

    def cameraReset(self):
        self.renderer.GetActiveCamera().SetFocalPoint(0, 0, 0)
        self.renderer.GetActiveCamera().SetPosition(0, 0, 1)
        self.renderer.GetActiveCamera().SetViewUp(0, -1, 0)
        self.renderer.GetActiveCamera().ParallelProjectionOn()
        self.renderer.GetActiveCamera().Zoom(2.5)
        self.renderer.ResetCamera()
        self.renderWindow.Render()

    def cameraReset3D(self):
        self.renderer.ResetCameraClippingRange()
        self.renderWindow.Render()

    def __setScalarRangeForCurrentArray(self):
        sR_t = [self.vtiDict[iT].GetScalarRange() for iT in self.times]
        self.scalarRange[self.currentArray] = [min([i[0] for i in sR_t]), max([i[1] for i in sR_t])]

    def resetWindowLevel(self):
        if self.currentArray not in self.scalarRange.keys():
            self.__setScalarRangeForCurrentArray()
        sR = self.scalarRange.get(self.currentArray, self.scalarRange.get('Default', [0,255]))
        if self.VERBOSE:
            print(f"Resetting window level - scalar range: {sR}")
            print(f"Resetting window level to {sR[1] - sR[0]:.2f}, {(sR[0] + sR[1]) / 2.0:.2f}")
        self.__updateMarkups(window=sR[1] - sR[0], level=(sR[0] + sR[1]) / 2.0)

    def getWindowLevel(self):
        # For single pane viewer, return default values
        return 255, 127.5

    def setWindowLevel(self, w, l):
        # For single pane viewer, this is a placeholder
        pass




    def pushButton1(self):
        print('Button pushed - do something')



    # IMAGE MANIPULATION
    def flipHorAction(self):
        transform = vtk.vtkTransform()
        transform.Scale(-1, 1, 1)  # Flip along X-axis
        for actor in self.renderer.GetActors():
            actor.SetUserTransform(transform)
        self.renderWindow.Render()

    def flipVertAction(self):
        transform = vtk.vtkTransform()
        transform.Scale(1, -1, 1)  # Flip along Y-axis
        for actor in self.renderer.GetActors():
            actor.SetUserTransform(transform)
        self.renderWindow.Render()



    # MARKUPS : TODO
    # def pointInteractorAction(self):
    #     if self.pointInteractorButton.isChecked():
    #         print('Begin point interaction')
    #         self.graphicsViewVTK.SetInteractorStyle(self.interactorStyleDict['Image'])
    #         self.freehandInteractorButton.setChecked(0)
    #         self.graphicsViewVTK.GetInteractorStyle().modifyDefaultInteraction_points()
    #     else: # this is for if on and click off (so nothing on)
    #         self.graphicsViewVTK.SetInteractorStyle(self.interactorStyleDict['Image'])
    #         self.graphicsViewVTK.GetInteractorStyle().modifyDefaultInteraction_default()

    # def freehandInteractorAction(self):
    #     if self.freehandInteractorButton.isChecked():
    #         print('Begin point-freehand interaction')
    #         self.pointInteractorButton.setChecked(0)

    #         self.resliceCursor.SetThickMode(False)
    #         self.resliceCursor.SetThickness(0, 0, 0)



    #         self.tracerWidget = vtk.vtkImageTracerWidget()
    #         self.tracerWidget.SetInteractor(self.graphicsViewVTK)
    #         # self.tracerWidget.SetViewProp(self.imageActor)  # Assuming you have an imageActor
    #         self.tracerWidget.ProjectToPlaneOn()
    #         self.tracerWidget.SetProjectionNormal(2)  # For XY plane (change as needed)
    #         self.tracerWidget.SetHandleSize(0.005)
    #         self.tracerWidget.AutoCloseOn()



    #         self.graphicsViewVTK.SetInteractorStyle(self.interactorStyleDict['ImageTracer'])
    #         # self.graphicsViewVTK.GetInteractorStyle().modifyDefaultInteraction_points() # change this

    #         # self.renderer.AddActor(self.imageActor)
    #         self.tracerWidget.SetEnabled(1)
    #         self.renderWindow.Render()


    #     else: # this is for if on and click off (so nothing on)
    #         self.graphicsViewVTK.SetInteractorStyle(self.interactorStyleDict['Image'])
    #         self.graphicsViewVTK.GetInteractorStyle().modifyDefaultInteraction_default()




    def markupModeChanged(self, mode):
        self.markupMode = mode
        if self.VERBOSE:
            print(f"Markup mode changed to: {mode}")

    def splineClosedChanged(self, state):
        self.splineClosed = state == 2  # Qt.Checked = 2
        if self.VERBOSE:
            print(f"Spline closed setting changed to: {self.splineClosed}")

    def selectArrayComboBoxActivated(self, selectedText):
        for iTime in self.times:
            self.vtiDict[iTime].GetPointData().SetActiveScalars(selectedText)
        # Update the image actor with new data
        self.updateViewAfterTimeChange()
        self.resetWindowLevel()
        self.statusBar().showMessage(selectedText)
        self.setCurrentArray(selectedText)

    def setCurrentArray(self, arrayName):
        self.currentArray = arrayName
        self.selectArrayComboBox.setCurrentText(arrayName)
        self.resetWindowLevel()
        self.renderWindow.Render()

    # MENU ACTIONS
    def _getFileViaDialog(self):
        fileName = piwakawakamarkupui.QtWidgets.QFileDialog.getOpenFileName(self,
                                                                ("Open image data"),
                                                                str(self.workingDirLineEdit.text()),
                                                                ("Image data (*.vti);;PVD(, *.pvd)"))[0]
        if self.VERBOSE:
            print(str(fileName))
        return str(fileName)
    def _getDirectoryViaDialog(self):
        dirName = piwakawakamarkupui.QtWidgets.QFileDialog.getExistingDirectory(self,
                                                                ("Open dicom directory"),
                                                                str(self.workingDirLineEdit.text()))
        if self.VERBOSE:
            print(str(dirName))
        return str(dirName)

    def _loadDicom(self):
        if self.VERBOSE:
            print('Load dicoms')
        dirName = self._getDirectoryViaDialog()
        self.loadDicomDir(dirName)

    # LOAD NEW DATA METHODS
    def loadDicomDir(self, dicomDir):
        dcmSeries = spydcmtk.dcmTK.DicomSeries.setFromDirectory(dicomDir)
        self.vtiDict = dcmSeries.buildVTIDict()
        if self.VERBOSE:
            print(f"Have VTI dict. Times (ms): {[int(i*1000.0) for i in sorted(self.vtiDict.keys())]}")
        # TODO - not saving correct coordinates for markups
        self._setupAfterLoad()

    def loadVTI_or_PVD(self, fileName=None):
        if self.VERBOSE:
            print('Load VTI')
        if not fileName:
            fileName = self._getFileViaDialog()
        if len(fileName) > 0:
            self.vtiDict = fIO.readImageFileToDict(fileName) # will check for vti internally and then return time 0 e.g. {0.0:vti}
            for iTime in self.vtiDict.keys():
                for iName in vtkfilters.getArrayNames(self.vtiDict[iTime]):
                    vtkfilters.setArrayDtype(self.vtiDict[iTime], iName, np.float64)
                vtkfilters.ensureScalarsSet(self.vtiDict[iTime])
            if self.VERBOSE:
                print('Data loaded...')
            self._setupAfterLoad()


    ## -------------------------- END UI SETUP -----------------------------------
    # ==================================================================================================================
    def _setupAfterLoad(self):
        self.times = sorted(self.vtiDict.keys())
        self.patientMeta.initFromVTI(self.getCurrentVTIObject())
        # Reset Markups
        self.Markups.initForNewData(len(self.times))
        self.setupTimeSlider()
        #
        self.selectArrayComboBox.clear()
        arrayName = vtkfilters.getScalarsArrayName(self.vtiDict[self.getCurrentTime()])
        if not arrayName:
            arrayName = vtkfilters.getArrayNames(self.vtiDict[self.getCurrentTime()])[0]
        self.currentArray = arrayName
        self.currentTimeID = 0
        for iArray in vtkfilters.getArrayNames(self.vtiDict[self.getCurrentTime()]):
            self.selectArrayComboBox.addItem(iArray)
        self.selectArrayComboBox.setCurrentText(self.currentArray)
        #
        bounds = self.getCurrentVTIObject().GetBounds()
        self.boundingDist = max([bounds[1]-bounds[0], bounds[3]-bounds[2], bounds[5]-bounds[4]])
        
        # Get image dimensions and build reslice dictionary BEFORE setting up image data
        ii = list(self.vtiDict.values())[0]
        dims = [0,0,0]
        ii.GetDimensions(dims)
        
        # Set max slice ID based on orientation
        if self.sliceOrientation == 'AXIAL':
            self.maxSliceID = dims[2] - 1
        elif self.sliceOrientation == 'CORONAL':
            self.maxSliceID = dims[1] - 1
        elif self.sliceOrientation == 'SAGITTAL':
            self.maxSliceID = dims[0] - 1
        
        # Build reslice dictionary with default orientation
        self.buildResliceDictionary(orientation=self.sliceOrientation)
        
        # Setup slice slider after reslice dictionary is built
        self.setupSliceSlider()
        
        # Now setup image data (which will call updateImageSlice)
        self.__setupNewImageData() ## MAIN SETUP HERE ##
        
        # Start at slice 0 (first slice)
        self.currentSliceID = 0
        
        if self.VERBOSE:
            print(f"Image dimensions: {dims}")
            print(f"Orientation: {self.sliceOrientation}")
            print(f"Max slice ID: {self.maxSliceID}")
            print(f"Starting at slice: {self.currentSliceID}")
        
        self.moveTimeSlider(self.currentTimeID)
        self.moveSliceSlider(self.currentSliceID)
    
    def buildResliceDictionary(self, orientation=None, customCenters=None, customNormals=None):
        """Build dictionary of reslices for all timesteps
        
        Args:
            orientation: 'AXIAL', 'CORONAL', 'SAGITTAL', or None for custom
            customCenters: List of center points for custom slices
            customNormals: List of normal vectors for custom slices
        """
        if orientation is None and (customCenters is None or customNormals is None):
            orientation = self.sliceOrientation
        
        self.resliceDict = {}
        self.sliceCenters = []
        self.sliceNormals = []
        
        if self.VERBOSE:
            print(f"Building reslice dictionary with orientation: {orientation}")
        
        # Get image dimensions for default slice generation
        ii = list(self.vtiDict.values())[0]
        dims = [0, 0, 0]
        ii.GetDimensions(dims)
        origin = ii.GetOrigin()
        spacing = ii.GetSpacing()
        center = ii.GetCenter()
        
        # Generate slice centers and normals
        if customCenters is not None and customNormals is not None:
            # Use custom centers and normals
            self.sliceCenters = customCenters
            self.sliceNormals = customNormals
            self.maxSliceID = len(customCenters) - 1
        else:
            # Generate default slices based on orientation
            if orientation == 'AXIAL':
                self.maxSliceID = dims[2] - 1
                for k in range(dims[2]):
                    sliceCenter = [center[0], center[1], origin[2] + k * spacing[2]]
                    self.sliceCenters.append(sliceCenter)
                    self.sliceNormals.append([0, 0, 1])
            elif orientation == 'CORONAL':
                self.maxSliceID = dims[1] - 1
                for j in range(dims[1]):
                    sliceCenter = [center[0], origin[1] + j * spacing[1], center[2]]
                    self.sliceCenters.append(sliceCenter)
                    self.sliceNormals.append([0, 1, 0])
            elif orientation == 'SAGITTAL':
                self.maxSliceID = dims[0] - 1
                for i in range(dims[0]):
                    sliceCenter = [origin[0] + i * spacing[0], center[1], center[2]]
                    self.sliceCenters.append(sliceCenter)
                    self.sliceNormals.append([1, 0, 0])
        
        # Build reslices for each timestep
        for timeStep in self.times:
            vtiObj = self.vtiDict[timeStep]
            resliceList = []
            
            for i, (sliceCenter, sliceNormal) in enumerate(zip(self.sliceCenters, self.sliceNormals)):
                reslice = _defineReslice(vtiObj, orientation, sliceCenter, normalVector=sliceNormal)
                resliceList.append(reslice)
            
            self.resliceDict[timeStep] = resliceList
            
            if self.VERBOSE:
                print(f"Built {len(resliceList)} reslices for timestep {timeStep}")
        
        if self.VERBOSE:
            print(f"Reslice dictionary built with {len(self.sliceCenters)} slices")
    
    def setSliceOrientation(self, orientation):
        """Change the slice orientation and rebuild reslice dictionary"""
        if orientation in ['AXIAL', 'CORONAL', 'SAGITTAL']:
            self.sliceOrientation = orientation
            self.buildResliceDictionary(orientation=orientation)
            
            # Reset to middle slice
            self.currentSliceID = int(self.maxSliceID / 2)
            
            # Update slider and display
            self.setupSliceSlider()
            self.updateImageSlice()
            self.updateViewAfterSliceChange()
            
            if self.VERBOSE:
                print(f"Changed orientation to {orientation}, max slice: {self.maxSliceID}")
    
    def setCustomSlices(self, centers, normals):
        """Set custom slice centers and normals and rebuild reslice dictionary"""
        if len(centers) != len(normals):
            raise ValueError("Number of centers must match number of normals")
        
        self.buildResliceDictionary(customCenters=centers, customNormals=normals)
        
        # Reset to first slice
        self.currentSliceID = 0
        
        # Update slider and display
        self.setupSliceSlider()
        self.updateImageSlice()
        self.updateViewAfterSliceChange()
        
        if self.VERBOSE:
            print(f"Set {len(centers)} custom slices")
    
    def getCurrentReslice(self):
        """Get the current reslice for the current timestep and slice"""
        if not hasattr(self, 'resliceDict') or not self.resliceDict:
            if self.VERBOSE:
                print("Reslice dictionary not initialized")
            return None
            
        if self.currentTimeID >= len(self.times):
            if self.VERBOSE:
                print(f"Current time ID {self.currentTimeID} out of range")
            return None
            
        currentTime = self.times[self.currentTimeID]
        if currentTime not in self.resliceDict:
            if self.VERBOSE:
                print(f"Time {currentTime} not found in reslice dictionary")
            return None
            
        resliceList = self.resliceDict[currentTime]
        if self.currentSliceID >= len(resliceList):
            if self.VERBOSE:
                print(f"Current slice ID {self.currentSliceID} out of range")
            return None
            
        return resliceList[self.currentSliceID]


    def exit(self):
        self.close()
        return 0


    # ==================================================================================================================
    #   DATA
    def getCurrentTime(self):
        return self.times[self.currentTimeID]

    def getCurrentVTIObject(self, COPY=False):
        ii = self.vtiDict[self.getCurrentTime()]
        if COPY:
            i2 = vtk.vtkImageData()
            i2.ShallowCopy(ii)
            return i2
        return ii

    def getCurrentResliceMatrix(self):
        return self.getCurrentReslice().GetResliceAxes()

    def getPointIDAtX(self, X):
        """Get point ID from world coordinates, accounting for reslice orientation"""
        return self.getCurrentVTIObject().FindPoint(X)

    def getIJKAtX(self, X):
        """Convert world coordinates to IJK coordinates, accounting for reslice orientation"""
        ijk = [0, 0, 0]
        pcoords = [0.0, 0.0, 0.0]
        res = self.getCurrentVTIObject().ComputeStructuredCoordinates(X, ijk, pcoords)
        if res == 0:
            return None
        return ijk

    def getIJKAtPtID(self, ptID):
        X = self.getCurrentVTIObject().GetPoint(ptID)
        ijk = self.getIJKAtX(X)
        return ijk


    def getPixelValueAtReslicePosition(self, mouseX, mouseY):
        """Get pixel value at mouse position from the current reslice"""
        X = self.mouseXYTo_ImageCS_X(mouseX, mouseY)
        X_ = self.imageCS_To_WorldCS_X(X)
        ptID = self.getCurrentVTIObject().FindPoint(X_)
        return self.getPixelValueAtPtID_tuple(ptID)
        
    
    def getReslice_IJK_X_ID_AtMouse(self, mouseX, mouseY):
        """Get IJK coordinates at mouse position for the current reslice"""
        X = self.mouseXYTo_ImageCS_X(mouseX, mouseY)
        X_ = self.imageCS_To_WorldCS_X(X)
        ijk = self.getIJKAtX(X_)
        return ijk, X_, self.getCurrentVTIObject().FindPoint(X_)
    
    
    def getPixelValueAtPtID_tuple(self, ptID):
        if (ptID < 0) or (ptID >= self.getCurrentVTIObject().GetNumberOfPoints()):
            return None
        return self.getCurrentVTIObject().GetPointData().GetArray(self.currentArray).GetTuple(ptID)


    def imageCS_To_WorldCS_X(self, imageCS_X):
        """Convert image coordinates to world coordinates"""
        matrix = self.getCurrentResliceMatrix()
        return matrix.MultiplyPoint([imageCS_X[0], imageCS_X[1], imageCS_X[2], 1])[:3]

    def mouseXYTo_ImageCS_X(self, mouseX, mouseY):
        """Convert mouse coordinates to world coordinates using vtkPropPicker"""
        self.graphicsViewVTK.picker.Pick(mouseX, mouseY, 0, self.renderer)
        pos = self.graphicsViewVTK.picker.GetPickPosition()
        return pos
        

    def getCurrentViewNormal(self): # uses current view
        """Get the view normal based on current slice"""
        if self.currentSliceID < len(self.sliceNormals):
            return np.array(self.sliceNormals[self.currentSliceID])
        return np.array([0, 0, 1])  # Default Z-axis normal

    def getViewNormal(self, i):
        """Get view normal - for single pane, same as current view normal"""
        return self.getCurrentViewNormal()
    

    def getCurrentResliceAsVTI(self, COPY=False):
        # For single pane viewer, return the current VTI object
        return self.getCurrentVTIObject(COPY)


    def __setupNewImageData(self): # ONLY ON NEW DATA LOAD
        self.__setScalarRangeForCurrentArray()
        
        # Set background color
        self.renderer.SetBackground(0.1, 0.1, 0.1)
        
        # Create image actor for slice display
        self.imageActor = vtk.vtkImageActor()
        self.renderer.AddActor(self.imageActor)
        
        # Update to show current slice
        self.updateImageSlice()
        
        # Image setup complete
        
        # Render
        self.cameraReset()
        self.cameraReset3D()


    # ======================== RENDERING ===============================================================================
    def updateViewAfterTimeChange(self): # NEED TO TRIGGER ON A TIME CHANGE
        # Update image data for current time
        self.updateImageSlice()
        self.updateViewAfterSliceChange()

    def updateViewAfterSliceChange(self):
        self.renderWindow.Render()
    
    def updateImageSlice(self):
        """Update the image actor to show the current slice using pre-built reslices"""
        if not hasattr(self, 'imageActor') or not self.imageActor:
            if self.VERBOSE:
                print("Image actor not initialized")
            return
            
        # Get the current reslice
        currentReslice = self.getCurrentReslice()
        
        if currentReslice is not None:
            # Get the output from the reslice
            thisImageSlice = currentReslice.GetOutput()
            
            # Set the extracted slice to the image actor
            if self.VERBOSE:
                print(f"Setting up imageActor at slice {self.currentSliceID} of {self.maxSliceID}")
                if self.currentSliceID < len(self.sliceCenters):
                    print(f"Slice center: {self.sliceCenters[self.currentSliceID]}")
                if self.currentSliceID < len(self.sliceNormals):
                    print(f"Slice normal: {self.sliceNormals[self.currentSliceID]}")
                print(f"Image range: {thisImageSlice.GetPointData().GetScalars().GetRange()}")
            
            self.imageActor.SetInputData(thisImageSlice)
        else:
            if self.VERBOSE:
                print(f"No reslice available for slice {self.currentSliceID}")

    def updateAllActorsToCurrentSlice(self):
        """
        For perfomrance action only on slider release
        :return:
        """
        for k1 in range(len(self.times)):
            try:
                self.imageResliceList[k1].SetResliceAxesDirectionCosines(self.cosineVecs[self.currentSliceID][0],
                                                                         self.cosineVecs[self.currentSliceID][1],
                                                                         self.cosineVecs[self.currentSliceID][2])
                self.imageResliceList[k1].SetResliceAxesOrigin(self.sliceCenters[self.currentSliceID])
            except IndexError:
                pass # no data loaded

    def clearCurrentMarkups(self):
        for iActor in self.markupActorList:
            self.renderer.RemoveActor(iActor)
        self.markupActorList = []

    def __updateMarkups(self, window=None, level=None):
        self.clearCurrentMarkups()
        ## POINTS
        pointSize = self.boundingDist * 0.01
        # Show lines when in spline mode
        SHOW_LINES = (self.markupMode == 'Spline')
        LOOP = self.splineClosed  # Use the spline closed setting

        ptsActor = self.Markups.getAllPointsActors(self.currentTimeID, pointSize)
        if ptsActor is not None:
            self.renderer.AddActor(ptsActor)
            self.markupActorList.append(ptsActor)
            if SHOW_LINES:
                lineWidth = 3 if self.markupMode == 'Spline' else pointSize*0.9
                lineActor = self.Markups.getAllPointsLineActor(self.currentTimeID, lineWidth, LOOP)
                self.renderer.AddActor(lineActor)
                self.markupActorList.append(lineActor)
        ## POLYDATA
        pdActors = self.Markups.getAllPolydataActors(self.currentTimeID)
        if len(pdActors) > 0:
            for ipdActor in pdActors:
                self.renderer.AddActor(ipdActor)
                self.markupActorList.append(ipdActor)
        ## SPLINE
        splineActors = self.Markups.getAllSplineActors(self.currentTimeID)
        if len(splineActors) > 0:
            for isplActor in splineActors:
                self.renderer.AddActor(isplActor)
                self.markupActorList.append(isplActor)
        if (window is not None) and (level is not None):
            self.setWindowLevel(window, level)
        self.renderWindow.Render()





    # ======================== Markups =================================================================================
    def deleteAllMarkups(self):
        self.Markups.reset()
        self.__updateMarkups()

    def addPoint(self, X, norm=None):
        self.Markups.addPoint(X, self.currentTimeID, self.getCurrentTime(), norm)
        self.__updateMarkups()

    def addSplinePoint(self, X, norm=None):
        """Add a point for spline creation. In spline mode, points are connected by splines."""
        self.Markups.addPoint(X, self.currentTimeID, self.getCurrentTime(), norm)
        # Update rendering to show splines
        self.__updateMarkups()

    def removeLastPoint(self):
        self.Markups.removeLastPoint(self.currentTimeID)
        self.__updateMarkups()

    def addPolydata(self, polydata, timeID=None, time=None, color=(0,1,1)):
        if time is not None:
            timeID = int(np.argmin([abs(i-time) for i in self.times]))
        else:
            if timeID is None:
                timeID = self.currentTimeID
        iTime = self.times[timeID]
        self.Markups.addPolydata(polydata, timeID, iTime, color=color)
        self.__updateMarkups()

    def addSpline(self, X): #TODO - TESTING -
        nn = self.getCurrentViewNormal()
        pts = vtkfilters.ftk.buildCircle3D(X, nn, 0.03, 25)
        if self.VERBOSE:
            print('Build circle at X and norm:',str(X), str(nn))
        self.Markups.addSpline(pts, self._getCurrentReslice(), self.getCurrentRenderer(), self.graphicsViewVTK, self.currentTimeID, self.getCurrentTime())
        self.__updateMarkups()


    # ======================== OTHER OUTPUTS ===========================================================================
    def saveMontage(self, outputFullFile, startPt, endPt, nImages, viewID):
        outputDir = os.path.split(outputFullFile)[0]
        fList = self.__saveImages(outputDir, startPt, endPt, nImages, viewID)
        os.system('cd %s && montage %s -tile %dx1 -geometry 300x300+0+0 %s' % (
            outputDir, ' '.join(fList), len(fList), outputFullFile))
        for iFile in fList:
            os.unlink(iFile)
        return outputFullFile

    # def saveGIF(self, outputFullFile, deltaEndSlice, deltaSlice):
    #     return self.__saveImages(outputFullFile, deltaEndSlice, deltaSlice, False, MAKE_GIF=True)

    def saveImages(self, outputDir, startPt, endPt, nImages, viewID, outputPrefix='', FULL_VIEW=False, size=None):
        return self.__saveImages( outputDir, startPt, endPt, nImages, viewID, outputPrefix=outputPrefix,
                                  FULL_VIEW=FULL_VIEW, size=size)

    def __saveImages(self, outputDir, startPt, endPt, nImages, viewID, outputPrefix='', FULL_VIEW=False, size=None):
        from PIL import Image
        fileOutList = []
        w, l = self.getWindowLevel()
        lowP, highP = l-(w/2.), l+(w/2.)
        imageLine = vtkfilters.buildPolyLineBetweenTwoPoints(startPt, endPt, nImages)
        allCP = vtkfilters.getPtsAsNumpy(imageLine)
        for k1, cp in enumerate(allCP):
            # Update camera position for different views
            self.renderer.GetActiveCamera().SetPosition(cp)
            self.__updateMarkups(w, l)  # will render
            fOut = os.path.join(outputDir, f'{outputPrefix}{k1}.png')
            if FULL_VIEW:
                windowToImageFilter = vtk.vtkWindowToImageFilter()
                windowToImageFilter.SetInput(self.graphicsViewVTK.GetRenderWindow())
                windowToImageFilter.Update()
                writer = vtk.vtkPNGWriter()
                writer.SetFileName(fOut)
                writer.SetInputConnection(windowToImageFilter.GetOutputPort())
                writer.Write()
            else:
                ii = self.getCurrentResliceAsVTI(COPY=True)
                dims = ii.GetDimensions()
                A = vtkfilters.getArrayAsNumpy(ii, 'ImageScalars')
                A[A < lowP] = lowP
                A[A > highP] = highP
                A = A + abs(np.min(A)) # Max all pixels positive
                A = (A / np.max(A) * 255) # Set to 0-255
                A = np.reshape(A, (dims[0], dims[1]), order='F')
                A = np.rot90(A, 1) # FIXME - should work out this number from viewID
                img = Image.fromarray(A.astype(np.uint8))  # uses mode='L'
                if size is not None:
                    try: 
                        size[1] 
                    except (TypeError, IndexError): 
                        size = [size, size]
                    wh = img.size
                    whMaxID = np.argmax(wh)
                    ratios = [wh[0] / wh[whMaxID], wh[1] / wh[whMaxID]]
                    if wh[whMaxID] > max(size):
                        sizeN = [size[0] * ratios[0], size[1] * ratios[1]]
                        img = img.resize((int(sizeN[0]), int(sizeN[1])))
                img.save(fOut)
            fileOutList.append(fOut)
        return fileOutList
        # os.system('convert %s -resize 400x400 %s'%(fOut, fOut))

# ======================================================================================================================
# ======================================================================================================================
# ======================================================================================================================



### ====================================================================================================================
def dummyModButtonAction():
    print('Nothing implemented')


def probeData(vtkObj, probeLocation, arrayName):
    """
    Get vtkObj array value at location
    :param vtkObj:
    :param probeLocation: coords xyz
    :param arrayName:
    :return:
    """
    myVtkPoints = vtk.vtkPoints()
    vertices = vtk.vtkCellArray()
    ptID = myVtkPoints.InsertNextPoint(probeLocation[0], probeLocation[1], probeLocation[2])
    vertices.InsertNextCell(1)
    vertices.InsertCellPoint(ptID)
    polyData = vtk.vtkPolyData()
    polyData.SetPoints(myVtkPoints)
    polyData.SetVerts(vertices)
    return probeDataWithPt(vtkObj, polyData, arrayName)

def probeDataWithPt(vtkObj, vtkPolyPt, arrayName):
    probeF = vtk.vtkProbeFilter()
    probeF.SetInputData(vtkPolyPt)
    probeF.SetSourceData(vtkObj)
    probeF.Update()
    return probeF.GetOutput().GetPointData().GetArray(arrayName).GetTuple(0)

def getClosestInSortedList(listIn, ref):
    for k1 in range(0, len(listIn)):
        if listIn[k1] > ref:
            return k1
    return len(listIn) - 1

### ====================================================================================================================
### ====================================================================================================================
### ====================================================================================================================
### ====================================================================================================================