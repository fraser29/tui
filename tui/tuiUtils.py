#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Created on 12 May 2022

Some general utilities to support tui


@author: Fraser M. Callaghan
@email: callaghan.fm@gmail.com
"""

from TTK import tuimarkupui

import numpy as np
import vtk
colors = vtk.vtkNamedColors()


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


def dialogGetName(parent):
    text, ok = tuimarkupui.QtWidgets.QInputDialog.getText(parent, 'Input Dialog',
                                          'Enter feature name:')
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



