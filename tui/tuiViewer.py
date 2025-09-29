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
from tui import tuiMarkups, tuiStyles, tuiUtils, tuimarkupui, baseMarkupViewer

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
class TUIMarkupViewer(tuimarkupui.QtWidgets.QMainWindow, tuimarkupui.Ui_BASEUI, baseMarkupViewer.BaseMarkupViewer):
    """
    UI for control of NMRViewer:
    Displays GUI
    Connects GUI buttons to source
    """
    def __init__(self):
        super(TUIMarkupViewer, self).__init__()
        self.setupUi(self)
        # Initialize base class
        baseMarkupViewer.BaseMarkupViewer.__init__(self, VERBOSE=False)
        
        # 3D-specific defaults
        self.currentSliceID = 0
        self.limitContourToOne = True
        self.minContourLength = 0.1
        self.contourVal = None
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
        layout = tuimarkupui.QtWidgets.QVBoxLayout(self.graphicsView)
        layout.addWidget(self.graphicsViewVTK)
        self.graphicsView.setLayout(layout)
        ##
        # print(self.graphicsViewVTK) # vtkRenderWindowInteractor
        # print(self.graphicsViewVTK.GetRenderWindow())
        # print(self.graphicsViewVTK.GetInteractorStyle()) # vtkInteractorStyleSwitch
        ##
        self.renderWindow = self.graphicsViewVTK.GetRenderWindow()
        self.rendererArray = [vtk.vtkRenderer(), vtk.vtkRenderer(), vtk.vtkRenderer(), vtk.vtkRenderer()]
        for k1 in range(4):
            self.renderWindow.AddRenderer(self.rendererArray[k1])
        self.renderWindow.SetMultiSamples(0)
        self.resliceCursorWidgetArray = [None] * 3  # [Bot R, Bot L, Top L]
        self.resliceCursor = vtk.vtkResliceCursor()

        self.picker = vtk.vtkPointPicker()
        self.picker.SetTolerance(0.005)
        self.worldPicker = vtk.vtkWorldPointPicker()
        #
        self.interactionState = None
        self.interactionView = None
        self.graphicsViewVTK.Initialize()
        self.graphicsViewVTK.Start()
        #
        self.viewButtonList = [None] * 5
        self.connections()
        # Markups already initialized in base class
        self.threeDContourActor = None
        self.planeActors3 = []
        self.markupActorList = []
        self.renderer3D = None
        self.interactorStyleDict = {'Image': tuiStyles.ImageInteractor(self),
                                    'Trackball': vtk.vtkInteractorStyleTrackballCamera()}
        self.graphicsViewVTK.SetInteractorStyle(self.interactorStyleDict['Image'])
        
        # Set file dialog reference for base class
        self.fileDialog = tuimarkupui.QtWidgets.QFileDialog
        
        self.show()

    # ==========================================================
    #   CONNECTIONS
    def connections(self):
        # Setup common connections from base class
        self._setupCommonConnections()
        
        # 3D-specific connections
        self.axialButton.clicked.connect(self.__axialButtonAction)
        self.saggitalButton.clicked.connect(self.__saggitalButtonAction)
        self.coronalButton.clicked.connect(self.__coronalButtonAction)
        self.threeDButton.clicked.connect(self.__threeDButtonAction)
        self.gridViewButton.clicked.connect(self.__gridButtonAction)
        self.viewButtonList = [self.saggitalButton, self.coronalButton, self.axialButton, self.threeDButton, self.gridViewButton]
        #
        # 3D-specific connections
        self.cursor3DCheck.stateChanged.connect(self.cursor3DChange)
        
        # Image manipulation buttons
        self.imManip_A.clicked.connect(self.toggleCrosshairs)
        # self.imManip_B.clicked.connect(self.rotateCamera90)
        ##
        self.updatePushButtonDict()

    # Push button methods inherited from base class

    # Custom sliders removed - using animation controls instead

    # Time slider methods inherited from base class

    # SLICE SLIDER
    def _getDeltaX(self):
        return np.mean(self.getCurrentVTIObject().GetSpacing())#[self.interactionView] # ?? is this best, or mean ??

    def scrollForwardCurrentSlice1(self):
        if self.interactionView < 3: # If in 3D window then do nothing
            cp = np.array(self.resliceCursor.GetCenter())
            nn = np.array(self.getCurrentViewNormal())
            dx = self._getDeltaX()
            self.resliceCursor.SetCenter(cp + nn * dx)
            self._updateMarkups() # will render

    def scrollBackwardCurrentSlice1(self):
        if self.interactionView < 3: # If in 3D window then do nothing
            cp = np.array(self.resliceCursor.GetCenter())
            nn = -1.0 * np.array(self.getCurrentViewNormal())
            dx = self._getDeltaX()
            self.resliceCursor.SetCenter(cp + nn * dx)
            self._updateMarkups()

    # BUTTONS
    def updateParallelScale(self, viewID):
        # Take viewID. GetParallelScale - set other views to same
        if viewID < 3: # If 3D view do nothing
            ps = self.rendererArray[self.interactionView].GetActiveCamera().GetParallelScale()
            for i in range(3):
                if i != viewID:
                    self.rendererArray[i].GetActiveCamera().SetParallelScale(ps)
            self.renderWindow.Render()

    def cameraReset(self):
        viewUp = [[0, 0, 1], [0, 0, 1], [0, -1, 0]]
        for i in range(3):
            self.resliceCursorWidgetArray[i].ResetResliceCursor()
            self.rendererArray[i].GetActiveCamera().SetFocalPoint(0, 0, 0)
            camPos = [0, 0, 0]
            camPos[i] = 1
            self.rendererArray[i].GetActiveCamera().SetPosition(camPos)
            self.rendererArray[i].GetActiveCamera().ParallelProjectionOn()
            self.rendererArray[i].GetActiveCamera().SetViewUp(viewUp[i])
            self.rendererArray[i].GetActiveCamera().Zoom(2.5)
            self.rendererArray[i].ResetCamera()
        self.renderWindow.Render()

    def cameraReset3D(self):
        self.rendererArray[3].ResetCameraClippingRange()
        self.renderWindow.Render()

    def toggleCrosshairs(self): 
        if self.imManip_A.isChecked():
            self.__updateCrosshairs(True)
        else:
            self.__updateCrosshairs(False)
        self.renderWindow.Render()

    def _getHelpFileName(self):
        """Override to specify TUI-specific help file"""
        return "help_tui.txt"

    # Window level methods inherited from base class

    def getWindowLevel(self):
        w = self.resliceCursorWidgetArray[self.interactionView].GetRepresentation().GetWindow()
        l = self.resliceCursorWidgetArray[self.interactionView].GetRepresentation().GetLevel()
        return w, l

    def setWindowLevel(self, w, l):
        for i in range(1,3):
            self.resliceCursorWidgetArray[i].GetRepresentation().SetWindowLevel(w, l)
        for i in range(1,3):
            self.resliceCursorWidgetArray[i].GetRepresentation().SetLookupTable(self.resliceCursorWidgetArray[0].GetRepresentation().GetLookupTable())
        self.renderWindow.Render()



    # GRID VIEW LAYOUT
    def __resetViewsButtons(self, viewID):
        for i in range(5):
            if i == viewID:
                self.viewButtonList[i].setChecked(1)
            else:
                self.viewButtonList[i].setChecked(0)
    def setGrossFrame(self, viewID):
        if (viewID > 3) or (viewID < 0):
            viewID = 4
            self.__frameReset()
        else:
            self.__grossView(viewID)
        self.__resetViewsButtons(viewID)
        self.renderWindow.Render()
    def __grossView(self, viewID):
        dy, cy = [0, 0.33, 0.66, 1], 0
        dx = 0.8 # % of renderwindow that large view will occupy
        for k1 in range(4):
            if k1 == viewID:
                self.rendererArray[k1].SetViewport(0, 0, dx, 1)
            else:
                self.rendererArray[k1].SetViewport(dx, dy[cy], 1, dy[cy + 1])
                cy += 1
    def __frameReset(self):
        self.rendererArray[0].SetViewport(0, 0, 0.5, 0.5)
        self.rendererArray[1].SetViewport(0.5, 0, 1, 0.5)
        self.rendererArray[2].SetViewport(0, 0.5, 0.5, 1)
        self.rendererArray[3].SetViewport(0.5, 0.5, 1, 1)
        self.renderWindow.Render()
    def __axialButtonAction(self):
        if self.axialButton.isChecked():
            self.setGrossFrame(2)
    def __saggitalButtonAction(self):
        if self.saggitalButton.isChecked():
            self.setGrossFrame(0)
    def __coronalButtonAction(self):
        if self.coronalButton.isChecked():
            self.setGrossFrame(1)
    def __threeDButtonAction(self):
        if self.threeDButton.isChecked():
            self.setGrossFrame(3)
    def __gridButtonAction(self):
        if self.gridViewButton.isChecked():
            self.setGrossFrame(4)


    def setContourVal(self, val):
        self.contourVal = val
        # self.contourLineEdit.setText('%5.0f'%(self.contourVal))
        self.__update3DSurfaceView()

    def cursor3DChange(self):
        if self.cursor3DCheck.isChecked():
            self.__update3DCursor(SHOW=True)
        else:
            self.__update3DCursor(SHOW=False)

    # Markup mode methods inherited from base class

    # Array selection methods inherited from base class

    # File loading methods inherited from base class


    ## -------------------------- END UI SETUP -----------------------------------
    # ==================================================================================================================
    def _setupViewerSpecificData(self):
        """3D-specific setup after data load"""
        self.__setupNewImageData() ## MAIN SETUP HERE ##
        ii = list(self.vtiDict.values())[0]
        dims = [0,0,0]
        ii.GetDimensions(dims)
        self.currentSliceID = int(dims[2]/2.0)
        self.setGrossFrame(4) # Make grid view default


    # Exit method inherited from base class

    # ==================================================================================================================
    # RESCLIE CURSOR WIDGET CALLBACKS
    def ResliceCursorStartCallback(self, obj, event):
        thisLineRepresentation = obj.GetResliceCursorRepresentation()
        self.interactionState = thisLineRepresentation.GetInteractionState()
        if self.interactionView == 3:
            self.interactionState = 3  # Force 3D view state
    

    def ResliceCursorCallback(self, obj, event):
        if self.interactionView == 3:  # In 3D view
            self.interactionState = None
            # print(self.interactionView, " exiting")
            obj.GetInteractor().ExitCallback()
            return
        # Check if interaction is within current renderer's viewport
        x, y = obj.GetInteractor().GetEventPosition()
        renderer = obj.GetDefaultRenderer()
        if not renderer.IsInViewport(x, y):
            obj.GetInteractor().ExitCallback()
            return
        
        if self.interactionState and self.interactionState > 4:
            obj.GetResliceCursorRepresentation().ComputeInteractionState(x, y, 1)
            self._updateMarkups()

    def ResliceCursorEndCallback(self, obj, event):
        self.interactionState = 0

    # ==================================================================================================================
    #   DATA - 3D specific methods

    def getCurrentRenderer(self):
        return self.rendererArray[self.interactionView]

    def getCurrentX(self): # point X under reslice cursor
        return self.resliceCursor.GetCenter()

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
        # Get the current reslice cursor widget
        if self.interactionView >2:
            return None
        widget = self.resliceCursorWidgetArray[self.interactionView]
        if widget is None:
            return None
        
        # Get the reslice cursor representation
        rep = widget.GetRepresentation()
        
        # Get the plane source
        planeSource = rep.GetPlaneSource()
        
        # Get the plane normal and origin
        normal = planeSource.GetNormal()
        origin = planeSource.GetOrigin()
        
        # Create a plane implicit function
        plane = vtk.vtkPlane()
        plane.SetNormal(normal)
        plane.SetOrigin(origin)
        
        # Create a point picker
        picker = vtk.vtkPointPicker()
        picker.SetTolerance(0.005)
        
        # Pick the point
        picker.Pick(mouseX, mouseY, 0, self.rendererArray[self.interactionView])
        
        # Get the picked point
        pickedPoint = picker.GetPickPosition()
        
        # Project the picked point onto the plane
        projectedPoint = [0, 0, 0]
        plane.ProjectPoint(pickedPoint, origin, normal, projectedPoint)
        
        return projectedPoint

    def getCurrentViewNormal(self): # uses view under mouse
        return np.array(self.resliceCursorWidgetArray[self.interactionView].GetResliceCursorRepresentation().GetPlaneSource().GetNormal())

    def getViewNormal(self, i):
        if (i<0) or (i>2):
            return None
        return np.array(self.resliceCursorWidgetArray[i].GetResliceCursorRepresentation().GetPlaneSource().GetNormal())


    def getCurrentReslice(self):
        return self.resliceCursorWidgetArray[self.interactionView].GetRepresentation().GetReslice()


    def getCurrentResliceMatrix(self):
        return self.resliceCursorWidgetArray[self.interactionView].GetRepresentation().GetReslice().GetResliceAxes()


    def getCurrentResliceAsVTP(self):
        ii = self.getCurrentResliceAsVTI(COPY=True)
        pp = vtkfilters.transformImageData(ii, self.getCurrentResliceMatrix())
        return vtkfilters.filterExtractSurface(pp)
    

    def getCurrentResliceAsVTI(self, COPY=False):
        ii = self.getCurrentReslice().GetOutput()
        if COPY:
            iRS = vtk.vtkImageData()
            iRS.ShallowCopy(ii)
            return iRS
        return ii


    def __setupNewImageData(self): # ONLY ON NEW DATA LOAD
        self._BaseMarkupViewer__setScalarRangeForCurrentArray()
        ##
        center = self.getCurrentVTIObject().GetCenter()
        self.resliceCursor.SetCenter(center[0], center[1], center[2])
        self.resliceCursor.SetThickMode(0)
        self.resliceCursor.SetThickness(0.01, 0.01, 0.01)
        self.resliceCursor.SetHole(2)
        self.resliceCursor.SetImage(self.getCurrentVTIObject())
        # 2D Reslice cursor widgets
        sR = self.scalarRange[self.currentArray]
        
        # Calculate cursor length based on image bounds
        bounds = self.getCurrentVTIObject().GetBounds()
        diagonalLength = ((bounds[1]-bounds[0])**2 + 
                         (bounds[3]-bounds[2])**2 + 
                         (bounds[5]-bounds[4])**2)**0.5
        cursorLength = diagonalLength * 0.25  # Adjust this factor to change cursor length
        
        for i in range(3):
            self.resliceCursorWidgetArray[i] = vtk.vtkResliceCursorWidget()
            rscRep = vtk.vtkResliceCursorLineRepresentation()
            rscRep.GetResliceCursorActor().GetCursorAlgorithm().SetResliceCursor(self.resliceCursor)
            rscRep.GetResliceCursorActor().GetCursorAlgorithm().SetReslicePlaneNormal(i)
            
            # Set cursor properties to control its appearance
            for i2 in range(3):
                centerlineProperty = rscRep.GetResliceCursorActor().GetCenterlineProperty(i2)
                centerlineProperty.SetRepresentationToWireframe()
                centerlineProperty.SetLineWidth(2)  # Make lines more visible
                # Try to limit the line length by clipping
                centerlineProperty.SetPointSize(cursorLength)
            w, l = self._BaseMarkupViewer__calculateOptimalWindowLevel()
            rscRep.SetWindowLevel(w, l, 0)
            if i > 0:
                rscRep.SetLookupTable(self.resliceCursorWidgetArray[0].GetRepresentation().GetLookupTable())
            
            # Try to constrain the widget to its renderer
            rscRep.GetResliceCursorActor().GetCursorAlgorithm().SetReslicePlaneNormal(i)
            rscRep.RestrictPlaneToVolumeOn()
            
            self.resliceCursorWidgetArray[i].SetInteractor(self.graphicsViewVTK)
            self.resliceCursorWidgetArray[i].SetRepresentation(rscRep)
            self.resliceCursorWidgetArray[i].SetDefaultRenderer(self.rendererArray[i])
            self.resliceCursorWidgetArray[i].SetEnabled(1)
            self.resliceCursorWidgetArray[i].GetRepresentation().GetReslice().SetInterpolationModeToLinear()
            self.resliceCursorWidgetArray[i].AddObserver('StartInteractionEvent', self.ResliceCursorStartCallback)
            self.resliceCursorWidgetArray[i].AddObserver('InteractionEvent', self.ResliceCursorCallback)
            self.resliceCursorWidgetArray[i].AddObserver('EndInteractionEvent', self.ResliceCursorEndCallback)
            self.resliceCursorWidgetArray[i].RemoveObservers("KeyPressEvent")
            self.resliceCursorWidgetArray[i].RemoveObservers("CharEvent")

        # Background
        for i in range(4):
            self.rendererArray[i].SetBackground(self.planeBackgroundColors[i])
        # 3D
        dims = [0,0,0]
        self.getCurrentVTIObject().GetDimensions(dims)
        if np.prod(dims) < 60e+6: # For very large data - don't want to do this
            print(f"Working with current array: {self.currentArray}")
            A = vtkfilters.getArrayAsNumpy(self.getCurrentVTIObject(), self.currentArray)
            A = A[A>1.0]
            contourVal = np.mean(A) * 2.0
            print(f"Made contour at value: {int(contourVal)}")
            self.setContourVal(contourVal)
        ##
        # Render
        self.__frameReset()
        self.cameraReset()
        self.cameraReset3D()


    # ======================== RENDERING ===============================================================================
    def updateViewAfterTimeChange(self): # NEED TO TRIGGER ON A TIME CHANGE
        self.resliceCursor.SetImage(self.getCurrentVTIObject()) # FIXME - check the picker
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
            for i in range(4):
                self.rendererArray[i].RemoveActor(iActor)
        self.markupActorList = []

    def _updateMarkups(self, window=None, level=None):
        self.clearCurrentMarkups()
        ## POINTS
        pointSize = self.boundingDist * 0.01
        # Show lines when in spline mode, otherwise use the original logic
        SHOW_LINES = self.splineClosed # If spline closed (but points) then show a closed line
        LOOP = self.splineClosed  # Use the spline closed setting
        tfA = [i==j for i,j in zip([1,0,0], self.getViewNormal(0))]
        tfB = [i==j for i,j in zip([0,-1,0], self.getViewNormal(1))]
        if (not all(tfA)) or (not all(tfB)):
            SHOW_LINES = False

        ptsActor = self.Markups.getAllPointsActors(self.currentTimeID, pointSize)
        if ptsActor is not None:
            # We add to 3D and then only to other views if all points withon 2 delta X of slice
            self.rendererArray[3].AddActor(ptsActor)
            self.markupActorList.append(ptsActor)
            if SHOW_LINES:
                lineWidth = 3 if self.markupMode == 'Spline' else pointSize*0.9
                lineActor = self.Markups.getAllPointsLineActor(self.currentTimeID, lineWidth, LOOP)
                self.rendererArray[3].AddActor(lineActor)
                self.markupActorList.append(lineActor)
            cpX = self.resliceCursor.GetCenter()
            for i in range(3):
                nn = self.getViewNormal(i)
                ptsActor_i = self.Markups.getAllPointsActors(self.currentTimeID, pointSize, cpX, nn, pointSize*0.9)
                if ptsActor_i is not None:
                    self.rendererArray[i].AddActor(ptsActor_i)
                    self.markupActorList.append(ptsActor_i)
                    if SHOW_LINES:
                        lineWidth = 3
                        lineActor_i = self.Markups.getAllPointsLineActor(self.currentTimeID, lineWidth, LOOP, cpX, nn, pointSize*0.9)
                        if lineActor_i is not None:
                            self.rendererArray[i].AddActor(lineActor_i)
                            self.markupActorList.append(lineActor_i)
        ## POLYDATA
        pdActors = self.Markups.getAllPolydataActors(self.currentTimeID)
        if len(pdActors) > 0:
            for ipdActor in pdActors:
                self.rendererArray[3].AddActor(ipdActor)
                self.markupActorList.append(ipdActor)
        ## SPLINE - splines disabled in TUI
        # self.Markups.showSplines_timeID_CP(self.currentTimeID, self.resliceCursor.GetCenter(), self.getViewNormal(2), pointSize*0.9)
        if (window is not None) and (level is not None):
            self.setWindowLevel(window, level)
        self.renderWindow.Render()

    def __updateCrosshairs(self, SHOW):
        for i in range(3):
            iActor = self.resliceCursorWidgetArray[i].GetRepresentation().GetResliceCursorActor()
            if SHOW:
                self.rendererArray[i].AddActor(iActor)
            else:
                self.rendererArray[i].RemoveActor(iActor)
        self.renderWindow.Render()


    def __update3DCursor(self, SHOW):
        iActor = self.resliceCursorWidgetArray[2].GetRepresentation().GetResliceCursorActor()
        if SHOW:
            self.rendererArray[3].AddActor(iActor)
        else:
            self.rendererArray[3].RemoveActor(iActor)
        self.renderWindow.Render()

    def __update3DSurfaceView(self):
        self.rendererArray[3].RemoveActor(self.threeDContourActor)
        if self.contourVal:
            cc, ccActor = self.__get3DContourActor()
            self.threeDContourActor = ccActor
            self.rendererArray[3].AddActor(self.threeDContourActor)
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