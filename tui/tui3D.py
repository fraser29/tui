#!/usr/bin/env python
'''
Created on 14 Feb 2020

Classes and mini applications to interact with 3D data via VTK

@author: fraser
'''

from __future__ import print_function
import vtk
import sys
import os
import numpy as np
from ngawari import fIO
from ngawari import vtkfilters
from TTK.tuiUtils import renderVolume3D



colors = vtk.vtkNamedColors()


# def add_SSAO(ren):
#
#     bounds = np.asarray(ren.ComputeVisiblePropBounds())
#
#     b_r = np.linalg.norm([bounds[1] - bounds[0], bounds[3] - bounds[2], bounds[5] - bounds[4]])
#
#     occlusion_radius = b_r * 0.1 # tune to your preference
#     occlusion_bias = 0.04 # not actually sure what this does
#
#     passes = vtk.vtkRenderPassCollection()
#     passes.AddItem(vtk.vtkRenderStepsPass())
#
#     seq = vtk.vtkSequencePass()
#     seq.SetPasses(passes)
#
#     ssao = vtk.vtkSSAOPass()
#     ssao.SetRadius(occlusion_radius)
#     ssao.SetDelegatePass(seq)
#     ssao.SetBias(occlusion_bias)
#     ssao.SetBlur(True)
#     ssao.SetKernelSize(256) # if this is too low the AO is inaccurate
#
#     fxaaP = vtk.vtkOpenGLFXAAPass() # Anti-Aliasing isn't included in the default
#     fxaaP.SetDelegatePass(ssao)
#
#     ren.SetPass(fxaaP)
#
#     ren.SetUseDepthPeeling(True)
#     ren.SetOcclusionRatio(0.1)
#     ren.SetMaximumNumberOfPeels(100)
#
#     return ren

class FCStyleMaster():
    def __init__(self, parent, helpStr='\n==== HELP ====\ns: actor to picked list. d: remove actor from list'):
        self.__helpStr = helpStr
        self.LastPickedActor = None
        self.LastPickedProperty = vtk.vtkProperty()
        self.NewPickedActor =  None
        self.parent = parent

    def addToHelpString(self, extraStr):
        self.__helpStr += '\n' + extraStr

    def keyPressCallback(self, obj, event):
        key = self.GetInteractor().GetKeyCode()
        # print('Got key press', key)
        if key == "s":
            if self.NewPickedActor:
                # pickedPolyData = self.NewPickedActor.GetMapper().GetInput()
                if (self.NewPickedActor not in self.parent.pickedActorsListA) & \
                        (self.NewPickedActor not in self.parent.pickedActorsListB):
                    self.parent.pickedActorsListA.append(self.NewPickedActor)
                    print('Added actor to list A (%d)'%(len(self.parent.pickedActorsListA)))
        elif key == "d":
            if self.NewPickedActor:
                if (self.NewPickedActor not in self.parent.pickedActorsListA) & \
                        (self.NewPickedActor not in self.parent.pickedActorsListB):
                    self.parent.pickedActorsListB.append(self.NewPickedActor)
                    print('Added actor to list B (%d)'%(len(self.parent.pickedActorsListB)))
        elif key == "h":
            print(self.__helpStr)
        elif key == 'e':
            print('WILL EXIT')
        elif key == 'i':
            print('INFO: ')
            print('    Picked list A:  %d'%(len(self.parent.pickedActorsListA)))
            print('    Picked list B:  %d'%(len(self.parent.pickedActorsListB)))
        elif key == "x":
            self.parent.execute()
        elif key == "1":
            self.parent.sc1()
        elif key == "2":
            self.parent.sc2()
        # elif key == "3": GOES TO 3D MODE
        #     self.parent.sc3()
        elif key == "4":
            self.parent.sc4()
        elif key == "5":
            self.parent.sc5()
        elif key == "6":
            self.parent.sc6()
        elif key == "7":
            self.parent.sc7()
        elif key == "8":
            self.parent.sc8()
        elif key == "9":
            self.parent.sc9()



