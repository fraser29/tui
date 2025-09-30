import os
import vtk

from ngawari import fIO
from ngawari import vtkfilters


### ====================================================================================================================
### ====================================================================================================================

class SinglePaneImageInteractor(vtk.vtkInteractorStyleImage):
    """
    Interactor style specifically designed for single pane viewers like piwakawakaViewer.py
    Simplified version of ImageInteractor without multi-view complexity
    """

    def __init__(self, parentImageViewer):
        vtk.vtkInteractorStyleImage.__init__(self)
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
        X = self.parentImageViewer.mouseXYTo_ImageCS_X(mouseX, mouseY)
        return X

    def mMoveCallback(self, obj, event):
        try:
            mouseX, mouseY = self.GetInteractor().GetEventPosition()
            ijk, worldPos, ID = self.parentImageViewer.getReslice_IJK_X_ID_AtMouse(mouseX, mouseY)
            if ijk is not None:
                # Get pixel value from data
                pixelVal = self.parentImageViewer.getPixelValueAtPtID_tuple(ID)[0]
                #
                if pixelVal is not None:
                    self.parentImageViewer.statusBar().showMessage('I: %d, J: %d, K: %d. X: %3.3f, %3.3f, %3.3f. Pixel: %3.2f'%(
                                                                    ijk[0], ijk[1], ijk[2], worldPos[0], worldPos[1], worldPos[2],
                                                                    pixelVal))
                else:
                    self.parentImageViewer.statusBar().showMessage('I: %d, J: %d, K: %d. X: %3.3f, %3.3f, %3.3f. %s'%(
                                                                    ijk[0], ijk[1], ijk[2], worldPos[0], worldPos[1], worldPos[2],
                                                                    'No pixel data'))
            else:
                self.parentImageViewer.statusBar().showMessage('I: %d, J: %d, K: %d. X: %3.3f, %3.3f, %3.3f. %s'%(
                                                                0,0,0,0,0,0,'Outside Image'))
        except (ValueError, TypeError): # outside image
            self.parentImageViewer.statusBar().showMessage('I: %d, J: %d, K: %d. X: %3.3f, %3.3f, %3.3f. %s'%(
                                                                0,0,0,0,0,0,'Outside Image'))
        self.OnMouseMove()

    def mouseScrollForwardCallback(self, obj, event):
        if self.GetInteractor().GetShiftKey():
            # Shift + scroll = zoom
            self.OnMouseWheelForward()
        else:
            # Regular scroll = change slice
            self.parentImageViewer.scrollForwardCurrentSlice1()

    def mouseScrollBackwardCallback(self, obj, event):
        if self.GetInteractor().GetShiftKey():
            # Shift + scroll = zoom
            self.OnMouseWheelBackward()
        else:
            # Regular scroll = change slice
            self.parentImageViewer.scrollBackwardCurrentSlice1()

    def keyPressCallback(self, obj, event):
        key = self.GetInteractor().GetKeyCode()
        keySym = self.GetInteractor().GetKeySym()
        if key == "h":
            print(' . = add point (or spline point if in spline mode)')
            print(' u = remove last point')
            print(' f = finish current spline (spline mode only)')
            print(' x = cancel current spline (spline mode only)')
            print(' r = reset view')
            print(' R = reset view and window level')
            print(' m = print patient meta')
            print(' p = save screenshot')
            print(' W = write all markups as points_%time.vtp')
            print(' w = reset window level')
            print(' V = toggle verbose mode')
            print(' Use UI controls to switch between Point and Spline modes')
            print('pressed help (%s)'%(key))
        elif key == ".":
            X = self.getXAtMouse()
            norm = self.parentImageViewer.getCurrentViewNormal()
            self.parentImageViewer.addPoint(X, norm)
        elif key == "u":
            self.parentImageViewer.removeLastPoint()
        elif key == "f":  # Finish current spline
            if hasattr(self.parentImageViewer, 'finishCurrentSpline'):
                self.parentImageViewer.finishCurrentSpline()
        elif key == "x":  # Cancel current spline
            if hasattr(self.parentImageViewer, 'cancelCurrentSpline'):
                self.parentImageViewer.cancelCurrentSpline()
        elif key == "R":
            self.parentImageViewer.cameraReset()
            self.parentImageViewer.cameraReset3D()
            self.parentImageViewer.resetWindowLevel()
        elif key == "r":
            self.parentImageViewer.cameraReset()
        elif key == "m":
            print(self.parentImageViewer.patientMeta)
        elif key == "p": # SCREENSHOT
            ffOut = os.path.join(self.parentImageViewer.workingDirLineEdit.text(), 'screenshot.png')
            windowToImageFilter = vtk.vtkWindowToImageFilter()
            windowToImageFilter.SetInput(self.parentImageViewer.graphicsViewVTK.GetRenderWindow())
            windowToImageFilter.Update()

            writer = vtk.vtkPNGWriter()
            writer.SetFileName(ffOut)
            writer.SetInputConnection(windowToImageFilter.GetOutputPort())
            writer.Write()
            print(f"Screenshot saved to {ffOut}")
        elif key == "W":
            ## WRITE OUT MARKUPS
            allMarkupPointsThisTime = self.parentImageViewer.Markups.getAllPointsForTime(self.parentImageViewer.currentTimeID)
            if len(allMarkupPointsThisTime) > 0:
                pointsPP = vtkfilters.buildPolydataFromXYZ([i.xyz for i in allMarkupPointsThisTime])
                print(fIO.writeVTKFile(pointsPP, os.path.join(self.parentImageViewer.workingDirLineEdit.text(), 'points_%d.vtp'%(self.parentImageViewer.currentTimeID))))
        elif key == "c":
            val = input("Give the contour level")
            try:
                val = float(val)
                self.parentImageViewer.setContourVal(val)
            except TypeError:
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

### ====================================================================================================================
### ====================================================================================================================
