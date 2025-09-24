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

class CoordinateSystem:
    """Abstract base for coordinate transformations"""
    def __init__(self, parentImageViewer):
        self.parentImageViewer = parentImageViewer
    
    def imageToWorld(self, imageCoords):
        """Transform image coordinates to world coordinates"""
        raise NotImplementedError("Subclasses must implement imageToWorld")
    
    def worldToImage(self, worldCoords):
        """Transform world coordinates to image coordinates"""
        raise NotImplementedError("Subclasses must implement worldToImage")
    
    def getTransformMatrix(self):
        """Get the current transform matrix"""
        raise NotImplementedError("Subclasses must implement getTransformMatrix")

class Viewer2DCoordinateSystem(CoordinateSystem):
    """2D viewer coordinate system (piwakawaka)"""
    
    def imageToWorld(self, imageCoords):
        """Transform image coordinates to world coordinates using reslice matrix"""
        if hasattr(self.parentImageViewer, 'imageCS_To_WorldCS_X'):
            return self.parentImageViewer.imageCS_To_WorldCS_X(imageCoords)
        else:
            # Fallback for compatibility
            return imageCoords
    
    def worldToImage(self, worldCoords):
        """Transform world coordinates to image coordinates"""
        # For 2D viewers, this is more complex - may need inverse transformation
        # For now, return as-is (this might need refinement based on your specific needs)
        return worldCoords
    
    def getTransformMatrix(self):
        """Get the current reslice matrix"""
        if hasattr(self.parentImageViewer, 'getCurrentResliceMatrix'):
            return self.parentImageViewer.getCurrentResliceMatrix()
        else:
            return None

