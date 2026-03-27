#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Created on 12 May 2022

Some general utilities to support tui


@author: Fraser M. Callaghan
@email: callaghan.fm@gmail.com
"""

from tui import tuimarkupui

import numpy as np
import vtk
from ngawari import vtkfilters, ftk
colors = vtk.vtkNamedColors()



# ==========================================================
#   CONSTANTS
# ==========================================================
colours = [[1.0, 0.0, 0.0],
           [1.0, 1.0, 0.0],
           [1.0, 0.0, 1.0],
           [0.0, 1.0, 0.0],
           [0.0, 1.0, 1.0],
           [0.0, 0.0, 1.0],
           [0.5, 0.0, 0.0],
           [0.5, 0.5, 0.0],
           [0.5, 0.0, 0.5],
           ]

AXIAL = 'AXIAL'
CORONAL = 'CORONAL'
SAGITTAL = 'SAGITTAL'
CUSTOM = 'Custom'


# ==========================================================
#   DIALOG FUNCTIONS
# ==========================================================
def dialogGetName(parent, prompt='Enter feature name:'):
    text, ok = tuimarkupui.QtWidgets.QInputDialog.getText(parent, 'Input Dialog',
                                          prompt)
    if ok:
        return str(text)
    return  ''


def dialogGetNumber(parent, infoStr='Enter value:', parse=float):
    text, ok = tuimarkupui.QtWidgets.QInputDialog.getText(parent, 'Input Dialog',
                                          infoStr)
    if ok:
        return parse(text)
    return  ''


def checkIfExtnPresent(fileName, extn): # TODO rename
    if (extn[0] == '.'):
        extn = extn[1:]

    le = len(extn)
    if (fileName[-le:] != extn):
        fileName = fileName + '.' + extn
    return fileName


def getApp(appName):
    app = tuimarkupui.QtWidgets.QApplication([appName])
    return app


# ==========================================================
#   COLOR MAP FUNCTIONS
# ==========================================================
def buildColorMap(scalarRange, imageReslice):
    table = vtk.vtkLookupTable()
    table.SetRange(scalarRange[0], scalarRange[1])  # image intensity range
    table.SetValueRange(0.0, 1.0)  # from black to white
    table.SetSaturationRange(0.0, 0.0)  # no color saturation
    table.SetRampToLinear()
    table.Build()
    # Map the image through the lookup table
    colorM = vtk.vtkImageMapToColors()
    colorM.SetLookupTable(table)
    colorM.SetInputConnection(imageReslice.GetOutputPort())
    return colorM


# ==========================================================
#   RENDER FUNCTIONS
# ==========================================================
def renderPolyData3D(actorsList):
    ren = vtk.vtkRenderer()
    renWin = vtk.vtkRenderWindow()
    renWin.AddRenderer(ren)
    iren = vtk.vtkRenderWindowInteractor()
    iren.SetRenderWindow(renWin)
    for iActor in actorsList:
        ren.AddActor(iActor)
    ren.SetBackground(0,0,0)
    renWin.SetSize(500, 500)
    style = vtk.vtkInteractorStyleTrackballCamera()
    iren.SetInteractorStyle(style)
    ren.ResetCamera()
    iren.Initialize()
    renWin.Render()
    iren.Start()
    return ren


def renderVolume3D(vtiObj):
    ren1 = vtk.vtkRenderer()
    renWin = vtk.vtkRenderWindow()
    renWin.AddRenderer(ren1)
    iren = vtk.vtkRenderWindowInteractor()
    iren.SetRenderWindow(renWin)
    # Create transfer mapping scalar value to opacity.
    opacityTransferFunction = vtk.vtkPiecewiseFunction()
    aMin, aMax = vtiObj.GetScalarRange()
    opacityTransferFunction.AddPoint(aMin, 0.0)
    opacityTransferFunction.AddPoint(aMax, 1.0)
    # Create transfer mapping scalar value to color.
    colorTransferFunction = vtk.vtkColorTransferFunction()
    colorTransferFunction.AddRGBPoint(aMin, 0.0, 0.0, 0.0)
    # colorTransferFunction.AddRGBPoint(64.0, 1.0, 0.0, 0.0)
    # colorTransferFunction.AddRGBPoint(128.0, 0.0, 0.0, 1.0)
    # colorTransferFunction.AddRGBPoint(192.0, 0.0, 1.0, 0.0)
    colorTransferFunction.AddRGBPoint(aMax, 1.0, 1.0, 1.0)
    # The property describes how the data will look.
    volumeProperty = vtk.vtkVolumeProperty()
    volumeProperty.SetColor(colorTransferFunction)
    volumeProperty.SetScalarOpacity(opacityTransferFunction)
    volumeProperty.ShadeOn()
    volumeProperty.SetInterpolationTypeToLinear()
    # The mapper / ray cast function know how to render the data.
    volumeMapper = vtk.vtkFixedPointVolumeRayCastMapper()
    volumeMapper.SetInputData(vtiObj)
    # The volume holds the mapper and the property and
    # can be used to position/orient the volume.
    volume = vtk.vtkVolume()
    volume.SetMapper(volumeMapper)
    volume.SetProperty(volumeProperty)
    ren1.AddVolume(volume)
    ren1.SetBackground(0,0,0)
    style = vtk.vtkInteractorStyleTrackballCamera()
    iren.SetInteractorStyle(style)
    ren1.ResetCamera()
    iren.Initialize()
    renWin.SetSize(600, 600)
    renWin.Render()
    iren.Start()
    return ren1


# ==========================================================
#   IMAGE FUNCTIONS
# ==========================================================
def imageX_2_PointID(imageData, X):
    ptID = imageData.FindPoint(X)
    if ptID < 0:
        raise ValueError('Point is outside of image (X=%s)'%(str(X)))
    return ptID


def imageX_2_IJK(imageData, X):
    ptID = imageX_2_PointID(imageData, X)
    return imageID_2_IJK(imageData, ptID)


def imageID_2_IJK(imageData, ID):
    # ijk = [0, 0, 0]
    # pcoords = [0.0, 0.0, 0.0]
    # res = imageData.ComputeStructuredCoordinates(iX, ijk, pcoords)
    # if res == 0:
    #     return [0, 0, 0]
    return np.unravel_index(ID, shape=imageData.GetDimensions(), order='F')


# ==========================================================
#   POLYDATA FUNCTIONS
# ==========================================================
def polydataFromX(X):
    myVtkPoints = vtk.vtkPoints()
    vertices = vtk.vtkCellArray()
    ptID = myVtkPoints.InsertNextPoint(X[0], X[1], X[2])
    vertices.InsertNextCell(1)
    vertices.InsertCellPoint(ptID)
    polyData = vtk.vtkPolyData()
    polyData.SetPoints(myVtkPoints)
    polyData.SetVerts(vertices)
    return polyData


# ==========================================================
#   SHOW NEW 3D WINDOW FUNCTIONS
# ==========================================================
def showNew3DWindow(listOfPolyData, listOfRGB=[]):
    renderer = vtk.vtkRenderer()
    renwin = vtk.vtkRenderWindow()
    renwin.AddRenderer(renderer)
    # An interactor
    interactor = vtk.vtkRenderWindowInteractor()
    interactor.GetInteractorStyle().SetCurrentStyleToTrackballCamera()
    interactor.SetRenderWindow(renwin)
    renderer.SetBackground(colors.GetColor3d('White'))

    # Add spheres to play with
    for k1 in range(len(listOfPolyData)):

        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputData(listOfPolyData[k1])
        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(listOfRGB[k1][0],
                                    listOfRGB[k1][1],
                                    listOfRGB[k1][2])
        if len(listOfRGB[k1]) == 4:
            actor.GetProperty().SetOpacity(listOfRGB[k1][3])
        # print(actor)
        renderer.AddActor(actor)
    # Start
    interactor.Initialize()
    renwin.Render()
    interactor.Start()



# ======================================================================================================================
#   -- HELPERS --
# ======================================================================================================================

# ==========================================================
#   ORIENTATION MATRIX FUNCTIONS
# ==========================================================
def _getOrientationMatrix(ORIENTATION, center):
    ''' Matrices for axial, coronal, sagittal
    '''
    if ORIENTATION == AXIAL:
        mat = vtk.vtkMatrix4x4()
        mat.DeepCopy((1, 0, 0, center[0],
                        0, 1, 0, center[1],
                        0, 0, 1, center[2],
                        0, 0, 0, 1))
        # mat.DeepCopy((-1, 0, 0, center[0],
        #                 0, -1, 0, center[1],
        #                 0, 0, 1, center[2],
        #                 0, 0, 0, 1))
    elif ORIENTATION == CORONAL:
        mat = vtk.vtkMatrix4x4()
        mat.DeepCopy((1, 0, 0, center[0],
                          0, 0, 1, center[1],
                          0, -1, 0, center[2],
                          0, 0, 0, 1))
    elif ORIENTATION == SAGITTAL:
        mat = vtk.vtkMatrix4x4()
        mat.DeepCopy((0, 0,-1, center[0],
                           1, 0, 0, center[1],
                           0, -1, 0, center[2],
                           0, 0, 0, 1))
    return mat


# ==========================================================
#   RESLICE FUNCTIONS
# ==========================================================
def defineReslice(vtiObj, ORIENTATION, center, normalVector=None, guidingVector=None, slabNumberOfSlices=2):
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