class MouseInteractorHighLightPoint(vtk.vtkInteractorStyleTrackballCamera, FCStyleMaster):

    def __init__(self, parent=None, sphereSize=3.0, shiftR=1.0, USE_SHIFTER=False):
        """
        LMB - pick a connected surface
        a - add that surface to "
        """
        vtk.vtkInteractorStyleTrackballCamera.__init__(self)
        FCStyleMaster.__init__(self, parent=parent)
        self.AddObserver("LeftButtonPressEvent", self.leftButtonPressEvent)
        self.AddObserver("KeyPressEvent", self.keyPressCallback)
        self.unpickableID =  len(self.parent.unpickablePolydataList) # Use this to add, remove points
        self.sphereSize = sphereSize
        self.shiftR = shiftR
        self.USE_SHIFTER = USE_SHIFTER


    def shiftPtToBySurfNorm(self, surfPickOn, pt, pID):
        ss = vtkfilters.addNormalsToPolyData(surfPickOn)
        triN = ss.GetPointData().GetArray('Normals').GetTuple(pID)
        X = np.array(pt) - self.shiftR * np.array(triN)
        return X

    def leftButtonPressEvent(self, obj, event):
        picker = vtk.vtkPointPicker()
        clickPos = self.GetInteractor().GetEventPosition()
        # print("Picking point: ", clickPos[0], clickPos[1])
        picker.Pick(clickPos[0],
                     clickPos[1],
                     0,
                     self.GetInteractor().GetRenderWindow().GetRenderers().GetFirstRenderer())
        pickedID = picker.GetPointId()
        # print(pickedID)
        if pickedID >= 0:
            pickedActor = picker.GetActor()
            pickedPoly = pickedActor.GetMapper().GetInput()
            X = pickedPoly.GetPoints().GetPoint(pickedID)
            if self.USE_SHIFTER:
                X = self.shiftPtToBySurfNorm(pickedPoly, X, pickedID)
            # print("Picked value: ", pickedClosestPoint)
            ss = vtkfilters.buildSphereSource(X, self.sphereSize)
            try:
                self.parent.unpickablePolydataList[self.unpickableID] = ss
            except IndexError:
                self.parent.unpickablePolydataList.append(ss)
        else:
            self.OnLeftButtonDown()
        self.parent.update()
        return



class MouseInteractorHighLightActor(vtk.vtkInteractorStyleTrackballCamera, FCStyleMaster):

    def __init__(self, parent=None):
        vtk.vtkInteractorStyleTrackballCamera.__init__(self)
        FCStyleMaster.__init__(self, parent=parent)
        self.AddObserver("LeftButtonPressEvent", self.leftButtonPressEvent)
        self.AddObserver("KeyPressEvent", self.keyPressCallback)


    def leftButtonPressEvent(self, obj, event):
        clickPos = self.GetInteractor().GetEventPosition()
        picker = vtk.vtkPropPicker()
        picker.Pick(clickPos[0], clickPos[1], 0, self.GetDefaultRenderer())
        # If something was selected
        if picker.GetActor():
            self.NewPickedActor = picker.GetActor()
            # If we picked something before, reset its property
            if self.LastPickedActor:
                self.LastPickedActor.GetProperty().DeepCopy(self.LastPickedProperty)
            # Save the property of the picked actor so that we can
            # restore it next time
            self.LastPickedProperty.DeepCopy(self.NewPickedActor.GetProperty())
            # Highlight the picked actor by changing its properties
            self.NewPickedActor.GetProperty().SetColor(colors.GetColor3d('Yellow'))
            # self.NewPickedActor.GetProperty().SetDiffuse(1.0)
            # self.NewPickedActor.GetProperty().SetSpecular(0.0)
            # save the last picked actor
            self.LastPickedActor = self.NewPickedActor
        self.OnLeftButtonDown()
        return
    #

class TUI3DInteractor(object):
    def __init__(self, pickablePolydataList, unpickablePolydataList=None, TUBE=False):
        self.pickablePolydataList = pickablePolydataList
        self.unpickablePolydataList = unpickablePolydataList
        self.pickableActors = []
        self.pickedActorsListA = []
        self.pickedActorsListB = []
        self.TUBE = TUBE
        self.props = {}
        ##
        self.renderer = vtk.vtkRenderer()
        self.__buildRenderer()


    def execute(self):
        print('Running execution')

    def __buildRenderer(self):
        # A renderer and render window
        self.renderer.SetBackground(colors.GetColor3d('White'))

        self.renwin = vtk.vtkRenderWindow()
        self.renwin.AddRenderer(self.renderer)

        # An interactor
        self.interactor = vtk.vtkRenderWindowInteractor()
        self.interactor.SetRenderWindow(self.renwin)

    def _clearRenderer(self):
        self.renderer.RemoveAllViewProps()
        self.pickableActors = []
        self.pickedActorsListA = []
        self.pickedActorsListB = []

    def updateData(self):
        self._clearRenderer()
        # Blue actor for all pickable
        for k1 in range(len(self.pickablePolydataList)):
            mapper = vtk.vtkPolyDataMapper()
            mapper.SetInputData(self.pickablePolydataList[k1])
            actor = vtk.vtkActor()
            actor.SetMapper(mapper)

            actor.GetProperty().SetColor(colors.GetColor3d(self.props.get('COLOUR_PICKABLE','Blue')))
            actor.GetProperty().SetRepresentationToSurface()
            # actor.GetProperty().SetLineWidth(self.props.get('LINE_WIDTH',1))
            # actor.GetProperty().SetLineWidth(self.props['LINE_WIDTH'])
            actor.GetProperty().SetOpacity(self.props.get('OPACITY_PICKABLE',1.0))
            # actor.GetProperty().SetDiffuse(1.0)
            # actor.GetProperty().SetSpecular(0.0)
            self.renderer.AddActor(actor)
            self.pickableActors.append(actor)

        # Red actor for all unpickable
        for k1 in range(len(self.unpickablePolydataList)):
            mapper = vtk.vtkPolyDataMapper()
            mapper.SetInputData(self.unpickablePolydataList[k1])
            actor = vtk.vtkActor()
            actor.SetMapper(mapper)

            actor.GetProperty().SetColor(colors.GetColor3d(self.props.get('COLOUR_UNPICKABLE','Red')))
            # actor.GetProperty().SetDiffuse(1.0)
            # actor.GetProperty().SetRepresentationToWireframe()
            actor.GetProperty().SetRepresentationToSurface()
            actor.GetProperty().SetOpacity(self.props.get('OPACITY_UNPICKABLE',0.7))
            actor.PickableOff()
            self.renderer.AddActor(actor)

    def removeByActor(self, iActor):
        mapper = iActor.GetMapper()
        polydata = mapper.GetInput()
        self.pickablePolydataList.remove(polydata)
        self.renderer.RemoveActor(iActor)

    def pickableToUnpickableByActor(self, iActor):
        # UPDATE AFTER
        mapper = iActor.GetMapper()
        polydata = mapper.GetInput()
        self.pickablePolydataList.remove(polydata)
        # self.renderer.RemoveActor(iActor)
        self.unpickablePolydataList.append(polydata)

    def removeByPickedList(self):
        for iActor in self.pickedActorsListA:
            self.removeByActor(iActor)
        for iActor in self.pickedActorsListB:
            self.removeByActor(iActor)

    def pickedToUnpickableA(self):
        for iActor in self.pickedActorsListA:
            self.pickableToUnpickableByActor(iActor)

    def update(self):
        self.updateData()
        self.renwin.Render()
        # print('New render: %d, %d' % (len(self.pickablePolydataList), len(self.unpickablePolydataList)))

    def show(self):
        # Start
        self.updateData()
        self.renwin.GetInteractor().Initialize()
        self.renwin.Render()
        self.renwin.GetInteractor().Start()

    def close_window(self, ):
        self.renwin.Finalize()
        self.interactor.TerminateApp()
        del self.renwin, self.interactor

