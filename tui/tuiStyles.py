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
from ngawari import vtkfilters

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
        # self.RemoveObservers('LeftButtonPressEvent')
        # self.AddObserver("LeftButtonPressEvent", self.lMButtonPressCallback)
        # self.RemoveObservers('LeftButtonReleaseEvent')
        # self.AddObserver("LeftButtonReleaseEvent", self.lMButtonReleaseCallback)
        # self.RemoveObservers('RightButtonReleaseEvent')
        # self.AddObserver("RightButtonReleaseEvent", self.rmbUp)
        # self.RemoveObservers('MiddleButtonReleaseEvent')
        # self.AddObserver("MiddleButtonReleaseEvent", self.mmbUp)
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

    ## ========== CONTOURING ===================================================================
    def modifyDefaultInteraction_contouring(self):
        self.LMB_ShiftPressed = False
        self.LMB_Pressed = False
        self.capturedPts = []
        def lmbPress(obj, ev):
            try:
                self.LMB_Pressed = True
            except NameError:
                return
            pixelVal, X, _, _, mX = self.getPixel_XYZ_IJK_ID_MxMy_UnderMouse()
            try:
                thisContour = \
                self.parentImageViewer.markups3List[self.parentImageViewer.sag_cor_ax_index].getContourValueForSliceAndTime(self.parentImageViewer.currentSliceID,
                                                                                                                            self.parentImageViewer.currentTimeID)[-1]
                if not thisContour.MANUAL:
                    pixelVal = int(self.getPixel_XYZ_IJK_ID_MxMy_UnderMouse()[0])
                    thisContour.cVal = float(pixelVal)
                    thisContour.X = [mX[0], mX[1], 0]
                    thisContour.MANUAL = True
                self.pixelPick = thisContour.cVal
            except IndexError:
                pixelVal, X, _, _, mX= self.getPixel_XYZ_IJK_ID_MxMy_UnderMouse()
                self.pixelPick = float(pixelVal)
                # self.parentImageViewer.markups3List[self.parentImageViewer.sag_cor_ax_index].resetContours()
                self.parentImageViewer.setContourVal(pixelVal)
                self.parentImageViewer.markups3List[self.parentImageViewer.sag_cor_ax_index].addContour(self.parentImageViewer.currentSliceID,
                                                          self.parentImageViewer.currentTimeID,
                                                          self.parentImageViewer.getCurrentTime(),
                                                          cVal=self.pixelPick, X=[mX[0], mX[1], 0], MANUAL=True, minLength=self.parentImageViewer.minContourLength)
            self.parentImageViewer.updateContoursAfterAChange()

        def lmbRelease(obj, ev):
            # try:
            #     R2 = vtk.vtkMath.Distance2BetweenPoints(self.capturedPts[0], self.capturedPts[-1])
            # except IndexError:
            #     R2 = 0.0
            # R2 = ftk.distTwoPoints(self.capturedPts[0], self.capturedPts[-1])
            # distmm = vtkfilters.np.sqrt(R2)*1000.0
            # if distmm > 5:
            #     print(distmm,' mm')
            self.LMB_Pressed = False
            self.capturedPts = []
            self.parentImageViewer.updateContoursAfterAChange()

        def mMove(obj, ev):
            try:
                if self.LMB_Pressed:
                    self.capturedPts.append(self.getXAtMouse())
                    dx = self.capturedPts[-1][0] - self.capturedPts[0][0]
                    delta = dx / self.parentImageViewer.boundingDist * (self.parentImageViewer.scalarRange[1] - \
                                                                        self.parentImageViewer.scalarRange[0])
                    # R2 = vtk.vtkMath.Distance2BetweenPoints(self.capturedPts[0], self.capturedPts[-1])
                    # mouseDist_mm = vtkfilters.np.sqrt(R2)*1000.0
                    thisContour = self.parentImageViewer.markups3List[self.parentImageViewer.sag_cor_ax_index].getContourValueForSliceAndTime(self.parentImageViewer.currentSliceID,
                                                                                                                                              self.parentImageViewer.currentTimeID)[-1]
                    thisContour.cVal = self.pixelPick-delta
                    self.parentImageViewer.setContourVal(thisContour.cVal)
                    self.parentImageViewer.updateContoursAfterAChange()
            except NameError:
                return

        ## adding priorities allow to control the order of observer execution
        ## (highest value first! if equal the first added observer is called first)
        self.RemoveObservers('LeftButtonPressEvent')
        self.AddObserver('LeftButtonPressEvent', lmbPress, 1.0)
        self.RemoveObservers('LeftButtonReleaseEvent')
        self.AddObserver("LeftButtonReleaseEvent", lmbRelease)
        self.RemoveObservers('MouseMoveEvent')
        self.AddObserver("MouseMoveEvent", mMove)
        # self.AddObserver('LeftButtonPressEvent', DummyFunc2, -1.0)


    ## ========== POINTS ===================================================================
    def modifyDefaultInteraction_points(self):
        self.LMB_ShiftPressed = False
        self.LMB_Pressed = False
        self.capturedPts = []
        def lmbPress(obj, ev):
            try:
                self.LMB_Pressed = True
            except NameError:
                return

            if not self.LMB_ShiftPressed:
                X = self.getXAtMouse()
                print(X)
                ijk = self.imageResliceX_to_ijk(X)
                pp = self.parentImageViewer.imageResliceXToRealWorldPolydataPt(X)
                Xwcs = pp.GetCenter()
                if self.parentImageViewer.DEBUG:
                    # print(self.parentImageViewer.imageResliceList[self.parentImageViewer.currentTimeID].GetResliceAxes())
                    print('Point select at Ximage=%5.3f,%5.3f,%5.3f. IJK=[%d,%d,%d], Xworld=%5.3f,%5.3f,%5.3f'%(
                            X[0],X[1],X[2], ijk[0], ijk[1], ijk[2], Xwcs[0], Xwcs[1], Xwcs[2]))
                self.parentImageViewer.markups3List[self.parentImageViewer.sag_cor_ax_index].addPoint(self.parentImageViewer.currentSliceID,
                                                        self.parentImageViewer.currentTimeID,
                                                        self.parentImageViewer.getCurrentTime(),
                                                        ij=ijk,
                                                        resliceXY=X,
                                                        xyz=Xwcs)
                self.parentImageViewer.updateContoursAfterAChange()

        def lmbRelease(obj, ev):
            self.LMB_Pressed = False
            # print(len(self.capturedPts))
            self.capturedPts = []
            self.parentImageViewer.updateContoursAfterAChange()

        def mMove(obj, ev):
            try:
                if self.LMB_Pressed:
                    nextX = self.getXAtMouse()
                    if len(self.capturedPts) == 0:
                        self.capturedPts.append(nextX)
                    else:
                        dx = vtk.vtkMath.Distance2BetweenPoints(self.capturedPts[-1], nextX)
                        if abs(dx) > (self.parentImageViewer.multiPointFactor*self.parentImageViewer.boundingDist):
                            self.capturedPts.append(nextX)
                            pp = self.parentImageViewer.imageResliceXToRealWorldPolydataPt(nextX)
                            self.parentImageViewer.markups3List[self.parentImageViewer.sag_cor_ax_index].addPoint(self.parentImageViewer.currentSliceID,
                                                                    self.parentImageViewer.currentTimeID,
                                                                    self.parentImageViewer.getCurrentTime(),
                                                                    resliceXY=nextX,
                                                                    ij=self.imageResliceX_to_ijk(nextX),
                                                                    xyz=pp.GetCenter())
                            self.parentImageViewer.updateContoursAfterAChange()
            except NameError:
                return

        ## adding priorities allow to control the order of observer execution
        ## (highest value first! if equal the first added observer is called first)
        self.RemoveObservers('LeftButtonPressEvent')
        self.AddObserver('LeftButtonPressEvent', lmbPress, 1.0)
        self.RemoveObservers('LeftButtonReleaseEvent')
        self.AddObserver("LeftButtonReleaseEvent", lmbRelease)
        self.RemoveObservers('MouseMoveEvent')
        self.AddObserver("MouseMoveEvent", mMove)
        # self.AddObserver('LeftButtonPressEvent', DummyFunc2, -1.0)

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
        # print('Got key press', key)
        if key == "h":
            print(' . = add point')
            print(' x = align to primary direction')
            print(' u = remove last point')
            print(' r = reset 3D view')
            print(' R = reset all views')
            print(' m = print patient meta')
            print(' p = save screenshot(s)')
            print(' T = save threshold threshold.vti')
            print(' P = save plane plane.vti')
            # print(' i = write reslice for zBIF classification') # Used by trackball (or something). Not working to override
            print(' W = write all markups as points_%time.vtp | contours_%time.vtp')
            print(' c = set contour level')
            print(' C = write contour to Working directory: input name')
            print(' o = switch limitContourToOne')
            print(' L = set contour min length - INACTIVE')
            print(' l = set multipoint factor')
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
        elif key == "r":
            self.parentImageViewer.cameraReset()

        # elif key == "s":
        #     X = self.getXAtMouse()
        #     self.parentImageViewer.addSpline(X)

        elif key == "m":
            # p, x, i, ii, mx = self.getPixel_XYZ_IJK_ID_MxMy_UnderMouse()
            # print('Pixel, XYZ, IJK, ID, MxMy = ',p, x, i, ii, mx)
            # pp = self.parentImageViewer.imageResliceXToRealWorldPolydataPt(x)
            # print('ppWCS Center =  ',pp.GetCenter())
            print(self.parentImageViewer.patientMeta)
        elif key == "p": # SCREENSHOT  / HISTOGRAM
            outDir = "/home/fraser/temp/ss"
            ffOut = '/home/fraser/temp/out.png'
            thisSlice = self.parentImageViewer.currentSliceID
            fileOutList = []
            os.system('mkdir %s'%(outDir))
            for id, k1 in enumerate(range(0, 200, 5)):
                nextSlice = thisSlice + k1
                self.parentImageViewer.moveSliceSlider(nextSlice)
                fOut = outDir + '/%d.png'%(id)
                windowToImageFilter = vtk.vtkWindowToImageFilter()
                windowToImageFilter.SetInput(self.parentImageViewer.graphicsViewVTK.GetRenderWindow())
                # windowToImageFilter.SetMagnification(3)  # set the resolution of the output image (3 times the current resolution of vtk render window)
                # windowToImageFilter.SetInputBufferTypeToRGBA()  # also record the alpha (transparency) channel
                # windowToImageFilter.ReadFrontBufferOff()  # read from the back buffer
                windowToImageFilter.Update()

                writer = vtk.vtkPNGWriter()
                writer.SetFileName(fOut)
                writer.SetInputConnection(windowToImageFilter.GetOutputPort())
                writer.Write()
                fileOutList.append(fOut)
                # os.system('convert %s -resize 400x400 %s'%(fOut, fOut))
            os.system('cd %s && montage %s -tile %dx1 -geometry 300x300+0+0 %s'%(outDir, ' '.join(fileOutList), len(fileOutList), ffOut))
            print(id, ffOut)
            shutil.rmtree(outDir)

        elif key == "T": # SAVE THRESHOLD MASK
            print("Save threshold not active")
            # print(fIO.writeVTKFile(plane, os.path.join(self.parentImageViewer.workingDirLineEdit.text(), "threshold.vti")))
            pass # currently only point markups

        elif key == "P": # SAVE PLANE
            plane = self.parentImageViewer.getCurrentResliceAsVTP()
            print(fIO.writeVTKFile(plane, os.path.join(self.parentImageViewer.workingDirLineEdit.text(), "plane.vtp")))


        elif key == "W":
            ## WRITE OUT MARKUPS
            allMarkupPointsThisTime = self.parentImageViewer.markups3List[
                self.parentImageViewer.sag_cor_ax_index].getAllPointsForTime(self.parentImageViewer.currentTimeID)
            if len(allMarkupPointsThisTime) > 0:
                pointsPP = vtkfilters.buildPolydataFromXYZ([i.xyz for i in allMarkupPointsThisTime])
                print(fIO.writeVTKFile(pointsPP, '/home/fraser/temp/points_%d.vtp'%(self.parentImageViewer.currentTimeID)))
            allContoursThisTime = self.parentImageViewer.markups3List[
                self.parentImageViewer.sag_cor_ax_index].getAllContourPolysForTime(self.parentImageViewer.currentTimeID,
                                                                                                     LIMIT_TO_ONE=self.parentImageViewer.limitContourToOne)
            if len(allContoursThisTime) > 0:
                print(fIO.writeVTKFile(vtkfilters.appendPolyDataList(allContoursThisTime),
                                       '/home/fraser/temp/contours_%d.vtp'%(self.parentImageViewer.currentTimeID)))
                # print(fIO.writeVTKFile(transPoly, '/home/fraser/temp/temp2.vtp'))

        elif key == "c":
            val = input("Give the contour level")
            try:
                val = float(val)
                self.parentImageViewer.setContourVal(val)
            except TypeError:
                pass
        elif key == "C":
            ## WRITE OUT CONTOUR - THIS SLICE AND TIME ONLY - TO WORKING DIRECTORY
            try:
                Xcs = self.parentImageViewer.markups3List[
                    self.parentImageViewer.sag_cor_ax_index].markupsDict['Contours'][self.parentImageViewer.currentTimeID][self.parentImageViewer.currentSliceID][0].X
                X = self.parentImageViewer.imageResliceXToRealWorldPolydataPt(Xcs).GetCenter()
                # thisContour = self.parentImageViewer.getCurrentContourPolydata()
                thisContour = self.parentImageViewer.markups3List[
                    self.parentImageViewer.sag_cor_ax_index].getAllContourPolyForSliceTime(self.parentImageViewer.currentSliceID,
                                                                                            self.parentImageViewer.currentTimeID,
                                                                                           closeX=X,
                                                                                            LIMIT_TO_ONE=self.parentImageViewer.limitContourToOne)
            except IndexError: # Then no contours - so check points
                allMarkupPointsThisTime = self.parentImageViewer.markups3List[self.parentImageViewer.sag_cor_ax_index].getAllPointsForSliceAndTime(self.parentImageViewer.currentSliceID,
                                                                                                                                                   self.parentImageViewer.currentTimeID)
                thisContour = vtkfilters.buildPolyLineFromXYZ([i.xyz for i in allMarkupPointsThisTime]+[allMarkupPointsThisTime[0].xyz])

            featureName = tuiUtils.dialogGetName(self.parentImageViewer)
            fileName = featureName if featureName.endswith('.vtp') else featureName+'.vtp'
            fileName = fileName if fileName.startswith('contour') else 'contour'+fileName
            fullFileOut = os.path.join(str(self.parentImageViewer.workingDirLineEdit.text()), fileName)
            print(fIO.writeVTKFile(thisContour, fullFileOut))

        elif key == "V":
            print('Add VelMRA')
            for kk in self.parentImageViewer.vtiDict.keys():
                ii = self.parentImageViewer.vtiDict[kk]
                VelMRA = vtkfilters.getArrayAsNumpy(ii, 'MRA') * vtkfilters.ftk.vectorMagnitudes(vtkfilters.getArrayAsNumpy(ii, 'Vel'))
                vtkfilters.addNpArray(ii, VelMRA, 'VelMRA')
            self.parentImageViewer.selectArrayComboBox.addItem('VelMRA')
            self.parentImageViewer.currentArray = 'VelMRA'
            self.parentImageViewer.selectArrayComboBox.setCurrentText(self.parentImageViewer.currentArray)
            print(self.parentImageViewer.currentArray)
            print(vtkfilters.getArrayAsNumpy(self.parentImageViewer.getCurrentVTIObject(), 'VelMRA').shape)


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

        elif key == "L":
            val = input('Enter contour min length')
            try:
                val = float(val)
                self.parentImageViewer.minContourLength = val
                print('Change minContourLength to %f'%(self.parentImageViewer.minContourLength))
            except ValueError:
                pass

        elif key == "l":
            val = input('Enter multipoint factor (current=%5.5f'%(self.parentImageViewer.multiPointFactor))
            try:
                val = float(val)
                self.parentImageViewer.multiPointFactor = val
                print('Change multipoint factor  to %f'%(self.parentImageViewer.multiPointFactor))
            except ValueError:
                pass

        elif key == "b":
            w,l = self.parentImageViewer.getWindowLevel()
            print(w,l)
            self.parentImageViewer.setWindowLevel(w, l)

        else:
            # Pass key to UserDefinedCallback
            # print('Pass %s to userDefined'%(key))
            self.userDefinedCallBack(key)

    def userDefinedCallBack(self, key):
        if key in self.userDefinedKeyCallbacks.keys():
            self.userDefinedKeyCallbacks[key]()