class Viewer3DCoordinateSystem(CoordinateSystem):
    """3D viewer coordinate system (tui)"""
    
    def imageToWorld(self, imageCoords):
        """Transform image coordinates to world coordinates"""
        # In 3D viewers, image and world coordinates are typically the same
        # But we can apply transformation if needed
        if hasattr(self.parentImageViewer, 'imageResliceXToRealWorldPolydataPt'):
            return self.parentImageViewer.imageResliceXToRealWorldPolydataPt(imageCoords).GetCenter()
        else:
            # For 3D viewers, image and world coordinates are usually the same
            return imageCoords
    
    def worldToImage(self, worldCoords):
        """Transform world coordinates to image coordinates"""
        # In 3D viewers, image and world coordinates are typically the same
        return worldCoords
    
    def getTransformMatrix(self):
        """Get the current reslice matrix"""
        if hasattr(self.parentImageViewer, 'getCurrentResliceMatrix'):
            return self.parentImageViewer.getCurrentResliceMatrix()
        else:
            return None

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
        self.coordinateSystem = self._createCoordinateSystem()
        self.markupsDict = {} # Dict(k=typestr, v=Dict(k=timeID, v=list_of_markup))
        self.markupsTypesCollections = {Points: MarkupPoints,
                                        Splines: MarkupSplines,
                                        Polydata: MarkupPolydatas,
                                        Masks: MarkupMasks}
        self.reset()
    
    def _createCoordinateSystem(self):
        """Factory method to create appropriate coordinate system"""
        viewerType = type(self.parentImageViewer).__name__
        if 'piwakawaka' in viewerType.lower():
            return Viewer2DCoordinateSystem(self.parentImageViewer)
        elif 'tui' in viewerType.lower():
            return Viewer3DCoordinateSystem(self.parentImageViewer)
        else:
            # Default to 2D coordinate system for backward compatibility
            return Viewer2DCoordinateSystem(self.parentImageViewer)

    def initForNewData(self, nTimes):
        self.nTimes = nTimes
        self.reset()

    def __genEmptyDict(self, CollectionClass):
        if CollectionClass is not None:
            if CollectionClass == MarkupPoints:
                return dict(zip(range(self.nTimes), [CollectionClass(self.coordinateSystem) for _ in range(self.nTimes)]))
            elif CollectionClass == MarkupSplines:
                return dict(zip(range(self.nTimes), [CollectionClass(self.coordinateSystem) for _ in range(self.nTimes)]))
            else:
                return dict(zip(range(self.nTimes), [CollectionClass() for _ in range(self.nTimes)]))
        else:
            return dict(zip(range(self.nTimes), [[] for _ in range(self.nTimes)]))

    def reset(self, timeID=None, markupType_list=()):
        if len(markupType_list) == 0:
            markupType_list = self.markupsTypesCollections.keys()
        if timeID is None:
            for iType in markupType_list:
                self.markupsDict[iType] = self.__genEmptyDict(self.markupsTypesCollections.get(iType, None))
        else:
            for iType in markupType_list:
                self.markupsDict[iType][timeID] = self.markupsTypesCollections.get(iType, None)

    def resetMarkup(self, markupType):
        self.reset(markupType_list=[markupType])

    # ============ POINTS ==============================================================================================
    def getNumberOfPoints(self, timeID):
        return len(self.markupsDict[Points][timeID])

    def addPoint(self, X, timeID, time, norm=None):
        self.markupsDict[Points][timeID].addPoint(X, norm, timeID, time)
        if self.parentImageViewer.markupMode == 'Spline':
            if len(self.markupsDict[Points][timeID]) > 2:
                self.markupsDict[Splines][timeID].addSpline(self.markupsDict[Points][timeID].getPoints_ImageCS(), 
                                                            reslice=self.parentImageViewer.getCurrentReslice(), 
                                                            renderer=self.parentImageViewer.renderer, 
                                                            interactor=self.parentImageViewer.graphicsViewVTK, 
                                                            handDrawn=True,
                                                            LOOP=self.parentImageViewer.splineClosed,
                                                            timeID=timeID, 
                                                            time=time)
                self.markupsDict[Points][timeID] = MarkupPoints(self.coordinateSystem)
            
    def removeLastPoint(self, timeID):
        try:
            self.markupsDict[Points][timeID].removePoint(-1)
        except IndexError:
            pass
    # ============ SPLINES =============================================================================================
    def addSpline(self, pts, reslice, renderer, interactor, timeID, time):
        self.markupsDict[Splines][timeID].addSpline(pts, reslice, renderer, interactor, handDrawn=True, timeID=timeID, time=time)

    def getAllSplineActors(self, timeID):
        return self.markupsDict[Splines][timeID].getListOfActors()

    def showSplines_timeID(self, timeID):
        for iTimeID in self.markupsDict[Splines].keys():
            for iSpline in self.markupsDict[Splines][iTimeID]:
                if iTimeID == timeID:
                    iSpline.SetEnabled(1)
                    iSpline.On()
                else:
                    iSpline.SetEnabled(0)
                    iSpline.Off()

    def getAllPointsActors(self, timeID, pointSize, boundCP=None, boundN=None, bounddx=None):
        return self.markupsDict[Points][timeID].getActorForAllPoints(pointSize, boundCP, boundN, bounddx)

    def getAllPointsLineActor(self, timeID, lineWidth=3, LOOP=False, boundCP=None, boundN=None, bounddx=None):
        return self.markupsDict[Points][timeID].getLineActorForAllPoints(lineWidth, LOOP, boundCP, boundN, bounddx)

    def getPolylineFromPoints(self, timeID, LOOP=False):
        return self.markupsDict[Points][timeID].getPolyLine(LOOP)

    def getPolyPointsFromPoints(self, timeID):
        return self.markupsDict[Points][timeID].getPolyData()

    def getXNumpyFromPoints(self, timeID):
        return self.markupsDict[Points][timeID].getPointsNumpy()
    
    def getAllPointsForTime(self, timeID):
        """Get all points for a specific time"""
        return self.markupsDict[Points].get(timeID, [])

    # ============ POLYDATA ============================================================================================
    def addPolydata(self, polydata, timeID, time, color=(0,0,1)):
        self.markupsDict[Polydata][timeID].addPolydata(polydata, timeID=timeID, time=time, color=color)

    def getAllPolydataActors(self, timeID):
        return self.markupsDict[Polydata][timeID].getListOfActors()