### ====================================================================================================================
### ====================================================================================================================
class TUI3DBasic_A(TUI3DInteractor):
    def __init__(self, pickableList, unpickableList=[]):
        TUI3DInteractor.__init__(self, pickableList, unpickableList)
        self.style = None
        self.setupStyleInteractor()

    def sc1(self): # LOCK -> make unpickable
        self.pickedToUnpickableA()
        self.update()

    def sc2(self): # REMOVE
        try:
            self.removeByPickedList()
        except ValueError:
            pass
        self.update()

    def sc4(self): # DELETE ALL PICKABLE
        for iActor in self.pickableActors:
            self.removeByActor(iActor)
        self.update()

    def sc5(self): # DELETE ALL PICKABLE
        for iActor in self.pickableActors:
            self.removeByActor(iActor)
        self.update()

    def execute(self): # SAVE
        appendPoly = vtkfilters.appendPolyDataList(self.unpickablePolydataList)
        print(fIO.writeVTKFile(appendPoly, '/home/fraser/temp/temp.vtp'))

    def setupStyleInteractor(self):
        # add the custom style
        self.style = MouseInteractorHighLightActor(self)
        self.style.SetDefaultRenderer(self.renderer)
        self.renwin.GetInteractor().SetInteractorStyle(self.style)
        self.style.addToHelpString('"x" to save "locked" to temp.vtp')
        self.style.addToHelpString('1: selected to locked ')
        self.style.addToHelpString('2: del selected ')
        self.style.addToHelpString('4: del unlocked')

### ====================================================================================================================
### ====================================================================================================================


### ====================================================================================================================
### ====================================================================================================================

def test():
    ff = '/media/fraser/Samsung_T3/PROJECTS/CABG/PhD_UCT_scans/E2B/contoursFull.vtp'
    pp = fIO.readVTKFile(ff)
    pList = [pp]
    # for k1, iPick in enumerate(sphList):
    #     vtkfilters.addFieldData(iPick, '%d' % (k1), 'Pick')
    i3D = TUI3DInteractor(pList, [], TUBE=True)
    i3D.show()


### ====================================================================================================================
### ====================================================================================================================


def main(args):
    if len(args) > 1:
        ff = args[1]
        print(ff)
        if ff[-4:] == '.vti':
            renderVolume3D(fIO.readVTKFile(ff))
        else:
            pp = fIO.readVTKFile(ff)
            vtkfilters.delArraysExcept(pp, [])
            # pp = vtkfilters.cleanData(pp)
            ccList = vtkfilters.getConnectedRegionAll(pp)
            # ccList = [vtkfilters.tubeFilter(i, 0.0005) for i in ccList]
            # ccList = [vtkfilters.tubeFilter(vtkfilters.filterTransformPolyData(i, 100.0), 0.1) for i in ccList]
            OBJ = TUI3DBasic_A(ccList, [])
            print('TUI3DBasic set up')
            OBJ.show()
            print('DONE')
    else:
        test()


if __name__ == '__main__':
    print(sys.argv)
    main(sys.argv)