#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
Created on 13 March 2019

Major update May 2022.
Change to ResliceCursorWidget and Markups in 3D space (rather than sliceID etc)

@author: Fraser M. Callaghan
@email: callaghan.fm@gmail.com
"""

import vtk
import numpy as np
from ngawari import vtkfilters
from scipy import ndimage


### ====================================================================================================================
### COORDINATE SYSTEM ABSTRACTION
### ====================================================================================================================


### ====================================================================================================================
### ====================================================================================================================
Points = 'Points'
Splines = 'Splines'
Polydata = 'Polydata'
Masks = 'Masks'

### ====================================================================================================================
### ====================================================================================================================
class Markups(object):
    """
    This is really a convienience class to take care of access to all markups
    Only use methods here.
    """
    def __init__(self, parent, nTimes=0):
        self.parentImageViewer = parent
        self.nTimes = nTimes
        self.markupsDict = {} # Dict(k=typestr, v=Dict(k=timeID, v=list_of_markup))
        self.markupsTypesCollections = {Points: MarkupPoints,
                                        Splines: MarkupSplines,
                                        Polydata: MarkupPolydatas,
                                        Masks: MarkupMasks}
        self.reset()


    def initForNewData(self, nTimes):
        self.nTimes = nTimes
        self.reset()


    def __genEmptyDict(self, CollectionClass):
        if CollectionClass is not None:
            if CollectionClass == MarkupPoints:
                return dict(zip(range(self.nTimes), [CollectionClass() for _ in range(self.nTimes)]))
            elif CollectionClass == MarkupSplines:
                return dict(zip(range(self.nTimes), [CollectionClass() for _ in range(self.nTimes)]))
            else:
                return dict(zip(range(self.nTimes), [CollectionClass() for _ in range(self.nTimes)]))
        else:
            return dict(zip(range(self.nTimes), [[] for _ in range(self.nTimes)]))


    def reset(self, timeID=None, markupType_list=()):
        if len(markupType_list) == 0:
            markupType_list = self.markupsTypesCollections.keys()
        # Clean up spline widgets before resetting
        if Splines in markupType_list or len(markupType_list) == 0:
            self._cleanupSplineWidgets(timeID)
        if timeID is None:
            for iType in markupType_list:
                self.markupsDict[iType] = self.__genEmptyDict(self.markupsTypesCollections.get(iType, None))
        else:
            for iType in markupType_list:
                self.markupsDict[iType][timeID] = self.markupsTypesCollections.get(iType, None)


    def resetMarkup(self, markupType):
        self.reset(markupType_list=[markupType])


    def _cleanupSplineWidgets(self, timeID=None):
        """Clean up spline widgets by properly disabling and removing them from interactor"""
        if Splines not in self.markupsDict:
            return
            
        if timeID is None:
            # Clean up all spline widgets
            for tID in self.markupsDict[Splines].keys():
                for spline in self.markupsDict[Splines][tID]:
                    self._disableSplineWidget(spline)
        else:
            # Clean up spline widgets for specific timeID
            if timeID in self.markupsDict[Splines]:
                for spline in self.markupsDict[Splines][timeID]:
                    self._disableSplineWidget(spline)


    def _disableSplineWidget(self, spline):
        """Properly disable a spline widget and remove it from interactor"""
        try:
            # Disable the widget
            spline.SetEnabled(0)
            spline.Off()
            # Try to remove observers to prevent memory leaks
            try:
                spline.RemoveAllObservers()
            except:
                pass
            # Force render update to ensure widget is visually removed
            if hasattr(self.parentImageViewer, 'renderWindow'):
                self.parentImageViewer.renderWindow.Render()
        except Exception as e:
            # If there's an error disabling the widget, just continue
            # This prevents crashes if the widget is already destroyed
            if hasattr(self.parentImageViewer, 'VERBOSE') and self.parentImageViewer.VERBOSE:
                print(f"Warning: Error disabling spline widget: {e}")


    # ============ POINTS ==============================================================================================
    def getNumberOfPoints(self, timeID):
        return len(self.markupsDict[Points][timeID])


    def _addPoint(self, X_image, X_world, timeID, sliceID, norm=None, orientation=None):
        self.markupsDict[Points][timeID].addPoint(X_image, X_world, norm, timeID, sliceID, orientation)

    def convertPointsToSpline(self, timeID, sliceID, orientation):
        self.markupsDict[Splines][timeID].addSpline(self.markupsDict[Points][timeID].getImage_np(), 
                                                    reslice=self.parentImageViewer.getCurrentReslice(), 
                                                    renderer=self.parentImageViewer.getCurrentRenderer(), 
                                                    interactor=self.parentImageViewer.graphicsViewVTK, 
                                                    handDrawn=True,
                                                    LOOP=self.parentImageViewer.splineClosed,
                                                    timeID=timeID, 
                                                    sliceID=sliceID,
                                                    orientation=orientation)
        self.markupsDict[Points][timeID] = MarkupPoints()


    def addPoint(self, X_image, X_world, timeID, sliceID, norm=None, orientation=None):
        if self.parentImageViewer.markupMode == 'Spline':
            self._addSplinePoint(X_image, X_world, timeID, sliceID, norm, orientation)
        else:
            self._addPoint(X_image, X_world, timeID, sliceID, norm, orientation=orientation)

    def _addSplinePoint(self, X_image, X_world, timeID, sliceID, norm=None, orientation=None):
        if self.markupsDict[Splines][timeID].isSplineOnThisSlice(sliceID):
            print("Interact with the spline widget to add a point")
            print("    Shift+LMB: move a spline handle")
            print("    CTRL+RMB: remove a spline handle")
            print("    MMB: translate spline")
            print("    RMB: scale spline")
        elif len(self.markupsDict[Points][timeID]) == 2:
            self._addPoint(X_image, X_world, timeID, sliceID, norm)
            self.convertPointsToSpline(timeID, sliceID, orientation)
        else:
            self._addPoint(X_image, X_world, timeID, sliceID, norm, orientation=orientation)

    def removeLastPoint(self, timeID):
        try:
            self.markupsDict[Points][timeID].removePoint(-1)
        except IndexError:
            pass
    # ============ SPLINES =============================================================================================
    def addSpline(self, pts, reslice, renderer, interactor, timeID, sliceID, LOOP, isHandDrawn=True):
        self.markupsDict[Splines][timeID].addSpline(pts, reslice, renderer, interactor, handDrawn=isHandDrawn, LOOP=LOOP, timeID=timeID, sliceID=sliceID)

    # NOT USED
    def showSplines_timeID_CP(self, timeID, CP, N, dx): # Used by TUI
        for iTimeID in self.markupsDict[Splines].keys():
            for iSpline in self.markupsDict[Splines][timeID]:
                if iTimeID == timeID:
                    ABCD = iSpline.getPlane()
                    if planes_within_tol(ABCD, CP, N, dx):
                        iSpline.SetEnabled(1)
                        iSpline.On()
                    else:
                        iSpline.SetEnabled(0)
                        iSpline.Off()
                else:
                    iSpline.SetEnabled(0)
                    iSpline.Off()


    def showSplines_timeID_sliceID(self, timeID, sliceID): # Used by PIWAKAWAKA
        for iTimeID in self.markupsDict[Splines].keys():
            for iSpline in self.markupsDict[Splines][iTimeID]:
                if iTimeID == timeID and iSpline.sliceID == sliceID:
                    iSpline.SetEnabled(1)
                    iSpline.On()
                else:
                    iSpline.SetEnabled(0)
                    iSpline.Off()

 
    def getSplinesTimeIDList(self):
        """Get splines list for each time"""
        return [self.markupsDict[Splines].get(iTimeID, []) for iTimeID in range(self.nTimes)]

    def getSplinePolyData(self, timeID, nSplinePts=100):
        return self.markupsDict[Splines][timeID].getSplinePolyData_WorldCS(self.parentImageViewer.imageCS_To_WorldCS_X, nSplinePts)


    def getAllPointsActors(self, timeID, pointSize, boundCP=None, boundN=None, bounddx=None, sliceID=None):
        return self.markupsDict[Points][timeID].getActorForAllPoints(pointSize, boundCP, boundN, bounddx, sliceID=sliceID)

    def getAllPointsLineActor(self, timeID, lineWidth=3, LOOP=False, boundCP=None, boundN=None, bounddx=None):
        return self.markupsDict[Points][timeID].getLineActorForAllPoints(lineWidth, LOOP, boundCP, boundN, bounddx)

    def getPolyDataFromPoints(self, timeID):
        return self.markupsDict[Points][timeID].getPolyData()

    def getXNumpyFromPoints(self, timeID):
        return self.markupsDict[Points][timeID].getWorld_np()
    
    def getAllPointsForTime(self, timeID):
        """Get all points for a specific time"""
        return self.markupsDict[Points].get(timeID, [])

    # ============ POLYDATA ============================================================================================
    def addPolydata(self, polydata, timeID, sliceID, color=(0,0,1)):
        self.markupsDict[Polydata][timeID].addPolydata(polydata, timeID=timeID, sliceID=sliceID, color=color)

    def getAllPolydataActors(self, timeID):
        return self.markupsDict[Polydata][timeID].getListOfActors()

### ====================================================================================================================
### MARKUP - PARENT
class Markup(object):
    """
    Parent class for Markup with coordinate system awareness
    """
    def __init__(self, timeID=0, sliceID=0, orientation=None):
        self.timeID = timeID
        self.sliceID = sliceID
        self.orientation = orientation
    
### ====================================================================================================================
### MARKUP - POINTS-LIST
class MarkupPoints(list):
    def __init__(self):
        super(MarkupPoints, self).__init__([])
        self.lineRGB = [1, 0.5, 0.7]

    def addPoint(self, X_image, X_world, norm=None, timeID=0, sliceID=0, orientation=None):
        # X is expected to be in image coordinates
        point = MarkupPoint(X_image, X_world, norm=norm, timeID=timeID, sliceID=sliceID, orientation=orientation)
        self.append(point)

    def removePoint(self, ID=-1):
        self.pop(ID)

    def getImage_np(self):
        return np.array([i.X_image for i in self])

    def getWorld_np(self):
        return np.array([i.X_world for i in self])

    def getPolyData(self):
        pp = vtkfilters.buildPolydataFromXYZ(self.getWorld_np())
        nn = np.array([i.norm for i in self])
        vtkfilters.setArrayFromNumpy(pp, nn, "normal", SET_VECTOR=True)
        return pp

    def getPointsWithinBounds(self, CP, N, delta):
        print(f"DEBUG: X:{self.getImage_np()}, CP: {CP}, N:{N}, dx:{delta}")
        dists = [abs(vtkfilters.ftk.distanceToPlane(i, N, CP)) for i in self.getImage_np()]
        tf = np.array(dists) < delta
        return [i for iTF,i in zip(tf, self) if iTF]

    def getPolyLine(self, LOOP=False):
        if len(self) < 2:
            return None
        pp = vtkfilters.buildPolyLineFromXYZ(self.getWorld_np(), LOOP)
        return pp

    def getPolyLine_ImageCS(self, LOOP=False, boundCP=None, boundN=None, bounddx=None):
        if len(self) < 2:
            return None
        if boundCP is not None:
            subList = self.getPointsWithinBounds(boundCP, boundN, bounddx)
            if len(subList) == 0:
                return None
            pp = vtkfilters.buildPolyLineFromXYZ(np.array([i.X_image for i in subList]), LOOP)
        else:
            pp = vtkfilters.buildPolyLineFromXYZ(self.getImage_np(), LOOP)
        return pp

    def getAllPointsPolyData_ImageCS(self, pointSize, boundCP=None, boundN=None, bounddx=None, sliceID=None):
        if len(self) == 0:
            return None
        if boundCP is not None:
            subList = self.getPointsWithinBounds(boundCP, boundN, bounddx)
            if len(subList) == 0:
                return None
            allData = [i.getSphereSource_Image(pointSize) for i in subList]
        elif sliceID is not None:
            allData = [i.getSphereSource_Image(pointSize) for i in self if i.sliceID==sliceID]
        else:
            allData = [i.getSphereSource_Image(pointSize) for i in self]
        pp = vtkfilters.appendPolyDataList(allData)
        return pp

    def getActorForAllPoints(self, pointSize, boundCP=None, boundN=None, bounddx=None, sliceID=None):
        pp = self.getAllPointsPolyData_ImageCS(pointSize, boundCP=boundCP, boundN=boundN, bounddx=bounddx, sliceID=sliceID)
        if (pp is None) or (pp.GetNumberOfPoints() < 1):
            return None
        ptMapper = vtk.vtkPolyDataMapper()
        ptMapper.SetInputData(pp)
        ptActor = vtk.vtkActor()
        ptActor.GetProperty().SetColor(self[0].farbe)
        ptActor.PickableOff()
        ptActor.SetMapper(ptMapper)
        return ptActor


    def getLineActorForAllPoints(self, lineWidth=3, LOOP=False, boundCP=None, boundN=None, bounddx=None):
        polyLine = self.getPolyLine_ImageCS(LOOP=LOOP, boundCP=boundCP, boundN=boundN, bounddx=bounddx)
        if polyLine is None:
            return None
        lineMapper = vtk.vtkPolyDataMapper()
        lineMapper.SetInputData(polyLine)
        lineActor = vtk.vtkActor()
        lineActor.GetProperty().SetColor(self.lineRGB)
        lineActor.PickableOff()
        lineActor.GetProperty().SetLineWidth(lineWidth)
        lineActor.SetMapper(lineMapper)
        return lineActor


### ====================================================================================================================

### ====================================================================================================================
### MARKUP - POINT
class MarkupPoint(Markup):
    def __init__(self, X_image, x_world, norm=None, timeID=0, sliceID=0, orientation=None):
        Markup.__init__(self, timeID, sliceID, orientation)
        self.X_image = X_image
        self.X_world = x_world
        self.norm = norm
        self.farbe = [1,0,0]
        # potential - hold parent

    def getSphereSource_Image(self, rad=0.002):
        Sx = vtkfilters.buildSphereSource(self.X_image, rad, res=16)
        return Sx

    def getPtActor(self, pointSize):
        ptMapper = vtk.vtkPolyDataMapper()
        ptMapper.SetInputData(self.getSphereSource_Image(pointSize))
        ptActor = vtk.vtkActor()
        ptActor.GetProperty().SetColor(self.farbe)
        ptActor.PickableOff()
        ptActor.SetMapper(ptMapper)
        return ptActor

### ====================================================================================================================
### MARKUP - SPLINES - LIST
class MarkupSplines(list):
    def __init__(self):
        super(MarkupSplines, self).__init__([])

    def addSpline(self, Xarrary_image, reslice, renderer, interactor, handDrawn, LOOP, timeID=0, sliceID=0, orientation=None):
        self.append(MarkupSpline(Xarrary_image, reslice, renderer, interactor, handDrawn, LOOP, timeID=timeID, sliceID=sliceID, orientation=orientation))

    def getSplinePolyData_WorldCS(self, imageToWorld_func, nSplinePts=100):
        return vtkfilters.appendPolyDataList([i.getSplinePolyData_WorldCS(imageToWorld_func, nSplinePts) for i in self])

    def isSplineOnThisSlice(self, sliceID):
        return any([i.sliceID==sliceID for i in self])

### ====================================================================================================================
### MARKUP - SPLINE
class MarkupSpline(Markup, vtk.vtkSplineWidget):
    def __init__(self, handlePoints, reslice, renderer, interactor, handDrawn, LOOP, timeID=0, sliceID=0, orientation=None):
        Markup.__init__(self, timeID, sliceID, orientation)
        vtk.vtkSplineWidget.__init__(self)
        self.LOOP = LOOP
        
        self.SetInteractor(interactor)
        self.SetCurrentRenderer(renderer)
        self.SetInputConnection(reslice.GetOutputPort())

        bnds = reslice.GetOutput().GetBounds()
        self.SetDefaultRenderer(renderer)
        self.PlaceWidget(bnds[0], bnds[1], bnds[2], bnds[3], bnds[4], bnds[5])
        self.ProjectToPlaneOn()
        self.SetProjectionNormalToZAxes()
        self.SetProjectionPosition(0.0)
        self.Off()
        self.SetEnabled(0)

        self._isHandDrawn = handDrawn
        self.GetLineProperty().SetColor(1,0,1)
        ##
        self.SetEnabled(1)
        self.On()
        self.setPoints(handlePoints)
        if self.LOOP:
            self.ClosedOn()
        ##
        self.AddObserver("EndInteractionEvent", self.splineUpdated)


    @property
    def isHandDrawn(self):
        print("Getting value...")
        return self._isHandDrawn

    @isHandDrawn.setter
    def isHandDrawn(self, tf):
        self._isHandDrawn = tf
        if self._isHandDrawn:
            self.SetEnabled(1)
            self.On()
        else:
            self.SetEnabled(0)
            self.Off()

    def splineUpdated(self, obj, event):
        self.isHandDrawn = True
        self.GetLineProperty().SetColor(1,0,0)

    def setPoints(self, pts, subSample=1):
        IDs = list(range(0,len(pts), subSample))
        npts = len(IDs)
        self.SetNumberOfHandles(npts)
        for k0, pID in enumerate(IDs):
            pt = pts[pID]
            self.SetHandlePosition(k0, pt[0], pt[1], pt[2])

    def getSplinePolyData_ImageCS(self):
        poly = vtk.vtkPolyData()
        self.GetPolyData(poly)
        return poly

    def getSplinePolyData_WorldCS(self, imageToWorld_func, nSplinePts=100):
        pts = self.getPoints(nSplinePts=nSplinePts) # Note LOOP done here with splining
        # but if self.LOOP  AND we had NO splining - then do loop. 
        worldCoords = np.array([imageToWorld_func(i, self.sliceID) for i in pts])
        print(f"DEBUG: Have Xim {pts.shape} and Xworld {worldCoords.shape}")
        return vtkfilters.buildPolyLineFromXYZ(worldCoords, LOOP=(self.LOOP and (nSplinePts is None)))

    def getPoints(self, nSplinePts=None):
        pts = []
        for k0 in range(self.GetNumberOfHandles()):
            ixyz = [0.0,0.0,0.0]
            self.GetHandlePosition(k0, ixyz)
            pts.append(ixyz)
        if nSplinePts is not None:
            pts = vtkfilters.ftk.splinePoints(pts, nSplinePts, periodic=self.LOOP, RETURN_NUMPY=False)
        return np.array(pts).T

    def getPlane(self):
        return vtkfilters.ftk.fitPlaneToPoints(self.getPoints())

    def addPoint(self, X):
        self.SetHandlePosition(self.GetNumberOfHandles(), X[0], X[1], X[2])
        self.SetNumberOfHandles(self.GetNumberOfHandles() + 1)
        self.SetEnabled(1)
        self.On()
        self.GetLineProperty().SetColor(1,0,0)

    def getActor(self):
        pass
        return None
    
    def __del__(self):
        """Destructor to ensure proper cleanup of VTK widget"""
        try:
            self.SetEnabled(0)
            self.Off()
        except:
            # Ignore errors during destruction
            pass

### ====================================================================================================================
### MARKUP - POLYDATAS - LIST
class MarkupPolydatas(list):
    def __init__(self):
        super(MarkupPolydatas, self).__init__([])

    def addPolydata(self, X, timeID=0, sliceID=0, color=(0,0,1)):
        self.append(MarkupPolydata(X, timeID=timeID, sliceID=sliceID, color=color))

    def getListOfActors(self):
        return [i.getActor() for i in self]
### ====================================================================================================================
### MARKUP - POLYDATA
class MarkupPolydata(Markup):
    def __init__(self, polydata, timeID=0, sliceID=0, color=(0, 0, 1)):
        super().__init__(None, timeID, sliceID)  # No coordinate system for polydata
        self.polydata = polydata
        self.color = color

    def getActor(self):
        pdMapper = vtk.vtkPolyDataMapper()
        pdMapper.SetInputData(self.polydata)
        pdActor = vtk.vtkActor()
        pdActor.GetProperty().SetColor(self.color)
        pdActor.GetProperty().SetLineWidth(4)
        pdActor.PickableOff()
        pdActor.SetMapper(pdMapper)
        return pdActor

###             NOT USED
### ====================================================================================================================
### ====================================================================================================================
### ====================================================================================================================
### ====================================================================================================================
class MarkupContour(Markup):

    def __init__(self, sliceID, timeID, time, cVal, X, MANUAL=False, minLength=0.1):
        super().__init__(sliceID, timeID, time)
        self.cVal = cVal
        self.MANUAL = MANUAL
        self.X = X
        self.minLength = minLength # THIS DOES NOTHING

    def __getClosestConnected_Size(self, data, X=None): # DID NOT WORK - TOO SLOW
        if X is None:
            X = self.X
        cc = vtkfilters.getConnectedRegionAll(data, minLength=self.minLength)
        dd = [vtk.vtkMath.Distance2BetweenPoints(X, ic.GetCenter()) for ic in cc]
        mindd = np.argmin(dd)
        return cc[mindd]

    def getContourPoly(self, imageResliceAsVTP, XOverride=None, LIMIT_TO_ONE=True):
        cc = vtkfilters.contourFilter(imageResliceAsVTP, self.cVal)
        # return self.__getClosestConnected_Size(cc, XOverride)
        if LIMIT_TO_ONE:
            if XOverride is not None:
                cc = vtkfilters.getConnectedRegionClosestToX(cc, XOverride)
            elif self.X is not None:
                cc = vtkfilters.getConnectedRegionClosestToX(cc, self.X)
        return cc

    def getContourActor(self, imageResliceAsVTI, XOverride=None, LIMIT_TO_ONE=False):
        cc = self.getContourPoly(imageResliceAsVTI, XOverride, LIMIT_TO_ONE=LIMIT_TO_ONE)
        cutMapper = vtk.vtkPolyDataMapper()
        cutMapper.SetInputData(cc)
        cutMapper.ScalarVisibilityOff()
        planeActor = vtk.vtkActor()
        planeActor.GetProperty().SetOpacity(0.8)
        if self.MANUAL:
            planeActor.GetProperty().SetColor([1, 0, 0])
        else:
            planeActor.GetProperty().SetColor([0, 0, 1])
        planeActor.GetProperty().SetLineWidth(1.5)
        # planeActor.GetProperty().SetAmbient(1)
        # planeActor.GetProperty().SetSpecularColor(1, 1, 1)
        # planeActor.GetProperty().SetDiffuseColor([1, 0, 0])
        # planeActor.GetProperty().SetDiffuse(0.8)
        # planeActor.GetProperty().SetSpecular(0.3)
        # planeActor.GetProperty().SetSpecularPower(20)
        planeActor.GetProperty().SetRepresentationToSurface()
        planeActor.SetMapper(cutMapper)
        planeActor.PickableOff()
        return planeActor


### ====================================================================================================================
### MARKUP - MASKS - LIST
class MarkupMasks(list):
    def __init__(self):
        super(MarkupMasks, self).__init__([])

### ====================================================================================================================
class MarkupMask(Markup):

    def __init__(self, timeID, time, baseImage, MANUAL=False, maskLabel='mask', RGB=(0.0,1.0,0.0), alpha=0.3):
        super().__init__(0, timeID, time)
        # self.mask = vtk.vtkImageMask()
        # self.mask.SetImageInput(baseImage)  # Original image
        # maskImage = vtkfilters.copyImage(baseImage)
        # self.mask.SetMaskInput(maskImage)    # Mask image (0s and 1s)
        # self.mask.SetMaskedOutputValue(0)    # Value for masked regions
        # self.mask.Update()
        # self.MANUAL = MANUAL
        # self.maskLabel = maskLabel
        # self.RGB = RGB
        # self.alpha = alpha

    # def setMask_upper_lower(self, baseArray, upper, lower):
    #     self.array = 

    def getMaskSlice_Ax(self, sliceID):
        return np.flip(self.array[:,:,sliceID],1).flatten('F').astype(int)
    def getMaskSlice_Sag(self, sliceID):
        return np.flip(self.array[sliceID,:,:],0).flatten('F').astype(int)
    def getMaskSlice_Cor(self, sliceID):
        return self.array[:,sliceID,:].flatten('F').astype(int)

    def errode(self, structure=None, errodeMask=None, iterations=1):
        self.array = ndimage.binary_erosion(self.array, iterations=iterations, structure=structure, mask=errodeMask).astype(int)
        # self.array[self.array>0]+=1

    def dilate(self, structure=None, dilateMask=None, iterations=1):
        self.array = ndimage.binary_dilation(self.array, iterations=iterations, structure=structure, mask=dilateMask).astype(int)
        # self.array[self.array>0]+=1

    def arrayToImageData(self, vtiToCopy):
        ii = vtk.vtkImageData()
        ii.SetOrigin(vtiToCopy.GetOrigin())
        ii.SetDimensions(vtiToCopy.GetDimensions())
        ii.SetSpacing(vtiToCopy.GetSpacing())
        vtkfilters.addNpArray(ii, self.array.astype(int), 'MASK', SET_SCALAR=True, IS_3D=True)
        return ii

    def getPolyData(self, iiToCopy):
        ii = self.arrayToImageData(iiToCopy)
        return vtkfilters.contourFilter(ii, 0.5)


    def getMaskPoints(self, imageReslice, sliceID, sag_cor_ax_int, closestPt=None):
        """

        :param imageReslice: pass in polydata from getCurrentResliceAsVTP
        :param sliceID:
        :param sag_cor_ax_int:
        :param closestPt: if given - will get closest connected
        :return: vtkPolyData of cell centers
        """
        if sag_cor_ax_int == 0:
            A = self.getMaskSlice_Sag(sliceID)
        elif sag_cor_ax_int == 1:
            A = self.getMaskSlice_Cor(sliceID)
        elif sag_cor_ax_int == 2:
            A = self.getMaskSlice_Ax(sliceID)
        vtkfilters.addNpArray(imageReslice, A, self.maskLabel, SET_SCALAR=True)
        tt = vtkfilters.filterThreshold(imageReslice, self.maskLabel, 0.5)
        if closestPt is not None:
            tt = vtkfilters.getConnectedRegionClosestToX2(tt, closestPt.GetCenter())
        cellCenters = vtkfilters.getCellCenters(tt)
        return cellCenters


    def getMaskActor(self, imageReslice, sliceID, sag_cor_ax_int):
        if sag_cor_ax_int == 0:
            A = self.getMaskSlice_Sag(sliceID)
        elif sag_cor_ax_int == 1:
            A = self.getMaskSlice_Cor(sliceID)
        elif sag_cor_ax_int == 2:
            A = self.getMaskSlice_Ax(sliceID)
        vtkfilters.addNpArray(imageReslice, A, self.maskLabel, SET_SCALAR=True)

        lookupTable = vtk.vtkLookupTable()
        lookupTable.SetNumberOfTableValues(2)
        lookupTable.SetRange(0.0, 1.0)
        lookupTable.SetTableValue(0, 0.0, 0.0, 0.0, 0.0)
        lookupTable.SetTableValue(1, self.RGB[0], self.RGB[1], self.RGB[2], self.alpha)
        lookupTable.Build()
        mapTransparency = vtk.vtkImageMapToColors()
        mapTransparency.SetLookupTable(lookupTable)
        mapTransparency.PassAlphaToOutputOn()
        mapTransparency.SetInputData(imageReslice)
        maskActor = vtk.vtkImageActor()
        maskActor.GetMapper().SetInputConnection(mapTransparency.GetOutputPort())
        return maskActor
### ====================================================================================================================



### ====================================================================================================================
### ====================================================================================================================
def binaryArrayFromImage(imageObj, arrayName, thresholdLower, thresholdUpper):
    A = vtkfilters.getArrayAsNumpy(imageObj, arrayName)
    A = np.reshape(A, imageObj.GetDimensions(), 'F')
    tl = A > thresholdLower
    th = A < thresholdUpper
    binaryA = (tl & th)
    return binaryA

def binaryArrayFromImage_andThresholdList(imageObj, arrayName, thresholdLowerList):
    A = vtkfilters.getArrayAsNumpy(imageObj, arrayName)
    A = np.reshape(A, imageObj.GetDimensions(), 'F')
    binaryA = np.zeros(A.shape, order='F')
    for k1 in range(len(thresholdLowerList)):
        sliceTF = A[:,:,k1] > thresholdLowerList[k1]
        binaryA[sliceTF,k1] = 1.0
    return binaryA


def planes_within_tol(plane1_ABC_D, X, n2, dX, angle_tol_rad=1e-2):
    # plane1_ABC_D: iterable (A,B,C,D)
    # X: iterable (x,y,z)
    # n2: iterable normal of second plane
    # dX: distance tolerance (same units as coordinates)
    # angle_tol_rad: maximum allowed angle between normals in radians (default ~0.57°)

    A, B, C, D = map(float, plane1_ABC_D)
    n1 = np.array([A, B, C], dtype=float)
    n2 = np.array(n2, dtype=float)
    X = np.array(X, dtype=float)

    n1_norm = np.linalg.norm(n1)
    n2_norm = np.linalg.norm(n2)
    if n1_norm == 0 or n2_norm == 0:
        raise ValueError("zero-length normal provided")

    u1 = n1 / n1_norm
    u2 = n2 / n2_norm

    # make directions consistent (so D signs match)
    if np.dot(u1, u2) < 0:
        u2 = -u2

    # angle between normals
    cosang = np.clip(np.dot(u1, u2), -1.0, 1.0)
    angle = np.arccos(cosang)

    if angle > angle_tol_rad:
        return False

    # plane constants with unit normals
    D1p = D / n1_norm           # plane1: u1·p + D1p = 0
    D2p = -np.dot(u2, X)        # plane2 through point X: u2·p + D2p = 0

    dist = abs(D2p - D1p)       # perpendicular distance between parallel planes

    IS_OK = dist <= float(dX)
    return IS_OK