### ====================================================================================================================
### MARKUP - PARENT
class Markup(object):
    """
    Parent class for Markup with coordinate system awareness
    """
    def __init__(self, coordinateSystem, timeID=0, time=0.0):
        self.coordinateSystem = coordinateSystem
        self.timeID = timeID
        self.time = time
        self.parentImageViewer = coordinateSystem.parentImageViewer
    
    def getWorldCoordinates(self):
        """Get world coordinates - implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement getWorldCoordinates")
    
    def getImageCoordinates(self):
        """Get image coordinates - implemented by subclasses"""
        raise NotImplementedError("Subclasses must implement getImageCoordinates")
    
    def transformToWorld(self, imageCoords):
        """Transform image coordinates to world"""
        return self.coordinateSystem.imageToWorld(imageCoords)
    
    def transformToImage(self, worldCoords):
        """Transform world coordinates to image"""
        return self.coordinateSystem.worldToImage(worldCoords)
    
    def getTransformMatrix(self):
        """Get the current transform matrix"""
        return self.coordinateSystem.getTransformMatrix()

### ====================================================================================================================
### MARKUP - POINTS-LIST
class MarkupPoints(list):
    def __init__(self, coordinateSystem=None):
        super(MarkupPoints, self).__init__([])
        self.pointRGB = [1, 0, 0]
        self.lineRGB = [1, 0.5, 0.7]
        self.coordinateSystem = coordinateSystem

    def addPoint(self, X, norm=None, timeID=0, time=0.0):
        # X is expected to be in image coordinates
        point = MarkupPoint(X, self.coordinateSystem, norm=norm, timeID=timeID, time=time)
        self.append(point)

    def removePoint(self, ID=-1):
        self.pop(ID)

    def getPoints_ImageCS(self):
        return np.array([i.getImageCoordinates() for i in self])

    def getPointsNumpy(self):
        return np.array([i.X for i in self])

    def getPolyData(self):
        pp = vtkfilters.buildPolydataFromXYZ(self.getPointsNumpy())
        nn = np.array([i.norm for i in self])
        vtkfilters.setArrayFromNumpy(pp, nn, "normal", SET_VECTOR=True)
        return pp

    def getPointsWithinBounds(self, CP, N, delta):
        dists = [abs(vtkfilters.ftk.distanceToPlane(i.X, N, CP)) for i in self]
        tf = np.array(dists) < delta
        return [i for B,i in zip(tf, self) if B]

    def getPolyLine(self, LOOP=False, boundCP=None, boundN=None, bounddx=None):
        if len(self) < 2:
            return None
        if boundCP is not None:
            subList = self.getPointsWithinBounds(boundCP, boundN, bounddx)
            if len(subList) == 0:
                return None
            pp = vtkfilters.buildPolyLineFromXYZ(np.array([i.X for i in subList]), LOOP)
        else:
            pp = vtkfilters.buildPolyLineFromXYZ(self.getPointsNumpy(), LOOP)
        return pp

    def getAllPointsPolyData(self, pointSize, boundCP=None, boundN=None, bounddx=None):
        if len(self) == 0:
            return None
        if boundCP is not None:
            subList = self.getPointsWithinBounds(boundCP, boundN, bounddx)
            if len(subList) == 0:
                return None
            allData = [i.getSphereSourceViewerCS(pointSize) for i in subList]
        else:
            allData = [i.getSphereSourceViewerCS(pointSize) for i in self]
        pp = vtkfilters.appendPolyDataList(allData)
        return pp

    def getActorForAllPoints(self, pointSize, boundCP=None, boundN=None, bounddx=None):
        pp = self.getAllPointsPolyData(pointSize, boundCP=boundCP, boundN=boundN, bounddx=bounddx)
        if (pp is None) or (pp.GetNumberOfPoints() < 1):
            return None
        ptMapper = vtk.vtkPolyDataMapper()
        ptMapper.SetInputData(pp)
        ptActor = vtk.vtkActor()
        ptActor.GetProperty().SetColor(self.pointRGB)
        ptActor.PickableOff()
        ptActor.SetMapper(ptMapper)
        return ptActor


    def getLineActorForAllPoints(self, lineWidth=3, LOOP=False, boundCP=None, boundN=None, bounddx=None):
        polyLine = self.getPolyLine(LOOP=LOOP, boundCP=boundCP, boundN=boundN, bounddx=bounddx)
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
    def __init__(self, X, coordinateSystem, norm=None, timeID=0, time=0.0):
        super().__init__(coordinateSystem, timeID, time)
        self._imageCoords = X  # Image coordinates (primary storage)
        self.norm = norm
        self._worldCoords = None  # Cached world coordinates
    
    @property   
    def X(self):
        """Get world coordinates (transformed from image coordinates)"""
        return self.getWorldCoordinates()
    
    @X.setter
    def X(self, value):
        """Set image coordinates and invalidate cached world coordinates"""
        self._imageCoords = value
        self._worldCoords = None
    
    @property
    def xyz(self):
        """Compatibility property for world coordinates (legacy support)"""
        return self.getWorldCoordinates()
    
    def getWorldCoordinates(self):
        """Get world coordinates (transformed from image coordinates)"""
        if self._worldCoords is None:
            self._worldCoords = self.transformToWorld(self._imageCoords)
        return self._worldCoords
    
    def getImageCoordinates(self):
        """Get image coordinates (primary storage)"""
        return self._imageCoords
    
    def updateFromImageCoords(self, imageCoords):
        """Update image coordinates and invalidate cached world coordinates"""
        self._imageCoords = imageCoords
        self._worldCoords = None
    
    def updateFromWorldCoords(self, worldCoords):
        """Update image coordinates from world coordinates"""
        self._imageCoords = self.transformToImage(worldCoords)
        self._worldCoords = None

    def getSphereSourceViewerCS(self, rad=0.002):
        Sx = vtkfilters.buildSphereSource(self.getImageCoordinates(), rad, res=16)
        return Sx

    def getPtActor(self, pointSize):
        ptMapper = vtk.vtkPolyDataMapper()
        ptMapper.SetInputData(self.getSphereSourceViewerCS(pointSize))
        ptActor = vtk.vtkActor()
        ptActor.GetProperty().SetColor([1, 0, 0])
        ptActor.PickableOff()
        ptActor.SetMapper(ptMapper)
        return ptActor

### ====================================================================================================================
### MARKUP - SPLINES - LIST
class MarkupSplines(list):
    def __init__(self, coordinateSystem=None):
        super(MarkupSplines, self).__init__([])
        self.coordinateSystem = coordinateSystem

    def addSpline(self, Xarrary, reslice, renderer, interactor, handDrawn, LOOP, timeID=0, time=0.0):
        self.append(MarkupSpline(Xarrary, reslice, renderer, interactor, handDrawn, LOOP, coordinateSystem=self.coordinateSystem, timeID=timeID, time=time))

    def getListOfActors(self):
        return [i.getActor() for i in self]
### ====================================================================================================================
### MARKUP - SPLINE
class MarkupSpline(Markup, vtk.vtkSplineWidget):
    def __init__(self, handlePoints, reslice, renderer, interactor, handDrawn, LOOP, coordinateSystem=None, timeID=0, time=0.0):
        Markup.__init__(self, coordinateSystem, timeID, time)
        vtk.vtkSplineWidget.__init__(self)


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
        if LOOP:
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

    def getActor(self):
        pass
        return None

### ====================================================================================================================
### MARKUP - POLYDATAS - LIST
class MarkupPolydatas(list):
    def __init__(self):
        super(MarkupPolydatas, self).__init__([])

    def addPolydata(self, X, timeID=0, time=0.0, color=(0,0,1)):
        self.append(MarkupPolydata(X, timeID=timeID, time=time, color=color))

    def getListOfActors(self):
        return [i.getActor() for i in self]
### ====================================================================================================================
### MARKUP - POLYDATA
class MarkupPolydata(Markup):
    def __init__(self, polydata, timeID=0, time=0.0, color=(0, 0, 1)):
        super().__init__(timeID, time)
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


