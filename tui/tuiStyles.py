#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Created on 12 May 2022

Basic viewer for advanced image processing:


@author: Fraser M. Callaghan
@email: callaghan.fm@gmail.com
"""


import os
import vtk
import shutil

from ngawari import fIO

from tui import tuiUtils


class ImageInteractor(vtk.vtkInteractorStyleTrackballCamera):
    """
    Subclass of vtkInteractorStyleImage    vtkInteractorStyleSwitch    vtkInteractorStyleTrackballCamera

    """

    def __init__(self, parentImageViewer):
        vtk.vtkInteractorStyleTrackballCamera.__init__(self)
        self.parentImageViewer = parentImageViewer
        self.RemoveObservers("KeyPressEvent")
        self.RemoveObservers("CharEvent")
        self.LMB_ShiftPressed = False
        self.LMB_Pressed = False
        self.capturedPts = [[]]
        self.SHOWING_MARKUP = False
        self.pixelPick = 0
        #
        self.userDefinedKeyCallbacks = {}
        self.AddObserver("KeyPressEvent", self.keyPressCallback)
        self.modifyDefaultInteraction_default()


    def modifyDefaultInteraction_default(self):
        self.LMB_ShiftPressed = False
        self.LMB_Pressed = False
        self.capturedPts = [[]]
        #
        self.AddObserver("MouseWheelForwardEvent", self.mouseScrollForwardCallback)
        self.AddObserver("MouseWheelBackwardEvent", self.mouseScrollBackwardCallback)
        self.AddObserver("MouseMoveEvent", self.mMoveCallback)


    def setUserDefinedKeyCallbackDict(self, keyCallbackDict):
        self.userDefinedKeyCallbacks = keyCallbackDict


    def getXAtMouse(self):
        (mouseX, mouseY) = self.GetInteractor().GetEventPosition()
        activeRenderer = self.GetInteractor().FindPokedRenderer(mouseX, mouseY)
        self.parentImageViewer.interactionView = self.parentImageViewer.rendererArray.index(activeRenderer)
        X = self.parentImageViewer.mouseXYToWorldX(mouseX, mouseY)
        return X

    ## ========== DEFAULT ===================================================================
    def lMButtonPressCallback(self, obj, event):
        if self.GetInteractor().GetShiftKey():
            self.LMB_ShiftPressed = True
            self.capturedPts = [self.getXAtMouse()]
        else:
            self.OnLeftButtonDown()

    def lMButtonReleaseCallback(self, obj, event):
        if self.LMB_ShiftPressed:
            self.LMB_ShiftPressed = False
            print(len(self.capturedPts))
        else:
            self.interactorWindowLevelEndEvent(obj, event)
            self.OnLeftButtonUp()

    def mMoveCallback(self, obj, event):
        X = self.getXAtMouse()
        ## - Depending on view that mouse over - enable / disable the different widgets (THIS IS NEEDED)
        for i in range(3):
            if i == self.parentImageViewer.interactionView:
                self.parentImageViewer.resliceCursorWidgetArray[i].SetPriority(1.0)
            else:
                self.parentImageViewer.resliceCursorWidgetArray[i].SetPriority(-1.0)
        #
        if self.parentImageViewer.interactionView < 4:
            try:
                ptID = self.parentImageViewer.getPointIDAtX(X)
                ijk = self.parentImageViewer.getIJKAtPtID(ptID)
                pixelVal = self.parentImageViewer.getPixelValueAtPtID_tuple(ptID)
                if len(pixelVal) > 1:
                    pixelVal = tuiUtils.np.linalg.norm(pixelVal)
                else:
                    pixelVal = pixelVal[0]
                self.parentImageViewer.statusBar().showMessage('I: %d, J: %d, K: %d. X: %3.3f, %3.3f, %3.3f. Pixel: %d = %3.2f'%(
                                                                ijk[0], ijk[1], ijk[2],X[0], X[1], X[2],
                                                                ptID, pixelVal))
            except (ValueError, TypeError): # outside image
                self.parentImageViewer.statusBar().showMessage('I: %d, J: %d, K: %d. X: %3.3f, %3.3f, %3.3f. %s'%(
                                                                0,0,0,0,0,0,'Outside Image'))
        self.OnMouseMove()

    def interactorWindowLevelEndEvent(self, obj, event):
        """
        This passes any windowing levels on to all actors at moment of end leveling event
        :param obj:
        :param event:
        :return:
        """
        thisActor = self.parentImageViewer.imageActorList[self.parentImageViewer.currentTimeID]
        w = thisActor.GetProperty().GetColorWindow()
        l = thisActor.GetProperty().GetColorLevel()
        for iActor in self.parentImageViewer.imageActorList:
            if iActor == thisActor:
                continue
            prop = iActor.GetProperty()
            prop.SetColorWindow(w)
            prop.SetColorLevel(l)
        self.EndWindowLevel()

    def rmbUp(self, obj, event):
        self.OnRightButtonUp()
    def mmbUp(self, obj, event):
        self.OnMiddleButtonUp()

    def mouseScrollForwardCallback(self, obj, event):
        if self.GetInteractor().GetShiftKey():
            self.parentImageViewer.scrollForwardCurrentSlice1()
        else:
            self.OnMouseWheelForward()
            self.parentImageViewer.updateParallelScale(self.parentImageViewer.interactionView)

    def mouseScrollBackwardCallback(self, obj, event):
        if self.GetInteractor().GetShiftKey():
            self.parentImageViewer.scrollBackwardCurrentSlice1()
        else:
            self.OnMouseWheelBackward()
            self.parentImageViewer.updateParallelScale(self.parentImageViewer.interactionView)

    def keyPressCallback(self, obj, event):
        key = self.GetInteractor().GetKeyCode()
        keySym = self.GetInteractor().GetKeySym()
        print('Got key press - KeyCode:', key, 'KeySym:', keySym)
        if key == "h":
            print(' . = add point (or spline point if in spline mode)')
            print(' x = align to primary direction')
            print(' u = remove last point')
            print(' r = reset 3D view')
            print(' R = reset all views')
            print(' m = print patient meta')
            print(' p = save screenshot(s)')
            print(' P = save plane plane.vtp')
            print(' c = set contour level')
            print(' o = switch limitContourToOne')
            print(' L = set contour min length - INACTIVE')
            print(' l = set multipoint factor')
            print(' Use UI controls to switch between Point and Spline modes')
            print('pressed help (%s)'%(key))
        elif key == ".":
            X = self.getXAtMouse()
            norm = self.parentImageViewer.getCurrentViewNormal()
            self.parentImageViewer.addPoint(X, norm)
        elif key == "u":
            self.parentImageViewer.removeLastPoint()
        elif key == '1':
            self.parentImageViewer.setGrossFrame(0)
        elif key == '2':
            self.parentImageViewer.setGrossFrame(1)
        elif key == '3':
            self.parentImageViewer.setGrossFrame(2)
        elif key == '4':
            self.parentImageViewer.setGrossFrame(3)
        elif key == '5':
            self.parentImageViewer.setGrossFrame(4)

        elif key == "R":
            self.parentImageViewer.cameraReset()
            self.parentImageViewer.cameraReset3D()
            self.parentImageViewer.resetWindowLevel()
        elif key == "r":
            self.parentImageViewer.cameraReset()


        elif key == "p": # SCREENSHOT  / HISTOGRAM
            ffOut = os.path.join(self.parentImageViewer.workingDirLineEdit.text(), 'screenshot.png')
            windowToImageFilter = vtk.vtkWindowToImageFilter()
            windowToImageFilter.SetInput(self.parentImageViewer.graphicsViewVTK.GetRenderWindow())
            windowToImageFilter.Update()
            writer = vtk.vtkPNGWriter()
            writer.SetFileName(ffOut)
            writer.SetInputConnection(windowToImageFilter.GetOutputPort())
            writer.Write()

        elif key == "P": # SAVE PLANE
            plane = self.parentImageViewer.getCurrentResliceAsVTP()
            print(fIO.writeVTKFile(plane, os.path.join(self.parentImageViewer.workingDirLineEdit.text(), "plane.vtp")))

        elif key == "c":
            val = input("Give the contour level")
            try:
                val = float(val)
                self.parentImageViewer.setContourVal(val)
            except TypeError:
                pass

        elif key == "L":
            val = input('Enter contour min length')
            try:
                val = float(val)
                self.parentImageViewer.minContourLength = val
                print('Change minContourLength to %f'%(self.parentImageViewer.minContourLength))
            except ValueError:
                pass

        elif key == "o":
            self.parentImageViewer.limitContourToOne = not self.parentImageViewer.limitContourToOne
            print('limitContourToOne == %s'%(self.parentImageViewer.limitContourToOne))


        elif key == "l":
            val = input('Enter multipoint factor (current=%5.5f'%(self.parentImageViewer.multiPointFactor))
            try:
                val = float(val)
                self.parentImageViewer.multiPointFactor = val
                print('Change multipoint factor  to %f'%(self.parentImageViewer.multiPointFactor))
            except ValueError:
                pass

        elif key == "w":
            w,l = self.parentImageViewer.getWindowLevel()
            print(f"Old window level: {w}, {l}")
            self.parentImageViewer.resetWindowLevel()
            print(f"New window level: {w}, {l}")

        elif key == "V":
            self.parentImageViewer.VERBOSE = not self.parentImageViewer.VERBOSE
            print(f"VERBOSE mode is now {self.parentImageViewer.VERBOSE}")

        elif keySym == 'Left':
            # Previous time step
            if self.parentImageViewer.currentTimeID > 0:
                self.parentImageViewer.currentTimeID -= 1
                self.parentImageViewer.moveTimeSlider(self.parentImageViewer.currentTimeID)
        elif keySym == 'Right':
            # Next time step
            if self.parentImageViewer.currentTimeID < len(self.parentImageViewer.times) - 1:
                self.parentImageViewer.currentTimeID += 1
                self.parentImageViewer.moveTimeSlider(self.parentImageViewer.currentTimeID)
        elif keySym == 'Up':
            # Forward slice
            self.parentImageViewer.scrollForwardCurrentSlice1()
        elif keySym == 'Down':
            # Backward slice
            self.parentImageViewer.scrollBackwardCurrentSlice1()

        else:
            # Pass key to UserDefinedCallback
            # print('Pass %s to userDefined'%(key))
            self.userDefinedCallBack(key)

    def userDefinedCallBack(self, key):
        if key in self.userDefinedKeyCallbacks.keys():
            self.userDefinedKeyCallbacks[key]()

# ======================================================================================================================
# ======================================================================================================================
# Screen shots to montage: 
            # outDir = os.path.join(self.parentImageViewer.workingDirLineEdit.text(), 'TEMP_SCREENSHOT')
            # ffOut = os.path.join(self.parentImageViewer.workingDirLineEdit.text(), 'screenshot.png')
            # thisSlice = self.parentImageViewer.currentSliceID
            # fileOutList = []
            # os.makedirs(outDir, exist_ok=True)
            # for id, k1 in enumerate(range(0, 200, 5)):
            #     nextSlice = thisSlice + k1
            #     self.parentImageViewer.moveSliceSlider(nextSlice)
            #     fOut = outDir + '/%d.png'%(id)
            #     windowToImageFilter = vtk.vtkWindowToImageFilter()
            #     windowToImageFilter.SetInput(self.parentImageViewer.graphicsViewVTK.GetRenderWindow())
            #     windowToImageFilter.Update()

            #     writer = vtk.vtkPNGWriter()
            #     writer.SetFileName(fOut)
            #     writer.SetInputConnection(windowToImageFilter.GetOutputPort())
            #     writer.Write()
            #     fileOutList.append(fOut)
            #     # os.system('convert %s -resize 400x400 %s'%(fOut, fOut))
            # os.system('cd %s && montage %s -tile %dx1 -geometry 300x300+0+0 %s'%(outDir, ' '.join(fileOutList), len(fileOutList), ffOut))
            # print(id, ffOut)
            # shutil.rmtree(outDir)