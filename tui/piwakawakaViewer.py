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
from ngawari import vtkfilters
import spydcmtk
from tui import tuiMarkups, tuiStyles, tuiUtils, piwakawakamarkupui

from vtk.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor # type: ignore

INDEX_OFFSET = 1

outputWindow = vtk.vtkOutputWindow()
outputWindow.SetGlobalWarningDisplay(0)
vtk.vtkObject.SetGlobalWarningDisplay(0)
vtk.vtkLogger.SetStderrVerbosity(vtk.vtkLogger.VERBOSITY_ERROR)

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
    def __init__(self):
        super(PIWAKAWAKAMarkupViewer, self).__init__()
        self.setupUi(self)
        # Defaults
        self.vtiDict = None
        self.patientMeta = spydcmtk.dcmVTKTK.PatientMeta()
        self.currentTimeID = 0
        self.currentSliceID = 0
        self.currentArray = ''
        self.times = []
        self.limitContourToOne = True
        self.minContourLength = 0.1
        self.scalarRange = {'Default':[0,255]}
        self.boundingDist = 0.0
        self.multiPointFactor = 0.0001
        self.contourVal = None
        # Markup mode settings
        self.markupMode = 'Point'  # 'Point' or 'Spline'
        self.splineClosed = True  # Whether splines should be closed
        ##
        self.nModPushButtons = 12
        self.modPushButtonDict = dict(zip(range(self.nModPushButtons),
                                          [['Mod-Button%d'%(i),dummyModButtonAction] for i in range(1,self.nModPushButtons+1)]))
        self.sliderDict = {}
        self.USE_FIELD_DATA = False
        self.DEBUG = False
        self.planeBackgroundColors = [[0.3, 0.1, 0.1],
                                      [0.1, 0.3, 0.1],
                                      [0.1, 0.1, 0.3],
                                      [0.1, 0.1, 0.1]]
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
        self.picker = vtk.vtkPointPicker()
        self.picker.SetTolerance(0.005)
        self.worldPicker = vtk.vtkWorldPointPicker()
        #
        self.interactionState = None
        self.graphicsViewVTK.Initialize()
        self.graphicsViewVTK.Start()
        #
        self.connections()
        self.Markups = tuiMarkups.Markups(self)
        self.threeDContourActor = None
        self.markupActorList = []
        self.interactorStyleDict = {'Image': tuiStyles.ImageInteractor(self),
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
        #
        # IMAGE MANIPULATION ## Don't want to do flipping etc - should just rotate other view until as desired
        # self.flipHorButton.clicked.connect(self.flipHorAction)
        # self.flipVertButton.clicked.connect(self.flipVertAction)
        #
        # MARKUP
        # self.pointInteractorButton.clicked.connect(self.pointInteractorAction)
        # self.freehandInteractorButton.clicked.connect(self.freehandInteractorAction)
        # self.contourSlider.valueChanged.connect(self.moveContourSlider) # Opacity
        # self.contourLineEdit.returnPressed.connect(self.enterInContourLineEdit)
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
    def _getDeltaX(self):
        return np.mean(self.getCurrentVTIObject().GetSpacing())#[self.interactionView] # ?? is this best, or mean ??

    def scrollForwardCurrentSlice1(self):
        if self.interactionView < 3: # If in 3D window then do nothing
            cp = np.array(self.resliceCursor.GetCenter())
            nn = np.array(self.getCurrentViewNormal())
            dx = self._getDeltaX()
            self.resliceCursor.SetCenter(cp + nn * dx)
            self.__updateMarkups() # will render

    def scrollBackwardCurrentSlice1(self):
        if self.interactionView < 3: # If in 3D window then do nothing
            cp = np.array(self.resliceCursor.GetCenter())
            nn = -1.0 * np.array(self.getCurrentViewNormal())
            dx = self._getDeltaX()
            self.resliceCursor.SetCenter(cp + nn * dx)
            self.__updateMarkups()

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
        if self.DEBUG:
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

    # def moveContourSlider(self, val=None):
    #     if self.threeDContourActor is not None:
    #         if val is not None:
    #             self.threeDContourActor.GetProperty().SetOpacity(float(val)/100.0)
    #             self.renderWindow.Render()

    # def enterInContourLineEdit(self):
    #     self.setContourVal(self.getContourVal())

    # def getContourVal(self):
    #     try:
    #         return float(self.contourLineEdit.text())
    #     except ValueError:
    #         return None

    def setContourVal(self, val):
        self.contourVal = val
        # self.contourLineEdit.setText('%5.0f'%(self.contourVal))
        self.__update3DSurfaceView()


    def markupModeChanged(self, mode):
        self.markupMode = mode
        print(f"Markup mode changed to: {mode}")

    def splineClosedChanged(self, state):
        self.splineClosed = state == 2  # Qt.Checked = 2
        print(f"Spline closed setting changed to: {self.splineClosed}")

    def selectArrayComboBoxActivated(self, selectedText):
        for iTime in self.times:
            self.vtiDict[iTime].GetPointData().SetActiveScalars(selectedText)
        self.resliceCursor.SetImage(self.getCurrentVTIObject())
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
        print(str(fileName))
        return str(fileName)
    def _getDirectoryViaDialog(self):
        dirName = piwakawakamarkupui.QtWidgets.QFileDialog.getExistingDirectory(self,
                                                                ("Open dicom directory"),
                                                                str(self.workingDirLineEdit.text()))
        print(str(dirName))
        return str(dirName)

    def _loadDicom(self):
        print('Load dicoms')
        dirName = self._getDirectoryViaDialog()
        self.loadDicomDir(dirName)

    # LOAD NEW DATA METHODS
    def loadDicomDir(self, dicomDir):
        dcmSeries = spydcmtk.dcmTK.DicomSeries.setFromDirectory(dicomDir)
        self.vtiDict = dcmSeries.buildVTIDict()
        print(f"Have VTI dict. Times (ms): {[int(i*1000.0) for i in sorted(self.vtiDict.keys())]}")
        # TODO - not saving correct coordinates for markups
        self._setupAfterLoad()

    def loadVTI_or_PVD(self, fileName=None):
        print('Load VTI')
        if not fileName:
            fileName = self._getFileViaDialog()
        if len(fileName) > 0:
            self.vtiDict = fIO.readImageFileToDict(fileName) # will check for vti internally and then return time 0 e.g. {0.0:vti}
            for iTime in self.vtiDict.keys():
                for iName in vtkfilters.getArrayNames(self.vtiDict[iTime]):
                    vtkfilters.setArrayDtype(self.vtiDict[iTime], iName, np.float64)
                vtkfilters.ensureScalarsSet(self.vtiDict[iTime])
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
        self.__setupNewImageData() ## MAIN SETUP HERE ##
        ii = list(self.vtiDict.values())[0]
        dims = [0,0,0]
        ii.GetDimensions(dims)
        self.currentSliceID = int(dims[2]/2.0)
        self.moveTimeSlider(self.currentTimeID)


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

    def getCurrentRenderer(self):
        return self.renderer

    def getCurrentX(self): # point X under cursor
        return [0, 0, 0]  # Default center point

    def getPointIDAtX(self, X):
        return tuiUtils.imageX_2_PointID(self.getCurrentVTIObject(), X)

    def getIJKAtX(self, X):
        IJK = self.patientMeta.patientToImageCoordinates(X)
        return IJK

    def getIJKAtPtID(self, ptID):
        return tuiUtils.imageID_2_IJK(self.getCurrentVTIObject(), ptID)

    def getPixelValueAtX_tuple(self, X):
        ptID = self.getPointIDAtX(X)
        return self.getPixelValueAtPtID_tuple(ptID)
    def getPixelValueAtPtID_tuple(self, ptID):
        return self.getCurrentVTIObject().GetPointData().GetArray(self.currentArray).GetTuple(ptID)

    def mouseXYToWorldX(self, mouseX, mouseY):
        # Create a point picker
        picker = vtk.vtkPointPicker()
        picker.SetTolerance(0.005)
        
        # Pick the point
        picker.Pick(mouseX, mouseY, 0, self.renderer)
        
        # Get the picked point
        pickedPoint = picker.GetPickPosition()
        
        return pickedPoint

    def getCurrentViewNormal(self): # uses current view
        return np.array([0, 0, 1])  # Default Z-axis normal

    def getViewNormal(self, i):
        return np.array([0, 0, 1])  # Default Z-axis normal


    def getCurrentResliceAsVTI(self, COPY=False):
        # For single pane viewer, return the current VTI object
        return self.getCurrentVTIObject(COPY)


    def __setupNewImageData(self): # ONLY ON NEW DATA LOAD
        self.__setScalarRangeForCurrentArray()
        
        # Set background color
        self.renderer.SetBackground(0.1, 0.1, 0.1)
        
        # Add image actor to renderer
        imageActor = vtk.vtkImageActor()
        imageActor.SetInputData(self.getCurrentVTIObject())
        self.renderer.AddActor(imageActor)
        
        # 3D contour if data is not too large
        dims = [0,0,0]
        self.getCurrentVTIObject().GetDimensions(dims)
        if np.prod(dims) < 60e+6: # For very large data - don't want to do this
            print(f"Working with current array: {self.currentArray}")
            A = vtkfilters.getArrayAsNumpy(self.getCurrentVTIObject(), self.currentArray)
            A = A[A>1.0]
            contourVal = np.mean(A) * 2.0
            print(f"Made contour at value: {int(contourVal)}")
            self.setContourVal(contourVal)
        
        # Render
        self.cameraReset()
        self.cameraReset3D()


    # ======================== RENDERING ===============================================================================
    def updateViewAfterTimeChange(self): # NEED TO TRIGGER ON A TIME CHANGE
        # Update image data for current time
        self.updateViewAfterSliceChange()

    def updateViewAfterSliceChange(self):
        self.renderWindow.Render()

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


    def __update3DSurfaceView(self):
        if self.threeDContourActor:
            self.renderer.RemoveActor(self.threeDContourActor)
        if self.contourVal:
            cc, ccActor = self.__get3DContourActor()
            self.threeDContourActor = ccActor
            self.renderer.AddActor(self.threeDContourActor)
        self.renderWindow.Render()

    def __get3DContourActor(self):
        cc = self.getCurrentContourPolydata()
        if cc:
            mapper = vtk.vtkPolyDataMapper()
            mapper.SetInputData(cc)
            mapper.ScalarVisibilityOff()
            contourActor = vtk.vtkActor()
            contourActor.GetProperty().SetRepresentationToSurface()
            contourActor.SetMapper(mapper)
            return cc, contourActor

    def getCurrentContourPolydata(self):
        if self.contourVal:
            contour = vtkfilters.contourFilter(self.getCurrentVTIObject(), self.contourVal)
            return vtkfilters.getConnectedRegionLargest(contour)

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