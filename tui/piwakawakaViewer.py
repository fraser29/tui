#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Created on 13 March 2019

Basic viewer for advanced image processing:


@author: Fraser M. Callaghan
@email: callaghan.fm@gmail.com
"""


# import argparse
import logging
import vtk
import os
import numpy as np
from ngawari import vtkfilters
from tui import piwakawakamarkupui, piwakawakaStyles, baseMarkupViewer, tuiUtils
from PyQt5 import QtWidgets

logger = logging.getLogger(__name__)

from vtk.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor # type: ignore

INDEX_OFFSET = 1

outputWindow = vtk.vtkOutputWindow()
outputWindow.SetGlobalWarningDisplay(0)
vtk.vtkObject.SetGlobalWarningDisplay(0)
vtk.vtkLogger.SetStderrVerbosity(vtk.vtkLogger.VERBOSITY_ERROR)


def _time_series_period(times_all):
    """Length of one temporal cycle: last time to first time plus one frame step (uniform cine)."""
    ta = np.asarray(times_all, dtype=float)
    if ta.size < 2:
        return None
    ta = np.sort(ta)
    dt = float(ta[1] - ta[0])
    return float(ta[-1] - ta[0] + dt)


def _interp_scalar_in_time(t_eval, t_key, vals, times_all, periodic):
    """Linear interpolation in time; if periodic, wrap using _time_series_period(times_all)."""
    t_eval = float(t_eval)
    t_key = np.asarray(t_key, dtype=float)
    vals = np.asarray(vals, dtype=float)
    order = np.argsort(t_key)
    t_key = t_key[order]
    vals = vals[order]
    if not periodic:
        return float(np.interp(t_eval, t_key, vals))
    period = _time_series_period(times_all)
    if period is None or period <= 0:
        return float(np.interp(t_eval, t_key, vals))
    t0 = float(np.min(times_all))
    te = t0 + ((t_eval - t0) % period)
    t_ext = np.concatenate([t_key - period, t_key, t_key + period])
    v_ext = np.concatenate([vals, vals, vals])
    return float(np.interp(te, t_ext, v_ext))


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
    def __init__(self):
        super(PIWAKAWAKAMarkupViewer, self).__init__()
        self.setupUi(self)
        # Initialize base class
        baseMarkupViewer.BaseMarkupViewer.__init__(self)
        
        # 2D-specific defaults
        self.currentSliceID = 0
        self.maxSliceID = 0
        self.sliceOrientation = tuiUtils.AXIAL  # 'AXIAL', 'CORONAL', 'SAGITTAL'
        self.resliceDict = {}  # Dictionary: {timestep: [list of reslices]}
        self.sliceCenters = []  # List of center points for slices
        self.sliceNormals = []  # List of normal vectors for slices
        # Custom slice settings
        self.customSliceCenters = []
        self.customSliceNormals = []
        #
        # GRAPHICS VIEW SETUP
        # Use common VTK setup from base class
        self.graphicsViewVTK, self.renderWindow = self._setupVTKInteractor(self.graphicsView)
        
        # Piwakawaka-specific renderer setup (single renderer)
        self.renderer = vtk.vtkRenderer()
        self.renderWindow.AddRenderer(self.renderer)
        
        self.interactionState = None
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
        self.imMarkupButton_A.clicked.connect(self.interpolateSplinesFromManualKeyframes)

    # Push button and time slider methods inherited from base class


    # SLICE SLIDER
    def setupSliceSlider(self):
        self.sliceSlider.setMinimum(0)
        self.sliceSlider.setMaximum(self.maxSliceID)
        logger.debug("Slice slider range: 0 to %d", self.maxSliceID)
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
        # Set reference scale for zoom calculation
        self._referenceParallelScale = self.renderer.GetActiveCamera().GetParallelScale()
        self.renderWindow.Render()

    def cameraReset3D(self):
        self.renderer.ResetCameraClippingRange()
        self.renderWindow.Render()

    def getZoomFactor(self):
        """Get current zoom factor from camera for 2D viewer"""
        camera = self.renderer.GetActiveCamera()
        if camera.GetParallelProjection():
            # For parallel projection, use parallel scale
            # Smaller parallel scale = more zoomed in
            # We'll use a reference scale to calculate zoom factor
            if not hasattr(self, '_referenceParallelScale'):
                self._referenceParallelScale = camera.GetParallelScale()
            zoom_factor = self._referenceParallelScale / camera.GetParallelScale()
        else:
            # For perspective projection, use view angle
            # Smaller view angle = more zoomed in
            if not hasattr(self, '_referenceViewAngle'):
                self._referenceViewAngle = camera.GetViewAngle()
            zoom_factor = self._referenceViewAngle / camera.GetViewAngle()
        
        # Clamp zoom factor to reasonable range
        return max(0.1, min(10.0, zoom_factor))

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
            logger.info("Set window level: window=%.2f, level=%.2f", w, l)


    def getCurrentSliceID(self):
        """Get current slice ID for 2D viewer"""
        return self.currentSliceID
    

    def orientationChanged(self, orientation):
        """Handle orientation change from dropdown"""
        if orientation == tuiUtils.CUSTOM:
            # For custom, we'll use the current custom slices if they exist, otherwise default to axial
            if hasattr(self, 'customSliceCenters') and hasattr(self, 'customSliceNormals'):
                if len(self.customSliceCenters) > 0 and len(self.customSliceNormals) > 0:
                    self.setCustomSlices(self.customSliceCenters, self.customSliceNormals)
                    logger.debug("Using custom slices: %d slices", len(self.customSliceCenters))
                    return
            # If no custom slices defined, fall back to axial
            orientation = tuiUtils.AXIAL
            self.orientationComboBox.setCurrentText(orientation)
        
        # Convert title case to uppercase for the method
        orientation_upper = orientation.upper()
        
        # Set the orientation and rebuild everything
        if orientation_upper in [tuiUtils.AXIAL, tuiUtils.CORONAL, tuiUtils.SAGITTAL]:
            self.sliceOrientation = orientation_upper
            self.buildResliceDictionary(orientation=orientation_upper)
            
            # Reset to middle slice
            self.currentSliceID = int(self.maxSliceID / 2)
            
            # Update slider and display
            self.setupSliceSlider()
            self.updateImageSlice()
            self.updateViewAfterSliceChange()
            
            logger.info("Changed orientation to %s, max slice: %d", orientation_upper, self.maxSliceID)
        else:
            logger.warning("Unknown orientation: %s", orientation)

    def setCustomSliceCentersAndNormals(self, centers, normals):
        """Set custom slice centers and normals for user-defined slicing"""
        if len(centers) != len(normals):
            raise ValueError("Number of centers must match number of normals")
        
        self.customSliceCenters = centers
        self.customSliceNormals = normals
        
        # If currently in custom mode, update the slices
        # if self.orientationComboBox.currentText() == "Custom":
        self.setCustomSlices(centers, normals)
        
        logger.debug("Set custom slice data: %d centers and %d normals", len(centers), len(normals))
        logger.debug("Custom slice centers[0]=%s", centers[0])
        logger.debug("Custom slice normals[0]=%s", normals[0])


    # Array selection methods inherited from base class

    # File loading methods inherited from base class


    def polyDataToMarkups(self, polyDataDict):
        pass
    ## -------------------------- END UI SETUP -----------------------------------
    # ==================================================================================================================
    def _setupViewerSpecificData(self):
        """2D-specific setup after data load"""
        # Set default orientation to Axial
        self.orientationComboBox.setCurrentText(tuiUtils.AXIAL)
        
        # Get image dimensions and build reslice dictionary BEFORE setting up image data
        ii = list(self.vtiDict.values())[0]
        dims = [0,0,0]
        ii.GetDimensions(dims)
        
        # Set max slice ID based on orientation
        if self.sliceOrientation == tuiUtils.AXIAL:
            self.maxSliceID = dims[2] - 1
        elif self.sliceOrientation == tuiUtils.CORONAL:
            self.maxSliceID = dims[1] - 1
        elif self.sliceOrientation == tuiUtils.SAGITTAL:
            self.maxSliceID = dims[0] - 1
        
        # Build reslice dictionary with default orientation
        self.buildResliceDictionary(orientation=self.sliceOrientation)
        self.setupSliceSlider()
        # Now setup image data (which will call updateImageSlice)
        self.__setupNewImageData() ## MAIN SETUP HERE ##
        self.currentSliceID = int(self.maxSliceID / 2)
        
        logger.debug("Image dimensions: %s", dims)
        logger.debug("Orientation: %s", self.sliceOrientation)
        logger.debug("Max slice ID: %d", self.maxSliceID)
        logger.debug("Starting at slice: %d", self.currentSliceID)
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
        
        logger.debug("Building reslice dictionary with orientation: %s", orientation)
        
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
            if orientation == tuiUtils.AXIAL:
                self.maxSliceID = dims[2] - 1
                for k in range(dims[2]):
                    sliceCenter = [center[0], center[1], origin[2] + k * spacing[2]]
                    self.sliceCenters.append(sliceCenter)
                    self.sliceNormals.append([0, 0, 1])
            elif orientation == tuiUtils.CORONAL:
                self.maxSliceID = dims[1] - 1
                for j in range(dims[1]):
                    sliceCenter = [center[0], origin[1] + j * spacing[1], center[2]]
                    self.sliceCenters.append(sliceCenter)
                    self.sliceNormals.append([0, 1, 0])
            elif orientation == tuiUtils.SAGITTAL:
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
                reslice = tuiUtils.defineReslice(vtiObj, orientation, sliceCenter, normalVector=sliceNormal)
                resliceList.append(reslice)
            
            self.resliceDict[timeStep] = resliceList
        logger.debug("Reslice dictionary built with %d slices", len(self.sliceCenters))
    
    def setSliceOrientation(self, orientation):
        """Change the slice orientation and rebuild reslice dictionary"""
        if orientation in [tuiUtils.AXIAL, tuiUtils.CORONAL, tuiUtils.SAGITTAL]:
            self.sliceOrientation = orientation
            self.buildResliceDictionary(orientation=orientation)
            
            # Reset to middle slice
            self.currentSliceID = int(self.maxSliceID / 2)
            
            # Update slider and display
            self.setupSliceSlider()
            self.updateImageSlice()
            self.updateViewAfterSliceChange()
            
            logger.debug("Changed orientation to %s, max slice: %d", orientation, self.maxSliceID)
    
    def setCustomSlices(self, centers, normals):
        """Set custom slice centers and normals and rebuild reslice dictionary"""
        if len(centers) != len(normals):
            raise ValueError("piwakawakaViewer: Number of centers must match number of normals")
        
        self.buildResliceDictionary(customCenters=centers, customNormals=normals)
        
        # Reset to first slice
        self.currentSliceID = 0
        
        # Update slider and display
        self.setupSliceSlider()
        self.updateImageSlice()
        self.updateViewAfterSliceChange()
        
        logger.debug("Set %d custom slices", len(centers))
    
    def getCurrentReslice(self):
        """Get the current reslice for the current timestep and slice"""
        if not hasattr(self, 'resliceDict') or not self.resliceDict:
            logger.warning("Reslice dictionary not initialized")
            return None
            
        if self.currentTimeID >= len(self.times):
            logger.warning("Current time ID %d out of range", self.currentTimeID)
            return None
            
        currentTime = self.times[self.currentTimeID]
        if currentTime not in self.resliceDict:
            logger.warning("Time %s not found in reslice dictionary", currentTime)
            return None
            
        resliceList = self.resliceDict[currentTime]
        if self.currentSliceID >= len(resliceList):
            logger.warning("Current slice ID %d out of range", self.currentSliceID)
            return None
            
        return resliceList[self.currentSliceID]


    # Exit and data access methods inherited from base class

    def getCurrentResliceMatrix(self):
        return self.getCurrentReslice().GetResliceAxes()

    def getIJK_imageCSX(self, imageCS_X):
        return self.getIJKAtX(self.imageCS_to_ResliceCS_X(imageCS_X))

    def getPtID_at_IJK(self, ijk):
        dims = self.getCurrentVTIObject().GetDimensions()
        i, j, k = ijk
        pointId = i + j * dims[0] + k * dims[0] * dims[1]
        return pointId

    def getPixelValueAtReslicePosition(self, mouseX, mouseY):
        """Get pixel value at mouse position from the current reslice"""
        X_imageCS = self.mouseXYTo_ImageCS_X(mouseX, mouseY)
        ptID = self.getCurrentVTIObject().FindPoint(X_imageCS)
        return self.getPixelValueAtPtID_tuple(ptID)
        
    def getReslice_IJK_X_ID_AtMouse(self, mouseX, mouseY):
        """Get IJK coordinates at mouse position for the current reslice"""
        X_imageCS = self.mouseXYTo_ImageCS_X(mouseX, mouseY)
        X_worldCS = self.imageCS_To_WorldCS_X(X_imageCS)
        ijk = self.getIJK_imageCSX(X_imageCS)
        return ijk, X_worldCS, self.getPtID_at_IJK(ijk)


    def imageCS_to_ResliceCS_X(self, imageCS_X, sliceID=None):
        if sliceID is None:
            matrix = self.getCurrentResliceMatrix()
        else:
            currentTime = self.times[self.currentTimeID]
            resliceList = self.resliceDict[currentTime]
            matrix = resliceList[sliceID].GetResliceAxes()
        return matrix.MultiplyPoint([imageCS_X[0], imageCS_X[1], imageCS_X[2], 1])[:3]
    
    def resliceCS_X_to_imageCS(self, resliceX):
        matrix = self.getCurrentResliceMatrix()
        inv_matrix = vtk.vtkMatrix4x4()
        vtk.vtkMatrix4x4.Invert(matrix, inv_matrix)
        return inv_matrix.MultiplyPoint([resliceX[0], resliceX[1], resliceX[2], 1])[:3]


    def imageCS_To_WorldCS_X(self, imageCS_X, sliceID=None):
        """Convert image coordinates to world coordinates - need sliceID else will look at current
        **not dealing with orientation change**
            1. Convert image coordinates to reslice coordinates
            2. Get IJK coordinates in reslice coordinates
            3. Convert IJK coordinates to world coordinates using PatientMeta
        """
        worldX_in_reslice = self.imageCS_to_ResliceCS_X(imageCS_X, sliceID)
        ijk_in_reslice = self.getIJKAtX(worldX_in_reslice)
        if ijk_in_reslice is None:
            return None
        imageCS_ijk = np.array([ijk_in_reslice[0], ijk_in_reslice[1], ijk_in_reslice[2]])
        return np.array(self.patientMeta.imageToPatientCoordinates(imageCS_ijk))


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


    def hardReset(self):
        self.__setupNewImageData()


    def __setupNewImageData(self): # ONLY ON NEW DATA LOAD
        self.setScalarRangeDictionary()
        # Set background color
        self.renderer.SetBackground(0.1, 0.1, 0.1)
        # Create image actor for slice display
        self.imageActor = vtk.vtkImageActor()
        self.renderer.AddActor(self.imageActor)
        # Update to show current slice
        self.updateImageSlice()
        # Set initial window level based on data
        self.resetWindowLevel()
        # Render
        self.cameraReset()
        self.cameraReset3D()


    # ======================== RENDERING ===============================================================================
    def updateViewAfterSliceChange(self):
        self.renderWindow.Render()
    
    def updateImageSlice(self):
        """Update the image actor to show the current slice using pre-built reslices"""
        if not hasattr(self, 'imageActor') or not self.imageActor:
            logger.warning("Image actor not initialized")
            return
        currentReslice = self.getCurrentReslice()
        if currentReslice is not None:
            thisImageSlice = currentReslice.GetOutput()
            self.imageActor.SetInputData(thisImageSlice)
        else:
            logger.warning("No reslice available for slice %d", self.currentSliceID)


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
        # Calculate base point size
        basePointSize = self.boundingDist * 0.01
        
        # Get zoom factor and adjust point size accordingly
        zoom_factor = self.getZoomFactor()
        # As we zoom in (zoom_factor > 1), we want smaller points
        # As we zoom out (zoom_factor < 1), we want larger points
        pointSize = basePointSize / zoom_factor
        
        # Clamp point size to reasonable range
        pointSize = max(basePointSize * 0.1, min(basePointSize * 5.0, pointSize))

        ptsActor = self.Markups.getAllPointsActors(self.currentTimeID, pointSize, sliceID=self.currentSliceID)
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

    def interpolateSplinesFromManualKeyframes(self):
        """Replace missing splines and automatic (interpolated) splines using linear interpolation in time between manual keyframes."""
        try:
            n_pts_i = 50
            periodic_time = self.temporalPeriodicSplineCheck.isChecked()
            splines_list = self.Markups.getSplinesTimeIDList()
            times = self.times
            n_times = len(times)
            counts = [len(splines_list[t]) for t in range(n_times)]
            if any(c > 1 for c in counts):
                raise ValueError("Interpolation expects at most one spline per time step.")

            def spline_at(tidx):
                return splines_list[tidx][0] if counts[tidx] else None

            kf = [t for t in range(n_times) if counts[t] and spline_at(t).isManual]
            if len(kf) < 2:
                raise ValueError(
                    "Need manual splines at at least two time points.\n"
                    "(Orange = manual keyframe; cyan = automatic.)")

            slice_id = spline_at(kf[0]).sliceID
            t_kf = np.array([times[i] for i in kf], dtype=float)
            P_kf = []
            for t in kf:
                P = spline_at(t).getPoints(nSplinePts=n_pts_i)
                if P.shape[1] != 3:
                    raise ValueError("Spline geometry must be planar (3xN sampled points).")
                P_kf.append(P.T)

            # n_curve = P_kf[0].shape[0]
            n_curve = 12
            curve_IDs = [int(i) for i in np.linspace(0, n_pts_i-1, n_curve-1)]
            curve_IDs.append(0)
            targets = []
            for ti in range(n_times):
                if counts[ti] == 0:
                    targets.append(ti)
                elif not spline_at(ti).isManual:
                    targets.append(ti)

            if not targets:
                QtWidgets.QMessageBox.information(
                    self, "Interpolate splines",
                    "No automatic or missing splines to update; all time steps are manual keyframes.")
                return

            for ti in targets:
                self.Markups.clearSplinesAtTime(ti)
                t_eval = float(times[ti])
                x_row = np.zeros(n_curve)
                y_row = np.zeros(n_curve)
                for k in range(n_curve):
                    xs = np.array([P_kf[j][0, curve_IDs[k]] for j in range(len(kf))])
                    ys = np.array([P_kf[j][1, curve_IDs[k]] for j in range(len(kf))])
                    x_row[k] = _interp_scalar_in_time(t_eval, t_kf, xs, times, periodic_time)
                    y_row[k] = _interp_scalar_in_time(t_eval, t_kf, ys, times, periodic_time)
                new_pts = [[float(x_row[k]), float(y_row[k]), 0.0] for k in range(n_curve)]
                time_val = times[ti]
                reslice = self.resliceDict[time_val][slice_id]
                self.Markups.addSpline(
                    new_pts,
                    reslice,
                    self.renderer,
                    self.graphicsViewVTK,
                    timeID=ti,
                    sliceID=slice_id,
                    LOOP=self.splineClosed,
                    is_manual=False,
                )
            self._updateMarkups()
            logger.info("Interpolated %d automatic spline(s) from %d manual keyframes.", len(targets), len(kf))
        except ValueError as e:
            QtWidgets.QMessageBox.warning(self, "Interpolate splines", str(e))


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

