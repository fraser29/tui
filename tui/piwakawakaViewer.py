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
from ngawari import vtkfilters, ftk
from tui import piwakawakamarkupui, piwakawakaStyles, baseMarkupViewer
import scipy.interpolate as interpolate

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
class PIWAKAWAKAMarkupViewer(piwakawakamarkupui.QtWidgets.QMainWindow, piwakawakamarkupui.Ui_BASEUI, baseMarkupViewer.BaseMarkupViewer):
    """
    UI for control of NMRViewer:
    Displays GUI
    Connects GUI buttons to source
    """
    def __init__(self, VERBOSE=False):
        super(PIWAKAWAKAMarkupViewer, self).__init__()
        self.setupUi(self)
        # Initialize base class
        baseMarkupViewer.BaseMarkupViewer.__init__(self, VERBOSE=VERBOSE)
        
        # 2D-specific defaults
        self.currentSliceID = 0
        self.maxSliceID = 0
        self.sliceOrientation = 'AXIAL'  # 'AXIAL', 'CORONAL', 'SAGITTAL'
        self.resliceDict = {}  # Dictionary: {timestep: [list of reslices]}
        self.sliceCenters = []  # List of center points for slices
        self.sliceNormals = []  # List of normal vectors for slices
        # Custom slice settings
        self.customSliceCenters = []
        self.customSliceNormals = []
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
        # Markups already initialized in base class
        self.markupActorList = []
        self.interactorStyleDict = {'Image': piwakawakaStyles.SinglePaneImageInteractor(self),
                                    'Trackball': vtk.vtkInteractorStyleTrackballCamera()}
        self.graphicsViewVTK.SetInteractorStyle(self.interactorStyleDict['Image'])
        
        # Set file dialog reference for base class
        self.fileDialog = piwakawakamarkupui.QtWidgets.QFileDialog
        
        self.show()


    def getCurrentRenderer(self):
        return self.renderer
    
    def _getHelpFileName(self):
        """Override to specify PIWAKAWAKA-specific help file"""
        return "help_piwakawaka.txt"
    
    # ==========================================================
    #   CONNECTIONS
    def connections(self):
        # Setup common connections from base class
        self._setupCommonConnections()
        
        # 2D-specific connections
        self.sliceSlider.valueChanged.connect(self.moveSliceSlider)
        self.sliceSlider.setSingleStep(1)
        self.sliceSlider.setPageStep(5)
        #
        # Orientation controls
        self.orientationComboBox.currentTextChanged.connect(self.orientationChanged)
        
        # Image manipulation buttons
        self.imManip_A.clicked.connect(self.flipCamera)
        self.imManip_B.clicked.connect(self.rotateCamera90)
        ##
        self.updatePushButtonDict()

    # Push button and time slider methods inherited from base class


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
        self._updateMarkups()

    # SLICE SLIDER
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

    def flipCamera(self):
        """Flip the camera view horizontally"""
        camera = self.renderer.GetActiveCamera()
        # Get current position and focal point
        pos = camera.GetPosition()
        focal = camera.GetFocalPoint()
        viewUp = camera.GetViewUp()
        
        # Flip horizontally by negating the x-component of position relative to focal point
        new_pos = [2 * focal[0] - pos[0], pos[1], pos[2]]
        camera.SetPosition(new_pos)
        self.renderWindow.Render()

    def rotateCamera90(self):
        """Rotate the camera view 90 degrees clockwise"""
        camera = self.renderer.GetActiveCamera()
        # Get current position and focal point
        pos = camera.GetPosition()
        focal = camera.GetFocalPoint()
        viewUp = camera.GetViewUp()
        
        # Rotate 90 degrees clockwise around the view normal
        # Calculate the view normal (from position to focal point)
        view_normal = [focal[0] - pos[0], focal[1] - pos[1], focal[2] - pos[2]]
        
        # Rotate the viewUp vector 90 degrees around the view normal
        # For a 90-degree rotation around Z-axis: (x, y) -> (-y, x)
        new_viewUp = [-viewUp[1], viewUp[0], viewUp[2]]
        camera.SetViewUp(new_viewUp)
        self.renderWindow.Render()

    # Window level methods inherited from base class

    def getWindowLevel(self):
        # Get current window level from image actor
        if hasattr(self, 'imageActor') and self.imageActor:
            prop = self.imageActor.GetProperty()
            return prop.GetColorWindow(), prop.GetColorLevel()
        return 255, 127.5

    def setWindowLevel(self, w, l):
        # Set window level on image actor
        if hasattr(self, 'imageActor') and self.imageActor:
            prop = self.imageActor.GetProperty()
            prop.SetColorWindow(w)
            prop.SetColorLevel(l)
            if self.VERBOSE:
                print(f"Set window level: window={w:.2f}, level={l:.2f}")


    def getCurrentSliceID(self):
        """Get current slice ID for 2D viewer"""
        return self.currentSliceID
    

    def orientationChanged(self, orientation):
        """Handle orientation change from dropdown"""
        if orientation == "Custom":
            # For custom, we'll use the current custom slices if they exist, otherwise default to axial
            if hasattr(self, 'customSliceCenters') and hasattr(self, 'customSliceNormals'):
                if len(self.customSliceCenters) > 0 and len(self.customSliceNormals) > 0:
                    self.setCustomSlices(self.customSliceCenters, self.customSliceNormals)
                    if self.VERBOSE:
                        print(f"Using custom slices: {len(self.customSliceCenters)} slices")
                    return
            # If no custom slices defined, fall back to axial
            orientation = "Axial"
            self.orientationComboBox.setCurrentText("Axial")
        
        # Convert title case to uppercase for the method
        orientation_upper = orientation.upper()
        
        # Set the orientation and rebuild everything
        if orientation_upper in ['AXIAL', 'CORONAL', 'SAGITTAL']:
            self.sliceOrientation = orientation_upper
            self.buildResliceDictionary(orientation=orientation_upper)
            
            # Reset to middle slice
            self.currentSliceID = int(self.maxSliceID / 2)
            
            # Update slider and display
            self.setupSliceSlider()
            self.updateImageSlice()
            self.updateViewAfterSliceChange()
            
            if self.VERBOSE:
                print(f"Changed orientation to {orientation_upper}, max slice: {self.maxSliceID}")
        else:
            if self.VERBOSE:
                print(f"Unknown orientation: {orientation}")

    def setCustomSliceCentersAndNormals(self, centers, normals):
        """Set custom slice centers and normals for user-defined slicing"""
        if len(centers) != len(normals):
            raise ValueError("Number of centers must match number of normals")
        
        self.customSliceCenters = centers
        self.customSliceNormals = normals
        
        # If currently in custom mode, update the slices
        if self.orientationComboBox.currentText() == "Custom":
            self.setCustomSlices(centers, normals)
        
        if self.VERBOSE:
            print(f"Set custom slice data: {len(centers)} centers and {len(normals)} normals")

    # Array selection methods inherited from base class

    # File loading methods inherited from base class


    ## -------------------------- END UI SETUP -----------------------------------
    # ==================================================================================================================
    def _setupViewerSpecificData(self):
        """2D-specific setup after data load"""
        # Set default orientation to Axial
        self.orientationComboBox.setCurrentText("Axial")
        
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
        self.setupSliceSlider()
        # Now setup image data (which will call updateImageSlice)
        self.__setupNewImageData() ## MAIN SETUP HERE ##
        self.currentSliceID = int(self.maxSliceID / 2)
        
        if self.VERBOSE:
            print(f"Image dimensions: {dims}")
            print(f"Orientation: {self.sliceOrientation}")
            print(f"Max slice ID: {self.maxSliceID}")
            print(f"Starting at slice: {self.currentSliceID}")
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


    # Exit and data access methods inherited from base class

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
        # print(f"DEBUG: imageCS_To_WorldCS_X: {imageCS_X} -> {matrix.MultiplyPoint([imageCS_X[0], imageCS_X[1], imageCS_X[2], 1])[:3]}")
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
        self._BaseMarkupViewer__setScalarRangeForCurrentArray()
        
        # Set background color
        self.renderer.SetBackground(0.1, 0.1, 0.1)
        
        # Create image actor for slice display
        self.imageActor = vtk.vtkImageActor()
        self.renderer.AddActor(self.imageActor)
        
        # Update to show current slice
        self.updateImageSlice()
        
        # Set initial window level based on data
        self.resetWindowLevel()
        
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
        currentReslice = self.getCurrentReslice()
        if currentReslice is not None:
            thisImageSlice = currentReslice.GetOutput()
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

    def _updateMarkups(self, window=None, level=None):
        self.clearCurrentMarkups()
        ## POINTS
        pointSize = self.boundingDist * 0.01

        ptsActor = self.Markups.getAllPointsActors(self.currentTimeID, pointSize)
        if ptsActor is not None:
            self.renderer.AddActor(ptsActor)
            self.markupActorList.append(ptsActor)
        ## POLYDATA
        pdActors = self.Markups.getAllPolydataActors(self.currentTimeID)
        if len(pdActors) > 0:
            for ipdActor in pdActors:
                self.renderer.AddActor(ipdActor)
                self.markupActorList.append(ipdActor)
        ## SPLINE
        self.Markups.showSplines_timeID_sliceID(self.currentTimeID, self.getCurrentSliceID())
        if (window is not None) and (level is not None):
            self.setWindowLevel(window, level)
        self.renderWindow.Render()



    # ======================== Markups - 2D specific implementations ================================================
    def removeActorFromAllRenderers(self, actor):
        """Remove actor from 2D renderer"""
        self.renderer.RemoveActor(actor)

    def updateViewAfterTimeChange(self):
        """Update view after time change for 2D viewer"""
        # Update image data for current time
        self.updateImageSlice()
        self.updateViewAfterSliceChange()


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
            self._updateMarkups(w, l)  # will render
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
def interpolateSplinesOverTime(piwakawakaViewer): 
    """
    Takes care of interpolation between all ROIs to permit tracking
    
    """
    # TODO - might need ot fix so same start point - just use ROI 0 and then all others start at closest pt
    # this will be needed once change npts in ROIs etc
    nSplinePts_i = 50
    splinesList = piwakawakaViewer.Markups.getSplinesTimeIDList()
    times = piwakawakaViewer.times
    counts = [len(splinesList[timeID]) for timeID in range(len(times))]
    countstf = [i>1 for i in counts]
    if any(countstf):
        raise ValueError("Must have one (or no) splines per time step")
    if sum(counts) < 2:
        raise ValueError("Must have splines at at least two time steps")
    ID_FIRST_SPLINE = countstf.index(True)
    XY = np.nan * np.ones((nSplinePts_i, len(times)+1, 2))
    handDrawntf = [False] * len(times)
    for iTimeID in range(len(times)):
        if counts[iTimeID] > 0:
            handDrawntf[iTimeID] = splinesList[iTimeID][0].isHandDrawn
    handDrawntf = handDrawntf[ID_FIRST_SPLINE:] + handDrawntf[:ID_FIRST_SPLINE]
    # Build XY matrix of spline points to interpolate between
    for iTimeID in range(len(times)):
        if handDrawntf[iTimeID]:
            pts = splinesList[iTimeID][0].getPoints(nSplinePts=nSplinePts_i)
            XY[:, iTimeID, :] = [i[:2] for i in pts]
    if piwakawakaViewer.TIME_PERIODIC:
        XY[:, -1, :] = XY[:, 0, :]
    u = [i - ID_FIRST_SPLINE for i in range(len(times)) if handDrawntf[i]] + [len(times) + 1]
    XY2 = splineRoisOverTime(XY, [float(i) / u[-1] for i in u])
    for iTimeID in range(len(times)):
        if not handDrawntf[iTimeID]:
            colID = iTimeID - ID_FIRST_SPLINE
            if ID_FIRST_SPLINE > iTimeID: colID -= 1
            newPts = np.squeeze(XY2[:, colID, :])
            newPts = [[i[0],i[1],0.0] for i in newPts]
            piwakawakaViewer.Markups.addSpline(newPts, 
                                                piwakawakaViewer.resliceDict[times[iTimeID]], 
                                                piwakawakaViewer.renderer, 
                                                piwakawakaViewer.graphicsViewVTK, 
                                                timeID=iTimeID,
                                                sliceID=piwakawakaViewer.getCurrentSliceID(),
                                                LOOP=piwakawakaViewer.splineClosed, 
                                                isHandDrawn=False)


def interpolateSplinesOverSlices(self):
    pass

def splineRoisOverTime(XYmat, u):
    """

    :param XYmat: should be shape nPts_per_ROI x nTimeSteps+1 x 2
        nans where not known. timeStep 0 must be known. timeStep -1 == 0
                                XY[:, -1, :] = XY[:, 0, :]
    :param u:
    :return:
    """
    XYmat = XYmat * 10000.0
    m, n, TWO = XYmat.shape
    XYout = np.zeros((m, n, TWO))
    newParams = np.linspace(0, 1, n)
    for k1 in range(m):
        xy = XYmat[k1, ~np.isnan(XYmat[k1, :, 0]), :].T
        tck, _ = interpolate.splprep(xy, u=u, k=1, per=1)
        newPts = interpolate.splev(newParams, tck)
        XYout[k1, :, 0] = newPts[0]
        XYout[k1, :, 1] = newPts[1]
    return XYout / 10000.0



### ====================================================================================================================
def dummyModButtonAction():
    print('Nothing implemented')



### ====================================================================================================================
### ====================================================================================================================
### ====================================================================================================================
### ====================================================================================================================