# ======================================================================================================================
# ======================================================================================================================
class ImageTracer(vtk.vtkImageTracerWidget):
    """


    THIS IS NOT WORKING - CAN INITIALISE BUT NOT INTERACTING - POSSIBLY MISSING MY KEY PRESSES - SCALE??

    """

    def __init__(self, parentImageViewer):
        vtk.vtkImageTracerWidget.__init__(self)
        self.parentImageViewer = parentImageViewer
        self.LMB_ShiftPressed = False
        self.LMB_Pressed = False
        self.capturedPts = [[]]
        self.SHOWING_MARKUP = False
        self.pixelPick = 0
        #
        self.SetCaptureRadius(150)
        self.GetGlyphSource().SetColor(1, 0, 0)
        #
        # Set the size of the glyph handle
        self.GetGlyphSource().SetScale(0.03)
        #
        # Set the initial rotation of the glyph if desired.  The default glyph
        # set internally by the widget is a '+' so rotating 45 deg. gives a 'x'
        self.GetGlyphSource().SetRotationAngle(45.0)
        self.GetGlyphSource().Modified()
        self.ProjectToPlaneOn()

    def setUp(self):
        self.SetProjectionNormalToZAxes()
        self.SetProjectionPosition(self.parentImageViewer.sliceCenters[self.parentImageViewer.currentSliceID][self.parentImageViewer.sag_cor_ax_index])
        self.SetViewProp(self.parentImageViewer.imageActorList[self.parentImageViewer.currentTimeID])
        self.SetInputData(self.parentImageViewer.getCurrentVTIObject())
        self.SetInteractor(self.parentImageViewer.graphicsViewVTK)
        self.PlaceWidget()
        # When the underlying vtkDataSet is a vtkImageData, the widget can be
        # forced to snap to either nearest pixel points, or pixel centers.
        self.SnapToImageOn()
        # Automatically form closed paths.
        self.AutoCloseOn()
        # self.AddObserver("KeyPressEvent", self.keyPressCallback)
        # self.modifyDefaultInteraction_default()
        self.On()
        self.InteractionOn()
        print(self.GetHandlePosition(0))
        print(self.parentImageViewer.sliceCenters[self.parentImageViewer.currentSliceID])

    def modifyDefaultInteraction_default(self):
        self.LMB_ShiftPressed = False
        self.LMB_Pressed = False
        self.capturedPts = [[]]
        #
        self.RemoveObservers('LeftButtonPressEvent')
        self.AddObserver("LeftButtonPressEvent", self.lMButtonPressCallback)
        self.RemoveObservers('LeftButtonReleaseEvent')
        self.AddObserver("LeftButtonReleaseEvent", self.lMButtonReleaseCallback)
        self.RemoveObservers('MouseWheelForwardEvent')
        self.AddObserver("MouseWheelForwardEvent", self.mouseScrollForwardCallback)
        self.RemoveObservers('RightButtonReleaseEvent')
        self.AddObserver("RightButtonReleaseEvent", self.rmbUp)
        self.RemoveObservers('MiddleButtonReleaseEvent')
        self.AddObserver("MiddleButtonReleaseEvent", self.mmbUp)
        self.RemoveObservers('MouseWheelBackwardEvent')
        self.AddObserver("MouseWheelBackwardEvent", self.mouseScrollBackwardCallback)
        # self.RemoveObservers('KeyPressEvent')
        self.RemoveObservers('MouseMoveEvent')
        self.AddObserver("MouseMoveEvent", self.mMoveCallback)

class ImageTracerInteractorStyle(vtk.vtkInteractorStyleImage):
    def __init__(self, parent):
        self.parent = parent
        self.AddObserver("LeftButtonPressEvent", self.OnLeftButtonDown)
        self.AddObserver("LeftButtonReleaseEvent", self.OnLeftButtonUp)

    def OnLeftButtonDown(self, obj, event):
        self.parent.tracerWidget.SetEnabled(1)
        self.parent.tracerWidget.On()

    def OnLeftButtonUp(self, obj, event):
        self.parent.tracerWidget.SetEnabled(0)
        self.parent.tracerWidget.Off()
        # Get the traced path
        path = vtk.vtkPolyData()
        self.parent.tracerWidget.GetPath(path)
        # Do something with the path...



### ====================================================================================================================
### ====================================================================================================================

class PaintInteractorStyle(vtk.vtkInteractorStyleImage):
    def __init__(self, parent=None):
        self.parent = parent
        self.AddObserver("LeftButtonPressEvent", self.OnLeftButtonDown)
        self.AddObserver("LeftButtonReleaseEvent", self.OnLeftButtonUp)
        self.AddObserver("MouseMoveEvent", self.OnMouseMove)
        
    def OnLeftButtonDown(self, obj, event):
        self.parent.isDrawing = True
        x, y = self.GetInteractor().GetEventPosition()
        self.parent.paintLabel(x, y)
        
    def OnLeftButtonUp(self, obj, event):
        self.parent.isDrawing = False
        
    def OnMouseMove(self, obj, event):
        if self.parent.isDrawing:
            x, y = self.GetInteractor().GetEventPosition()
            self.parent.paintLabel(x, y)